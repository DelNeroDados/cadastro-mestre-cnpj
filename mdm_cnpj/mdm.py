"""MDM: match, sobrevivência, linhagem, crosswalk e hierarquia matriz/filial.

CNPJ válido igual = mesma empresa. Sem CNPJ válido, calculo um score de
semelhança (nome, dígitos do CNPJ, CEP). Caso duvidoso vai para a fila de
revisão em vez de ser unido automaticamente."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from .padronizacao import CAMPOS, chave_nome
from .validadores import VALIDADORES, cnpj_raiz, cnpj_valido, eh_matriz, para_data


def carregar_config(caminho: Path) -> dict:
    return yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))


def id_mestre(cnpj: str) -> str:
    """Identificador estável: o mesmo CNPJ gera sempre o mesmo id, em qualquer execução."""
    return "MDM-" + hashlib.sha1(cnpj.encode()).hexdigest()[:8].upper()


def score_similaridade(a: pd.Series, b: pd.Series, pesos: dict[str, float]) -> float:
    """Score de 0 a 1 entre dois registros. Atributos ausentes saem da conta."""
    partes: dict[str, float] = {}
    na, nb = chave_nome(a["razao_social"]), chave_nome(b["razao_social"])
    if na and nb:
        partes["nome"] = fuzz.token_sort_ratio(na, nb) / 100
    if len(a["cnpj"]) >= 12 and len(b["cnpj"]) >= 12:
        partes["cnpj"] = Levenshtein.normalized_similarity(a["cnpj"], b["cnpj"])
    if a["cep"] and b["cep"]:
        partes["cep"] = 1.0 if a["cep"] == b["cep"] else 0.0
    if a["municipio"] and b["municipio"]:
        partes["municipio"] = 1.0 if a["municipio"] == b["municipio"] else 0.0
    peso_total = sum(pesos[k] for k in partes)
    if peso_total == 0 or "nome" not in partes:  # sem nome não há base para afirmar nada
        return 0.0
    return sum(pesos[k] * v for k, v in partes.items()) / peso_total


def casar(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (crosswalk, fila_revisao)."""
    pesos = cfg["match"]["pesos"]
    lim_auto = cfg["match"]["limiares"]["automatico"]
    lim_rev = cfg["match"]["limiares"]["revisao"]

    valido = df["cnpj"].map(cnpj_valido)
    cross = pd.DataFrame({
        "fonte": df["fonte"], "id_origem": df["id_origem"], "cnpj_origem": df["cnpj"],
        "id_mestre": [id_mestre(c) if v else "" for c, v in zip(df["cnpj"], valido)],
        "metodo_match": ["cnpj_exato" if v else "" for v in valido],
        "score_match": [1.0 if v else None for v in valido],
    }, index=df.index)

    # Representante de cada CNPJ para comparação: preferimos o registro da Receita.
    ordem_fonte = {"receita": 0, "cartao": 1, "erp": 2}
    candidatos = (df[valido].assign(_o=df["fonte"].map(ordem_fonte))
                  .sort_values("_o").drop_duplicates("cnpj"))

    primeiro_token = candidatos["razao_social"].map(lambda n: (chave_nome(n).split() or [""])[0])
    fila = []
    for idx, reg in df[~valido].iterrows():
        # Blocagem por UF OU início do CEP OU primeira palavra do nome.
        # Só por UF perdia o cliente com a UF digitada errada.
        token = (chave_nome(reg["razao_social"]).split() or [""])[0]
        mesmo_bloco = pd.Series(False, index=candidatos.index)
        if reg["uf"]:
            mesmo_bloco |= candidatos["uf"] == reg["uf"]
        if len(reg["cep"]) >= 3:
            mesmo_bloco |= candidatos["cep"].str[:3] == reg["cep"][:3]
        if token:
            mesmo_bloco |= primeiro_token == token
        bloco = candidatos[mesmo_bloco]
        scores = [(score_similaridade(reg, cand, pesos), cand) for _, cand in bloco.iterrows()]
        melhor, cand = max(scores, key=lambda s: s[0], default=(0.0, None))
        melhor = round(melhor, 3)
        if cand is not None and melhor >= lim_auto:
            cross.loc[idx, ["id_mestre", "metodo_match", "score_match"]] = \
                [id_mestre(cand["cnpj"]), "fuzzy_automatico", melhor]
        elif cand is not None and melhor >= lim_rev:
            cross.loc[idx, ["metodo_match", "score_match"]] = ["revisao_steward", melhor]
            fila.append({
                "fonte": reg["fonte"], "id_origem": reg["id_origem"],
                "cnpj_origem": reg["cnpj"], "razao_social_origem": reg["razao_social"],
                "id_mestre_sugerido": id_mestre(cand["cnpj"]), "cnpj_sugerido": cand["cnpj"],
                "razao_social_sugerida": cand["razao_social"], "score": melhor,
                "decisao": "", "decidido_por": "", "data_decisao": "",
            })
        else:
            cross.loc[idx, ["metodo_match", "score_match"]] = ["sem_correspondente", melhor]
    return cross.reset_index(drop=True), pd.DataFrame(fila, columns=[
        "fonte", "id_origem", "cnpj_origem", "razao_social_origem", "id_mestre_sugerido",
        "cnpj_sugerido", "razao_social_sugerida", "score", "decisao", "decidido_por",
        "data_decisao"])


def aplicar_decisoes(cross: pd.DataFrame, decisoes: pd.DataFrame | None) -> pd.DataFrame:
    """Incorpora as decisões do Steward (decisao = UNIR ou SEPARAR) ao crosswalk.

    Fecha o ciclo humano: o Steward preenche a planilha da fila de revisão, e na
    próxima execução as decisões viram vínculos definitivos.
    """
    if decisoes is None or decisoes.empty:
        return cross
    cross = cross.copy()
    for _, d in decisoes.iterrows():
        alvo = (cross["fonte"] == d["fonte"]) & (cross["id_origem"].astype(str) == str(d["id_origem"]))
        decisao = str(d.get("decisao", "")).strip().upper()
        if decisao == "UNIR":
            cross.loc[alvo, ["id_mestre", "metodo_match"]] = [d["id_mestre_sugerido"], "decisao_steward"]
        elif decisao == "SEPARAR":
            cross.loc[alvo, "metodo_match"] = "sem_correspondente"
    return cross


def _valor_valido(campo: str, valor, cfg: dict) -> bool:
    if valor is None or str(valor).strip() == "":
        return False
    nome = cfg["sobrevivencia"].get("validar_antes", {}).get(campo)
    return VALIDADORES[nome](valor) if nome else True


def sobreviver(df: pd.DataFrame, cross: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (golden, linhagem)."""
    sv = cfg["sobrevivencia"]
    padrao = sv["padrao"]
    base = df.merge(cross[["fonte", "id_origem", "id_mestre", "metodo_match"]],
                    on=["fonte", "id_origem"])
    base = base[base["id_mestre"] != ""].copy()
    base["_data"] = base["data_referencia"].map(lambda d: para_data(d) or pd.Timestamp.min.date())

    golden, linhagem = [], []
    for mid, grupo in base.groupby("id_mestre", sort=True):
        reg = {"id_mestre": mid}
        for campo in CAMPOS:
            regra = sv.get("campos", {}).get(campo, {})
            prioridade = regra.get("prioridade", padrao["prioridade"])
            cand = grupo[[_valor_valido(campo, v, cfg) for v in grupo[campo]]]
            cand = cand[cand["fonte"].isin(prioridade)]
            distintos = sorted(set(map(str, cand[campo])))
            if cand.empty:
                reg[campo] = ""
                continue
            cand = cand.assign(_p=cand["fonte"].map(prioridade.index))
            cand = cand.sort_values(["_p", "_data", "score_registro"], ascending=[True, False, False])
            vencedor = cand.iloc[0]
            empatados = (cand["_p"] == vencedor["_p"]).sum()
            criterio = f"prioridade_fonte ({' > '.join(prioridade)})"
            if empatados > 1:
                criterio += " + mais_recente"
            reg[campo] = vencedor[campo]
            linhagem.append({
                "id_mestre": mid, "campo": campo, "valor": vencedor[campo],
                "fonte": vencedor["fonte"], "id_origem": vencedor["id_origem"],
                "data_referencia": vencedor["data_referencia"], "criterio": criterio,
                "valores_distintos": len(distintos),
                "alternativas": " | ".join(v for v in distintos if v != str(vencedor[campo]))[:300],
            })
        fontes = sorted(grupo["fonte"].unique())
        reg.update({
            "cnpj_raiz": cnpj_raiz(reg["cnpj"]),
            "eh_matriz": eh_matriz(reg["cnpj"]),
            "fontes": ",".join(fontes),
            "qtd_registros_origem": len(grupo),
            "status_mestre": "VALIDADO_RECEITA" if "receita" in fontes else "SEM_FONTE_AUTORITATIVA",
            "completude_pct": round(100 * sum(1 for c in CAMPOS if str(reg[c]).strip()) / len(CAMPOS), 1),
            "data_ultima_evidencia": max(grupo["data_referencia"].fillna("")),
        })
        golden.append(reg)
    return pd.DataFrame(golden), pd.DataFrame(linhagem)


def hierarquia(golden: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for raiz, g in golden.groupby("cnpj_raiz"):
        matriz = g[g["eh_matriz"]]
        linhas.append({
            "cnpj_raiz": raiz,
            "razao_social": (matriz if not matriz.empty else g).iloc[0]["razao_social"],
            "id_mestre_matriz": matriz.iloc[0]["id_mestre"] if not matriz.empty else "",
            "qtd_estabelecimentos": len(g),
            "qtd_filiais": int((~g["eh_matriz"]).sum()),
            "matriz_no_cadastro": not matriz.empty,
        })
    return pd.DataFrame(linhas)


@dataclass
class ResultadoMDM:
    crosswalk: pd.DataFrame
    fila_revisao: pd.DataFrame
    golden: pd.DataFrame
    linhagem: pd.DataFrame
    hierarquia: pd.DataFrame


def executar(df: pd.DataFrame, cfg: dict, decisoes: pd.DataFrame | None = None) -> ResultadoMDM:
    cross, fila = casar(df, cfg)
    cross = aplicar_decisoes(cross, decisoes)
    if decisoes is not None and not decisoes.empty:
        ja = set(zip(decisoes["fonte"], decisoes["id_origem"].astype(str)))
        fila = fila[[(f, str(i)) not in ja for f, i in zip(fila["fonte"], fila["id_origem"])]]
    golden, linhagem = sobreviver(df, cross, cfg)
    return ResultadoMDM(cross, fila, golden, linhagem, hierarquia(golden))
