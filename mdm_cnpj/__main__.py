"""Linha de comando.

  python -m mdm_cnpj demo                      base sintética, sem rede (para recrutadores)
  python -m mdm_cnpj real --pdfs PASTA [...]   cartões reais + Receita (+ ERP opcional)
  python -m mdm_cnpj catalogo                  regenera docs/CATALOGO_DE_REGRAS.md do YAML
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from . import demo, extracao, fontes, pipeline
from .receita import ClienteReceita

RAIZ = pipeline.RAIZ


def _resumo(ex: pipeline.Execucao, pasta: Path) -> None:
    m = ex.metricas
    print()
    print("=" * 64)
    print(f" Registros de origem ......... {m['registros_origem']}  {m['por_fonte']}")
    print(f" Cadastro mestre ............. {m['registros_mestres']} estabelecimentos "
          f"({m['empresas']} empresas)")
    print(f" Redundância eliminada ....... {100 * m['taxa_redundancia']:.1f}%")
    print(f" Índice de qualidade ......... fontes {m['indice_fontes']} -> mestre {m['indice_mestre']}")
    print(f" Não conformidades ........... {m['nao_conformidades']} "
          f"({m['nao_conformidades_criticas']} críticas)")
    print(f" Fila de revisão do Steward .. {m['fila_revisao']} pares")
    print(f" Clientes em risco ........... {m['clientes_em_risco']} (CNPJ não ativo)")
    print("=" * 64)
    print(f" Saídas em: {pasta}")
    print("   relatorio_qualidade.html  RESUMO.md  mdm.sqlite  cadastro_mestre.csv")
    print("   nao_conformidades.csv     fila_revisao_steward.csv")


def rodar_demo(pasta_dados: Path, pasta_saida: Path) -> pipeline.Execucao:
    """Gera a base sintética e roda o pipeline inteiro, sem rede."""
    demo.gerar(pasta_dados)
    lidos = json.loads((pasta_dados / "cartoes_extraidos.json").read_text(encoding="utf-8"))
    silver_c = fontes.silver_cartoes(lidos)
    silver_e = fontes.silver_erp(pasta_dados / "clientes_erp.csv")
    cliente = ClienteReceita(pasta_dados / "receita", offline=True)
    silver_r, sem = fontes.silver_receita(cliente, list(silver_c["cnpj"]) + list(silver_e["cnpj"]))
    silver = pd.concat([silver_r, silver_c, silver_e], ignore_index=True)
    return pipeline.executar(silver, [], sem, pasta_saida, demo.DATA_DEMO, "demo")


def cmd_demo(args) -> None:
    print("Gerando a base sintética e rodando o pipeline...")
    saida = RAIZ / "saida_demo"
    _resumo(rodar_demo(RAIZ / "dados_demo", saida), saida)


def cmd_real(args) -> None:
    lidos, rejeitados = [], []
    for pasta in args.pdfs:
        print(f"Lendo cartões em {pasta} ...")
        l, r = extracao.extrair_pasta(Path(pasta), RAIZ / ".cache" / "extracao", avisar=print)
        lidos += l
        rejeitados += r
    silver_c = fontes.silver_cartoes(lidos)
    partes = [silver_c]
    if args.erp:
        partes.append(fontes.silver_erp(Path(args.erp)))
    cnpjs = [c for p in partes for c in p["cnpj"]]
    print("Consultando a Receita (BrasilAPI, OpenCNPJ)" + (" em modo offline" if args.offline else "") + "...")
    cliente = ClienteReceita(RAIZ / ".cache" / "receita", offline=args.offline)
    silver_r, sem = fontes.silver_receita(cliente, cnpjs)
    silver = pd.concat([silver_r, *partes], ignore_index=True)
    saida = RAIZ / "saida_real"
    ex = pipeline.executar(silver, rejeitados, sem, saida, date.today(), "real")
    _resumo(ex, saida)


def cmd_catalogo(args) -> None:
    from .documentacao import gerar_catalogo
    destino = gerar_catalogo(RAIZ / "config" / "regras_qualidade.yaml",
                             RAIZ / "docs" / "CATALOGO_DE_REGRAS.md")
    print(f"Catálogo gerado em {destino}")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console do Windows em cp1252
    ap = argparse.ArgumentParser(prog="mdm_cnpj", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("demo", help="roda com a base sintética").set_defaults(func=cmd_demo)
    real = sub.add_parser("real", help="roda com cartões CNPJ reais")
    real.add_argument("--pdfs", nargs="+", required=True, help="pastas com os PDFs")
    real.add_argument("--erp", help="CSV de clientes do ERP (opcional)")
    real.add_argument("--offline", action="store_true", help="usa só o cache da Receita")
    real.set_defaults(func=cmd_real)
    sub.add_parser("catalogo", help="gera o catálogo de regras em Markdown").set_defaults(
        func=cmd_catalogo)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
