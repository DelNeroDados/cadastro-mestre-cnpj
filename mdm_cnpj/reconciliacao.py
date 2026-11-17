"""Compara cartões e ERP com a Receita, campo a campo (acurácia).

No cartão, divergência pode ser só documento antigo. Quando a situação mudou
depois da emissão, isso fica anotado em motivo_provavel."""
from __future__ import annotations

import pandas as pd

from .padronizacao import chave_nome, sem_acento

CAMPOS_COMPARADOS = [
    "razao_social", "nome_fantasia", "data_abertura", "situacao_cadastral", "cnae_principal",
    "logradouro", "numero", "bairro", "municipio", "uf", "cep", "email", "telefone",
]


def _norm(campo: str, valor) -> str:
    v = sem_acento(str(valor or "")).upper().strip()
    if campo in ("razao_social", "nome_fantasia"):
        return chave_nome(v)
    return " ".join(v.split())


def reconciliar(silver: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (acuracia_por_campo, divergencias)."""
    ref = silver[silver["fonte"] == "receita"].set_index("cnpj")
    outras = silver[(silver["fonte"] != "receita") & silver["cnpj"].isin(ref.index)]

    linhas_div, contagem = [], []
    for _, reg in outras.iterrows():
        r = ref.loc[reg["cnpj"]]
        for campo in CAMPOS_COMPARADOS:
            a, b = _norm(campo, reg[campo]), _norm(campo, r[campo])
            if not a or not b:  # sem valor de um dos lados não há o que comparar
                continue
            igual = a == b
            contagem.append((reg["fonte"], campo, igual))
            if not igual:
                motivo = ""
                if (campo == "situacao_cadastral" and reg["data_referencia"]
                        and r["data_situacao_cadastral"] > reg["data_referencia"]):
                    motivo = "situacao_mudou_depois_do_documento"
                linhas_div.append({
                    "fonte": reg["fonte"], "id_origem": reg["id_origem"], "cnpj": reg["cnpj"],
                    "campo": campo, "valor_fonte": reg[campo], "valor_receita": r[campo],
                    "data_referencia_fonte": reg["data_referencia"], "motivo_provavel": motivo,
                })

    cont = pd.DataFrame(contagem, columns=["fonte", "campo", "igual"])
    if cont.empty:
        acur = pd.DataFrame(columns=["fonte", "campo", "comparados", "iguais", "acuracia"])
    else:
        acur = (cont.groupby(["fonte", "campo"])["igual"].agg(comparados="size", iguais="sum")
                .reset_index())
        acur["acuracia"] = (100 * acur["iguais"] / acur["comparados"]).round(1)
    return acur, pd.DataFrame(linhas_div, columns=[
        "fonte", "id_origem", "cnpj", "campo", "valor_fonte", "valor_receita",
        "data_referencia_fonte", "motivo_provavel"])
