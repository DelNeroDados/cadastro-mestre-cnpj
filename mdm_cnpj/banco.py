"""Grava as tabelas no SQLite e cria as views de sql/views.sql."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

PASTA_SQL = Path(__file__).resolve().parent.parent / "sql"


def gravar(caminho: Path, tabelas: dict[str, pd.DataFrame]) -> None:
    caminho = Path(caminho)
    if caminho.exists():
        caminho.unlink()  # cada execução é uma foto completa e reproduzível
    with sqlite3.connect(caminho) as con:
        for nome, df in tabelas.items():
            df.to_sql(nome, con, index=False)
        con.executescript((PASTA_SQL / "views.sql").read_text(encoding="utf-8"))
