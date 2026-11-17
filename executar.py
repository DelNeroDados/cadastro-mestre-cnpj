"""Ponto de entrada: python executar.py demo | real --pdfs PASTA | catalogo

Equivale a `python -m mdm_cnpj`, mas também funciona no Python portátil
(embeddable), que não coloca a pasta do script no sys.path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mdm_cnpj.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
