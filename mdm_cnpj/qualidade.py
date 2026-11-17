"""Motor das regras de qualidade (config/regras_qualidade.yaml).

Gera três tabelas: nao_conformidades (por registro), resultados (por regra e
fonte) e scorecard (por dimensão e fonte)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from .validadores import (VALIDADORES, cep_pertence_uf, cep_valido, cnpj_valido, eh_matriz,
                          para_data, uf_valida)

DIMENSOES = ["completude", "validade", "consistencia", "unicidade", "atualidade"]


@dataclass
class Regra:
    id: str
    nome: str
    dimensao: str
    tipo: str
    severidade: str
    acao: str = ""
    descricao: str = ""
    campo: str = ""
    campos: list[str] = field(default_factory=list)
    validador: str = ""
    valores: list[str] = field(default_factory=list)
    valor: str = ""
    dias: int = 0
    opcional: bool = False
    no_score: bool = False
    fontes: list[str] = field(default_factory=list)

    def aplica(self, fonte: str) -> bool:
        return not self.fontes or fonte in self.fontes

    @property
    def campos_alvo(self) -> str:
        return self.campo or ",".join(self.campos) or {
            "cep_uf": "cep,uf", "matriz_filial": "cnpj,tipo_estabelecimento"}.get(self.tipo, "")


@dataclass
class Catalogo:
    regras: list[Regra]
    metas: dict[str, float]
    pesos: dict[str, int]
    versao: str = ""
    dono_do_dado: str = ""
    steward: str = ""


def carregar_catalogo(caminho: Path) -> Catalogo:
    cfg = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    regras = [Regra(**r) for r in cfg["regras"]]
    ids = [r.id for r in regras]
    if len(ids) != len(set(ids)):
        raise ValueError("Há regras com id repetido no catálogo.")
    for r in regras:
        if r.dimensao not in DIMENSOES:
            raise ValueError(f"{r.id}: dimensão desconhecida '{r.dimensao}'.")
        if r.tipo == "validador" and r.validador not in VALIDADORES:
            raise ValueError(f"{r.id}: validador desconhecido '{r.validador}'.")
    return Catalogo(regras, cfg["metas"], cfg["pesos_severidade"], str(cfg.get("versao", "")),
                    cfg.get("dono_do_dado", ""), cfg.get("steward", ""))


# Cada tipo de regra devolve (avaliado, conforme)
def _preenchido(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip() != ""


def _avaliar(regra: Regra, df: pd.DataFrame, hoje: date) -> tuple[pd.Series, pd.Series]:
    todos = pd.Series(True, index=df.index)
    t = regra.tipo

    if t == "obrigatorio":
        return todos, _preenchido(df[regra.campo])

    if t == "obrigatorio_algum":
        ok = pd.Series(False, index=df.index)
        for c in regra.campos:
            ok |= _preenchido(df[c])
        return todos, ok

    if t == "validador":
        avaliado = _preenchido(df[regra.campo]) if regra.opcional else todos
        funcao = VALIDADORES[regra.validador]
        ok = df[regra.campo].map(lambda v: bool(funcao(v)) if v not in (None, "") else False)
        return avaliado, ok

    if t == "dominio":
        avaliado = _preenchido(df[regra.campo]) if regra.opcional else todos
        return avaliado, df[regra.campo].isin(regra.valores)

    if t == "igual":
        avaliado = _preenchido(df[regra.campo]) if regra.opcional else todos
        return avaliado, df[regra.campo] == regra.valor

    if t == "cep_uf":
        avaliado = df["cep"].map(cep_valido) & df["uf"].map(uf_valida)
        ok = pd.Series([cep_pertence_uf(c, u) for c, u in zip(df["cep"], df["uf"])], index=df.index)
        return avaliado, ok

    if t == "datas_ordem":
        ini = df[regra.campos[0]].map(para_data)
        fim = df[regra.campos[1]].map(para_data)
        avaliado = ini.notna() & fim.notna()
        ok = pd.Series([bool(a and b and a <= b) for a, b in zip(ini, fim)], index=df.index)
        return avaliado, ok

    if t == "matriz_filial":
        avaliado = df["cnpj"].map(cnpj_valido) & df["tipo_estabelecimento"].isin(["MATRIZ", "FILIAL"])
        ok = (df["tipo_estabelecimento"] == "MATRIZ") == df["cnpj"].map(eh_matriz)
        return avaliado, ok

    if t == "unico":
        avaliado = _preenchido(df[regra.campo])
        repetido = df[regra.campo].duplicated(keep=False) & avaliado
        return avaliado, ~repetido

    if t == "idade_maxima":
        datas = df[regra.campo].map(para_data)
        avaliado = datas.notna()
        ok = datas.map(lambda d: d is not None and (hoje - d).days <= regra.dias)
        return avaliado, ok

    raise ValueError(f"{regra.id}: tipo de regra desconhecido '{t}'.")


@dataclass
class ResultadoQualidade:
    nao_conformidades: pd.DataFrame
    resultados: pd.DataFrame
    scorecard: pd.DataFrame
    indice_geral: float
    indice_por_fonte: dict[str, float]


def avaliar(df: pd.DataFrame, catalogo: Catalogo, hoje: date | None = None) -> ResultadoQualidade:
    hoje = hoje or date.today()
    linhas_nc, linhas_res = [], []

    for fonte, parte in df.groupby("fonte", sort=True):
        for regra in catalogo.regras:
            if not regra.aplica(fonte):
                continue
            avaliado, ok = _avaliar(regra, parte, hoje)
            falhou = avaliado & ~ok.astype(bool)
            n_aval, n_falha = int(avaliado.sum()), int(falhou.sum())
            linhas_res.append({
                "regra_id": regra.id, "regra": regra.nome, "dimensao": regra.dimensao,
                "severidade": regra.severidade, "fonte": fonte, "avaliados": n_aval,
                "falhas": n_falha, "conformes": n_aval - n_falha,
                "taxa_conformidade": round(100 * (n_aval - n_falha) / n_aval, 2) if n_aval else None,
                "no_score": regra.no_score,
            })
            alvo = regra.campos_alvo
            for _, reg in parte[falhou].iterrows():
                valor = " | ".join(str(reg.get(c, "")) for c in alvo.split(",") if c)
                linhas_nc.append({
                    "fonte": fonte, "id_origem": reg["id_origem"], "cnpj": reg["cnpj"],
                    "regra_id": regra.id, "regra": regra.nome, "dimensao": regra.dimensao,
                    "severidade": regra.severidade, "campo": alvo, "valor_encontrado": valor,
                    "acao_recomendada": regra.acao,
                })

    resultados = pd.DataFrame(linhas_res)
    nc = pd.DataFrame(linhas_nc, columns=[
        "fonte", "id_origem", "cnpj", "regra_id", "regra", "dimensao", "severidade", "campo",
        "valor_encontrado", "acao_recomendada"])

    pontuaveis = resultados[~resultados["no_score"] & (resultados["avaliados"] > 0)].copy()
    pontuaveis["peso"] = pontuaveis["severidade"].map(catalogo.pesos)

    sc = (pontuaveis.groupby(["fonte", "dimensao"], as_index=False)[["avaliados", "conformes"]].sum())
    tot = pontuaveis.groupby("dimensao", as_index=False)[["avaliados", "conformes"]].sum()
    tot.insert(0, "fonte", "TODAS")
    sc = pd.concat([sc, tot], ignore_index=True)
    sc["conformidade"] = (100 * sc["conformes"] / sc["avaliados"]).round(2)
    sc["meta"] = sc["dimensao"].map(catalogo.metas)
    sc["atingiu_meta"] = sc["conformidade"] >= sc["meta"]

    def indice(p: pd.DataFrame) -> float:
        return round(100 * (p["conformes"] * p["peso"]).sum() / (p["avaliados"] * p["peso"]).sum(), 2)

    por_fonte = {f: indice(p) for f, p in pontuaveis.groupby("fonte")}
    return ResultadoQualidade(nc, resultados, sc, indice(pontuaveis), por_fonte)


def score_por_registro(df: pd.DataFrame, nc: pd.DataFrame, catalogo: Catalogo) -> pd.Series:
    """Nota de 0 a 100 por registro: 100 menos o peso das regras que ele violou.

    Usada pelo MDM como critério de desempate: entre duas fontes de mesma
    prioridade, sobrevive o valor do registro mais "saudável".
    """
    penal = (nc.assign(p=nc["severidade"].map(catalogo.pesos))
               .groupby(["fonte", "id_origem"])["p"].sum())
    chave = list(zip(df["fonte"], df["id_origem"]))
    return pd.Series([max(0, 100 - 5 * penal.get(k, 0)) for k in chave], index=df.index)
