"""Teste de ponta a ponta com a base sintética: o que o recrutador vai rodar."""
import re
import sqlite3
from pathlib import Path

import pytest

from mdm_cnpj.__main__ import rodar_demo

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def execucao(tmp_path_factory):
    base = tmp_path_factory.mktemp("demo")
    ex = rodar_demo(base / "dados", base / "saida")
    return ex, base / "saida"


def test_numeros_reproduziveis(execucao):
    ex, _ = execucao
    m = ex.metricas
    assert m["registros_origem"] == 194
    assert m["registros_mestres"] == 51
    assert m["fila_revisao"] == 1
    assert m["cnpjs_alfanumericos"] >= 3
    assert m["indice_mestre"] > m["indice_fontes"], "o MDM tem que melhorar a qualidade"


def test_todo_registro_com_cnpj_valido_vira_mestre(execucao):
    ex, _ = execucao
    cross = ex.mdm.crosswalk
    exatos = cross[cross["metodo_match"] == "cnpj_exato"]
    assert (exatos["id_mestre"] != "").all()
    assert set(cross["metodo_match"]) <= {"cnpj_exato", "fuzzy_automatico", "revisao_steward",
                                          "sem_correspondente", "decisao_steward"}


def test_saidas_geradas(execucao):
    _, saida = execucao
    for nome in ("mdm.sqlite", "relatorio_qualidade.html", "RESUMO.md", "cadastro_mestre.csv",
                 "nao_conformidades.csv", "fila_revisao_steward.csv"):
        assert (saida / nome).exists(), nome


def test_consultas_do_steward_rodam(execucao):
    _, saida = execucao
    sql = (RAIZ / "sql" / "consultas_steward.sql").read_text(encoding="utf-8")
    comandos = [c for c in sql.split(";") if re.search(r"\bSELECT\b", c)]
    with sqlite3.connect(saida / "mdm.sqlite") as con:
        for c in comandos:
            con.execute(c).fetchall()
        for (view,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'view'"):
            con.execute(f"SELECT * FROM {view}").fetchall()
    assert len(comandos) >= 7


def test_saidas_compartilhaveis_sem_dado_pessoal(execucao):
    ex, saida = execucao
    publicos = (saida / "RESUMO.md").read_text(encoding="utf-8") + \
        (saida / "relatorio_qualidade.html").read_text(encoding="utf-8")
    assert not re.search(r"\b\d{11}\b(?!\d)", re.sub(r"\d{14}", "", publicos)), "CPF exposto"
    emails = [e for e in ex.silver["email"] if e]
    assert emails and not any(e in publicos for e in emails), "e-mail exposto"
