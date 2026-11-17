"""Gera docs/CATALOGO_DE_REGRAS.md a partir do YAML de regras."""
from __future__ import annotations

from pathlib import Path

from .qualidade import DIMENSOES, carregar_catalogo

TITULOS = {"completude": "Completude", "validade": "Validade", "consistencia": "Consistência",
           "unicidade": "Unicidade", "atualidade": "Atualidade"}


def gerar_catalogo(origem: Path, destino: Path) -> Path:
    cat = carregar_catalogo(origem)
    linhas = [
        "# Catálogo de regras de qualidade",
        "",
        "> Gerado automaticamente de `config/regras_qualidade.yaml` por "
        "`python executar.py catalogo`. Não edite à mão.",
        "",
        f"- **Versão do catálogo:** {cat.versao}",
        f"- **Dono do dado:** {cat.dono_do_dado}",
        f"- **Steward responsável:** {cat.steward}",
        f"- **Pesos por severidade no índice:** "
        + ", ".join(f"{k} = {v}" for k, v in cat.pesos.items()),
        "",
        "| Dimensão | Meta de conformidade |",
        "|---|---|",
        *[f"| {TITULOS[d]} | {cat.metas[d]}% |" for d in DIMENSOES],
    ]
    for dim in DIMENSOES:
        regras = [r for r in cat.regras if r.dimensao == dim]
        if not regras:
            continue
        linhas += ["", f"## {TITULOS[dim]}", "",
                   "| ID | Regra | Severidade | Fontes | Ação recomendada |", "|---|---|---|---|---|"]
        for r in regras:
            nome = r.nome + (f"<br><sub>{r.descricao.strip()}</sub>" if r.descricao else "")
            if r.no_score:
                nome += "<br><sub>Alerta de negócio: não entra no índice de qualidade.</sub>"
            linhas.append(f"| {r.id} | {nome} | {r.severidade} | "
                          f"{', '.join(r.fontes) if r.fontes else 'todas'} | {r.acao} |")
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino
