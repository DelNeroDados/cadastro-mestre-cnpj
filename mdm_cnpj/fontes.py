"""Carga das três fontes para a camada silver (esquema canônico)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import extracao, receita
from .padronizacao import CAMPOS, CONTROLE, padronizar
from .validadores import cnpj_valido

COLUNAS_SILVER = CONTROLE + CAMPOS


def _df(registros: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(registros, columns=COLUNAS_SILVER).fillna("")


def silver_cartoes(lidos: list[dict]) -> pd.DataFrame:
    """Bronze do cartão -> silver. A data de emissão do cartão é a data de referência."""
    return _df([
        padronizar(extracao.para_canonico(d), "cartao", d["arquivo"], d.get("data_emissao", ""))
        for d in lidos
    ])


# Colunas do ERP -> esquema canônico.
MAPA_ERP = {
    "cnpj_cpf": "cnpj", "razao_social": "razao_social", "nome_fantasia": "nome_fantasia",
    "endereco": "logradouro", "numero": "numero", "bairro": "bairro", "cidade": "municipio",
    "uf": "uf", "cep": "cep", "email": "email", "telefone": "telefone",
}


def silver_erp(caminho: Path) -> pd.DataFrame:
    bruto = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    faltando = (set(MAPA_ERP) | {"cod_cliente", "dt_atualizacao"}) - set(bruto.columns)
    if faltando:
        raise ValueError(f"O arquivo do ERP não tem as colunas: {sorted(faltando)}")
    return _df([
        padronizar({MAPA_ERP[k]: v for k, v in linha.items() if k in MAPA_ERP},
                   "erp", linha["cod_cliente"], linha["dt_atualizacao"])
        for linha in bruto.to_dict("records")
    ])


def silver_receita(cliente: receita.ClienteReceita, cnpjs: list[str],
                   avisar=print) -> tuple[pd.DataFrame, list[dict]]:
    """Consulta cada CNPJ válido. Devolve (silver, consultas_sem_dados)."""
    registros, sem_dados = [], []
    unicos = sorted({c for c in cnpjs if cnpj_valido(c)})
    for n, cnpj in enumerate(unicos, 1):
        if not cliente.offline and n % 10 == 0:
            avisar(f"  Receita: {n}/{len(unicos)}")
        resp = cliente.consultar(cnpj)
        if resp is None:
            sem_dados.append({"cnpj": cnpj, "status": "sem_resposta"})
        elif resp["status"] != 200:
            sem_dados.append({"cnpj": cnpj, "status": f"http_{resp['status']}"})
        else:
            registros.append(padronizar(receita.para_canonico(resp["dados"]), "receita",
                                        cnpj, resp["consultado_em"]))
    return _df(registros), sem_dados
