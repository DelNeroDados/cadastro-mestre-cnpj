"""Gera o relatório HTML e o RESUMO.md, com os dados pessoais mascarados."""
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
from jinja2 import Environment

from . import lgpd
from .validadores import formatar_cnpj

SITUACOES_RISCO = ["BAIXADA", "INAPTA", "SUSPENSA", "NULA"]

NOMES_DIMENSAO = {
    "completude": "Completude", "validade": "Validade", "consistencia": "Consistência",
    "unicidade": "Unicidade", "atualidade": "Atualidade",
}
NOMES_FONTE = {"receita": "Receita Federal", "cartao": "Cartões CNPJ", "erp": "ERP",
               "mestre": "Cadastro mestre", "TODAS": "Todas as fontes"}
NOMES_MATCH = {
    "cnpj_exato": "CNPJ idêntico (determinístico)", "fuzzy_automatico": "Similaridade alta (automático)",
    "decisao_steward": "Decisão do Steward", "revisao_steward": "Aguardando o Steward",
    "sem_correspondente": "Quarentena (sem correspondente)",
}


def _barras(itens: list[dict]) -> list[dict]:
    """Prepara barras horizontais: rótulo, valor (0-100), meta e status."""
    return [{**i, "largura": max(0.0, min(100.0, i["valor"]))} for i in itens]


def contexto(ex) -> dict:
    m = ex.metricas
    sc = ex.dq.scorecard
    todas = sc[sc["fonte"] == "TODAS"].set_index("dimensao")
    dimensoes = _barras([
        {"rotulo": NOMES_DIMENSAO[d], "valor": float(todas.loc[d, "conformidade"]),
         "meta": float(todas.loc[d, "meta"]), "ok": bool(todas.loc[d, "atingiu_meta"]),
         "detalhe": f"{int(todas.loc[d, 'conformes'])} de {int(todas.loc[d, 'avaliados'])} verificações"}
        for d in NOMES_DIMENSAO if d in todas.index
    ])
    fontes = _barras(
        [{"rotulo": NOMES_FONTE[f], "valor": v, "meta": None, "ok": True,
          "detalhe": f"índice ponderado por severidade"} for f, v in sorted(m["indice_por_fonte"].items())]
        + [{"rotulo": NOMES_FONTE["mestre"], "valor": m["indice_mestre"], "meta": None, "ok": True,
            "detalhe": "as mesmas regras aplicadas ao golden record", "destaque": True}]
    )

    # Matriz dimensão x fonte para a tabela do scorecard.
    piv = sc[sc["fonte"] != "TODAS"].pivot(index="dimensao", columns="fonte", values="conformidade")
    metas = ex.catalogo.metas
    matriz = [{"dimensao": NOMES_DIMENSAO[d], "meta": metas[d],
               "celulas": [{"v": (None if pd.isna(piv.loc[d, f]) else float(piv.loc[d, f])),
                            "ok": (not pd.isna(piv.loc[d, f])) and piv.loc[d, f] >= metas[d]}
                           for f in piv.columns]}
              for d in NOMES_DIMENSAO if d in piv.index]

    res = ex.dq.resultados
    regras = (res[res["falhas"] > 0].sort_values(["severidade", "falhas"], ascending=[True, False],
                                                 key=lambda s: s.map({"critica": 0, "alta": 1, "media": 2, "baixa": 3})
                                                 if s.name == "severidade" else s))
    catalogo = {r.id: r for r in ex.catalogo.regras}

    nc = lgpd.mascarar_df(ex.dq.nao_conformidades)
    exemplos = (nc[nc["severidade"].isin(["critica", "alta"])]
                .drop_duplicates("regra_id").head(8))

    acur = ex.acuracia.pivot(index="campo", columns="fonte", values="acuracia")
    acuracia = [{"campo": c, "valores": [None if pd.isna(acur.loc[c, f]) else float(acur.loc[c, f])
                                         for f in acur.columns]} for c in acur.index]

    cross = ex.mdm.crosswalk
    match = (cross.groupby("metodo_match").size().reindex(NOMES_MATCH).dropna().astype(int))
    fila = lgpd.mascarar_df(ex.mdm.fila_revisao)
    quarentena = lgpd.mascarar_df(
        cross[cross["metodo_match"] == "sem_correspondente"]
        .merge(ex.silver[["fonte", "id_origem", "razao_social"]], on=["fonte", "id_origem"]))
    risco = lgpd.mascarar_df(ex.mdm.golden[ex.mdm.golden["situacao_cadastral"].isin(SITUACOES_RISCO)]
                             [["cnpj", "razao_social", "natureza_juridica", "situacao_cadastral",
                               "data_situacao_cadastral"]])
    conflitos = (ex.mdm.linhagem.assign(conf=ex.mdm.linhagem["valores_distintos"] > 1)
                 .groupby("campo")["conf"].mean().mul(100).round(1).sort_values(ascending=False).head(6))

    return {
        "m": m, "modo": ex.modo, "hoje": ex.hoje.strftime("%d/%m/%Y"),
        "dimensoes": dimensoes, "fontes": fontes, "matriz": matriz,
        "colunas_matriz": [NOMES_FONTE[f] for f in piv.columns],
        "regras": [{"id": r.regra_id, "nome": r.regra, "dim": NOMES_DIMENSAO[r.dimensao],
                    "sev": r.severidade, "fonte": NOMES_FONTE[r.fonte], "falhas": int(r.falhas),
                    "aval": int(r.avaliados), "taxa": r.taxa_conformidade,
                    "no_score": bool(r.no_score), "acao": catalogo[r.regra_id].acao}
                   for r in regras.itertuples()],
        "exemplos": exemplos.to_dict("records"),
        "acuracia": acuracia, "colunas_acuracia": [NOMES_FONTE[f] for f in acur.columns],
        "match": [(NOMES_MATCH[k], int(v)) for k, v in match.items()],
        "fila": fila.to_dict("records"), "quarentena": quarentena.to_dict("records"),
        "risco": risco.to_dict("records"), "conflitos": list(conflitos.items()),
        "rejeitados": ex.rejeitados["motivo"].value_counts().to_dict(),
        "versao_catalogo": ex.catalogo.versao, "n_regras": len(ex.catalogo.regras),
        "fmt_cnpj": formatar_cnpj, "fonte_nome": lambda f: NOMES_FONTE.get(f, f),
    }


def gerar(ex, pasta: Path) -> None:
    ctx = contexto(ex)
    env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    (Path(pasta) / "relatorio_qualidade.html").write_text(
        env.from_string(MODELO_HTML).render(**ctx), encoding="utf-8")
    (Path(pasta) / "RESUMO.md").write_text(resumo_md(ctx), encoding="utf-8")


def _md_tabela(cabecalho: list[str], linhas: list[list]) -> str:
    def cel(v):
        return "-" if v is None else str(v).replace("|", "\\|")
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    saida += ["| " + " | ".join(cel(v) for v in l) + " |" for l in linhas]
    return "\n".join(saida)


def resumo_md(ctx: dict) -> str:
    m = ctx["m"]
    origem = ", ".join(f"{ctx['fonte_nome'](k)}: {v}" for k, v in m["por_fonte"].items())
    partes = [
        f"# Resumo da execução ({'demonstração sintética' if ctx['modo'] == 'demo' else 'dados reais'})",
        f"Data de referência: {ctx['hoje']} · catálogo de regras v{ctx['versao_catalogo']} "
        f"({ctx['n_regras']} regras). Arquivo gerado automaticamente por `executar.py`.",
        "## Números principais",
        _md_tabela(["Indicador", "Valor"], [
            ["Registros de origem", f"{m['registros_origem']} ({origem})"],
            ["Registros no cadastro mestre", f"{m['registros_mestres']} estabelecimentos de {m['empresas']} empresas"],
            ["Redundância eliminada pelo MDM", f"{100 * m['taxa_redundancia']:.1f}%"],
            ["Índice de qualidade: fontes → mestre", f"{m['indice_fontes']} → {m['indice_mestre']}"],
            ["Não conformidades registradas", f"{m['nao_conformidades']} ({m['nao_conformidades_criticas']} críticas)"],
            ["Pares na fila de revisão do Steward", m["fila_revisao"]],
            ["Clientes com CNPJ não ativo", m["clientes_em_risco"]],
            ["CNPJs alfanuméricos (novo formato de 2026)", m["cnpjs_alfanumericos"]],
        ]),
        "## Scorecard por dimensão (todas as fontes)",
        _md_tabela(["Dimensão", "Conformidade", "Meta", "Status"], [
            [d["rotulo"], f"{d['valor']:.1f}%", f"{d['meta']:.0f}%",
             "✅ atingiu" if d["ok"] else "⚠️ abaixo da meta"] for d in ctx["dimensoes"]]),
        "## Regras com falhas",
        _md_tabela(["Regra", "Severidade", "Fonte", "Falhas", "Conformidade", "Ação recomendada"], [
            [f"{r['id']} {r['nome']}" + (" *(alerta, fora do índice)*" if r["no_score"] else ""),
             r["sev"], r["fonte"], f"{r['falhas']}/{r['aval']}", f"{r['taxa']:.1f}%", r["acao"]]
            for r in ctx["regras"]]),
        "## Acurácia contra a Receita (% de valores iguais)",
        _md_tabela(["Campo", *ctx["colunas_acuracia"]], [
            [a["campo"], *[None if v is None else f"{v:.1f}%" for v in a["valores"]]]
            for a in ctx["acuracia"]]),
        "## Como os registros foram casados",
        _md_tabela(["Método", "Registros"], [list(x) for x in ctx["match"]]),
    ]
    if ctx["fila"]:
        partes += ["## Fila de revisão do Steward", _md_tabela(
            ["Origem", "Nome na origem", "Sugestão", "Score"],
            [[f"{f['fonte']} {f['id_origem']}", f["razao_social_origem"],
              f"{f['razao_social_sugerida']} ({ctx['fmt_cnpj'](f['cnpj_sugerido'])})", f["score"]]
             for f in ctx["fila"]])]
    partes.append("\n*Dados pessoais (nome e CPF de empresário individual, e-mail, telefone) "
                  "mascarados conforme a política de LGPD do projeto.*\n")
    return "\n\n".join(partes)


MODELO_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qualidade do Cadastro</title>
<style>
:root {
  color-scheme: light;
  --surface-0: #f5f4f1; --surface-1: #fcfcfb; --border: #e3e2de; --grid: #ecebe7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #6f6e69;
  --series-1: #2a78d6; --series-1-soft: #cde2fb; --meta: #0b0b0b;
  --good: #0ca30c; --good-text: #006300; --warning: #fab219; --warning-text: #8a5a00;
  --critical: #d03b3b; --critical-text: #b02a2a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0: #121211; --surface-1: #1a1a19; --border: #2f2f2c; --grid: #262624;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9a998f;
    --series-1: #3987e5; --series-1-soft: #184f95; --meta: #f0efec;
    --good-text: #4cc94c; --warning-text: #fab219; --critical-text: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #121211; --surface-1: #1a1a19; --border: #2f2f2c; --grid: #262624;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9a998f;
  --series-1: #3987e5; --series-1-soft: #184f95; --meta: #f0efec;
  --good-text: #4cc94c; --warning-text: #fab219; --critical-text: #e66767;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface-0); color: var(--text-primary);
       font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 32px 16px 64px; }
header p { color: var(--text-secondary); margin: 4px 0 0; }
h1 { font-size: 28px; margin: 0; letter-spacing: -0.01em; }
h2 { font-size: 19px; margin: 0 0 4px; }
.sub { color: var(--text-secondary); margin: 0 0 16px; font-size: 14px; }
section { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
          padding: 20px; margin-top: 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px;
         margin-top: 24px; }
.tile { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }
.tile .k { color: var(--text-secondary); font-size: 13px; }
.tile .v { white-space: nowrap; font-size: 24px; font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.2; margin-top: 4px; }
.tile .d { color: var(--text-muted); font-size: 12.5px; margin-top: 2px; }
.bars { display: grid; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 150px 1fr 150px; align-items: center; gap: 12px; }
.bar-label { font-size: 14px; }
.track { position: relative; height: 22px; border-radius: 4px;
         background: repeating-linear-gradient(90deg, transparent 0 calc(10% - 1px), var(--grid) calc(10% - 1px) 10%); }
.fill { position: absolute; left: 0; top: 3px; bottom: 3px; background: var(--series-1); border-radius: 0 4px 4px 0; }
.fill.destaque { background: var(--text-primary); }
.goal { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--meta); }
.bar-val { font-variant-numeric: tabular-nums; font-size: 14px; }
.status { font-size: 12.5px; white-space: nowrap; }
.status.ok { color: var(--good-text); } .status.ko { color: var(--warning-text); }
.status.ko::before { content: "▲ "; } .status.ok::before { content: "● "; }
.hit { cursor: default; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.tbl-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--text-secondary); font-weight: 600; font-size: 12.5px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 99px; font-size: 12px; border: 1px solid var(--border); }
.sev-critica { color: var(--critical-text); border-color: currentColor; }
.sev-alta { color: var(--warning-text); border-color: currentColor; }
.sev-media, .sev-baixa { color: var(--text-secondary); }
.cell-ok { color: var(--good-text); } .cell-ko { color: var(--warning-text); font-weight: 600; }
.cell-ko::before { content: "▲ "; font-size: 10px; }
.muted { color: var(--text-muted); }
.nota { font-size: 12.5px; color: var(--text-muted); margin-top: 10px; }
#tip { position: fixed; pointer-events: none; background: var(--text-primary); color: var(--surface-1);
       padding: 6px 10px; border-radius: 6px; font-size: 12.5px; opacity: 0; transition: opacity .1s; max-width: 280px; z-index: 9; }
footer { margin-top: 28px; color: var(--text-muted); font-size: 12.5px; }
@media (max-width: 760px) {
  .grid2 { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 1fr; gap: 4px; }
  main { padding: 20px 16px 48px; }
  h1 { font-size: 23px; }
}
</style>
</head>
<body>
<main>
<header>
  <h1>Qualidade e cadastro mestre de empresas</h1>
  <p>{{ "Demonstração com base 100% sintética" if modo == "demo" else "Execução com dados reais" }}
     · referência {{ hoje }} · catálogo de regras v{{ versao_catalogo }} ({{ n_regras }} regras)</p>
</header>

<div class="tiles">
  <div class="tile"><div class="k">Registros de origem</div><div class="v">{{ m.registros_origem }}</div>
    <div class="d">{% for f, n in m.por_fonte.items() %}{{ fonte_nome(f) }} {{ n }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
  <div class="tile"><div class="k">Cadastro mestre</div><div class="v">{{ m.registros_mestres }}</div>
    <div class="d">estabelecimentos de {{ m.empresas }} empresas</div></div>
  <div class="tile"><div class="k">Redundância eliminada</div><div class="v">{{ "%.1f"|format(100 * m.taxa_redundancia) }}%</div>
    <div class="d">registros que eram a mesma empresa</div></div>
  <div class="tile"><div class="k">Índice de qualidade</div><div class="v">{{ "%.1f"|format(m.indice_fontes) }} → {{ "%.1f"|format(m.indice_mestre) }}</div>
    <div class="d">fontes → cadastro mestre</div></div>
  <div class="tile"><div class="k">Não conformidades</div><div class="v">{{ m.nao_conformidades }}</div>
    <div class="d">{{ m.nao_conformidades_criticas }} críticas · {{ m.fila_revisao }} na fila do Steward</div></div>
  <div class="tile"><div class="k">Clientes em risco</div><div class="v">{{ m.clientes_em_risco }}</div>
    <div class="d">CNPJ baixado, inapto ou suspenso</div></div>
</div>

<section>
  <h2>Conformidade por dimensão de qualidade</h2>
  <p class="sub">Todas as fontes juntas. A marca vertical em cada barra é a meta acordada no catálogo de regras.</p>
  <div class="bars">
  {% for b in dimensoes %}
    <div class="bar-row hit" data-tip="{{ b.rotulo }}: {{ '%.1f'|format(b.valor) }}% ({{ b.detalhe }}) · meta {{ '%.0f'|format(b.meta) }}%">
      <div class="bar-label">{{ b.rotulo }}</div>
      <div class="track"><div class="fill" style="width: {{ b.largura }}%"></div>
        <div class="goal" style="left: calc({{ b.meta }}% - 1px)"></div></div>
      <div><span class="bar-val">{{ "%.1f"|format(b.valor) }}%</span>
        <span class="status {{ 'ok' if b.ok else 'ko' }}">{{ "atingiu" if b.ok else "abaixo da meta" }}</span></div>
    </div>
  {% endfor %}
  </div>
  <div class="tbl-wrap" style="margin-top:18px">
  <table>
    <thead><tr><th>Dimensão</th>{% for c in colunas_matriz %}<th class="n">{{ c }}</th>{% endfor %}<th class="n">Meta</th></tr></thead>
    <tbody>
    {% for l in matriz %}<tr><td>{{ l.dimensao }}</td>
      {% for c in l.celulas %}<td class="n">{% if c.v is none %}<span class="muted">n/a</span>{% else %}<span class="{{ 'cell-ok' if c.ok else 'cell-ko' }}">{{ "%.1f"|format(c.v) }}%</span>{% endif %}</td>{% endfor %}
      <td class="n muted">{{ l.meta }}%</td></tr>{% endfor %}
    </tbody>
  </table>
  </div>
  <p class="nota">n/a: a regra não se aplica à fonte (ex.: atualidade não é medida na Receita, consultada no momento da carga).</p>
</section>

<section>
  <h2>Índice de qualidade por fonte, antes e depois do MDM</h2>
  <p class="sub">Média das regras ponderada pela severidade (crítica 8, alta 4, média 2, baixa 1). A última barra aplica as mesmas regras ao cadastro mestre.</p>
  <div class="bars">
  {% for b in fontes %}
    <div class="bar-row hit" data-tip="{{ b.rotulo }}: {{ '%.2f'|format(b.valor) }} ({{ b.detalhe }})">
      <div class="bar-label">{{ b.rotulo }}</div>
      <div class="track"><div class="fill{{ ' destaque' if b.destaque }}" style="width: {{ b.largura }}%"></div></div>
      <div class="bar-val">{{ "%.2f"|format(b.valor) }}</div>
    </div>
  {% endfor %}
  </div>
</section>

<section>
  <h2>Regras com falhas</h2>
  <p class="sub">Cada regra tem dimensão, severidade e uma ação recomendada para o responsável.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Regra</th><th>Severidade</th><th>Fonte</th><th class="n">Falhas</th><th class="n">Conformidade</th><th>Ação recomendada</th></tr></thead>
    <tbody>{% for r in regras %}
      <tr><td><b>{{ r.id }}</b> {{ r.nome }}{% if r.no_score %} <span class="muted">(alerta de negócio, fora do índice)</span>{% endif %}</td>
        <td><span class="pill sev-{{ r.sev }}">{{ r.sev }}</span></td><td>{{ r.fonte }}</td>
        <td class="n">{{ r.falhas }}/{{ r.aval }}</td><td class="n">{{ "%.1f"|format(r.taxa) }}%</td><td class="muted">{{ r.acao }}</td></tr>{% endfor %}
    </tbody></table></div>
  {% if exemplos %}
  <h2 style="margin-top:20px">Exemplos de não conformidades graves</h2>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Regra</th><th>Fonte</th><th>Registro</th><th>Valor encontrado</th></tr></thead>
    <tbody>{% for e in exemplos %}<tr><td>{{ e.regra_id }}</td><td>{{ fonte_nome(e.fonte) }}</td><td>{{ e.id_origem }}</td><td>{{ e.valor_encontrado or "(vazio)" }}</td></tr>{% endfor %}</tbody>
  </table></div>
  {% endif %}
</section>

<div class="grid2">
<section style="margin-top:20px">
  <h2>Como os registros foram casados</h2>
  <p class="sub">Match determinístico pelo CNPJ; os demais, por similaridade de nome, CNPJ e CEP.</p>
  <table><tbody>{% for nome, n in match %}<tr><td>{{ nome }}</td><td class="n">{{ n }}</td></tr>{% endfor %}</tbody></table>
  <h2 style="margin-top:18px">Campos em que as fontes mais discordam</h2>
  <p class="sub">% dos registros mestres com mais de um valor válido concorrendo.</p>
  <table><tbody>{% for c, p in conflitos %}<tr><td>{{ c }}</td><td class="n">{{ p }}%</td></tr>{% endfor %}</tbody></table>
</section>
<section style="margin-top:20px">
  <h2>Acurácia contra a Receita</h2>
  <p class="sub">% de valores idênticos ao da fonte autoritativa, campo a campo.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Campo</th>{% for c in colunas_acuracia %}<th class="n">{{ c }}</th>{% endfor %}</tr></thead>
    <tbody>{% for a in acuracia %}<tr><td>{{ a.campo }}</td>{% for v in a.valores %}<td class="n">{% if v is none %}<span class="muted">-</span>{% else %}<span class="{{ 'cell-ok' if v >= 95 else 'cell-ko' }}">{{ "%.1f"|format(v) }}%</span>{% endif %}</td>{% endfor %}</tr>{% endfor %}</tbody>
  </table></div>
  <p class="nota">▲ abaixo de 95%. Nos cartões, parte das divergências é documento antigo, não erro: {{ m.cartoes_desatualizados_situacao }} cartões mostram situação que mudou depois da emissão.</p>
</section>
</div>

<section>
  <h2>Fila do Data Steward</h2>
  <p class="sub">Casos que a máquina não decide sozinha. A decisão (UNIR ou SEPARAR) é registrada em <code>decisoes_steward.csv</code> e aplicada na próxima execução.</p>
  {% if fila %}<div class="tbl-wrap"><table>
    <thead><tr><th>Origem</th><th>Nome na origem</th><th>Sugestão do MDM</th><th class="n">Score</th></tr></thead>
    <tbody>{% for f in fila %}<tr><td>{{ fonte_nome(f.fonte) }} {{ f.id_origem }}<br><span class="muted">{{ f.cnpj_origem or "(sem CNPJ)" }}</span></td>
      <td>{{ f.razao_social_origem }}</td><td>{{ f.razao_social_sugerida }}<br><span class="muted">{{ fmt_cnpj(f.cnpj_sugerido) }}</span></td><td class="n">{{ f.score }}</td></tr>{% endfor %}</tbody>
  </table></div>{% else %}<p class="muted">Nenhum par aguardando revisão.</p>{% endif %}
  {% if quarentena %}<h2 style="margin-top:18px">Quarentena</h2>
  <p class="sub">Sem CNPJ válido e sem correspondente: não entram no cadastro mestre até serem tratados.</p>
  <table><tbody>{% for q in quarentena %}<tr><td>{{ fonte_nome(q.fonte) }} {{ q.id_origem }}</td><td>{{ q.razao_social }}</td><td class="muted">{{ q.cnpj_origem or "(sem CNPJ)" }}</td><td class="n">melhor score {{ q.score_match }}</td></tr>{% endfor %}</tbody></table>{% endif %}
</section>

{% if risco %}
<section>
  <h2>Clientes com CNPJ não ativo</h2>
  <p class="sub">Alerta de negócio (regra DQ010): não devem receber nota fiscal até a situação ser regularizada.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>CNPJ</th><th>Razão social</th><th>Situação</th><th>Desde</th></tr></thead>
    <tbody>{% for r in risco %}<tr><td>{{ fmt_cnpj(r.cnpj) }}</td><td>{{ r.razao_social }}</td><td>{{ r.situacao_cadastral }}</td><td>{{ r.data_situacao_cadastral }}</td></tr>{% endfor %}</tbody>
  </table></div>
</section>
{% endif %}

{% if rejeitados %}
<section>
  <h2>Documentos que não puderam ser lidos</h2>
  <p class="sub">Nenhum arquivo é movido ou apagado; cada rejeição fica registrada com o motivo.</p>
  <table><tbody>{% for motivo, n in rejeitados.items() %}<tr><td>{{ motivo }}</td><td class="n">{{ n }}</td></tr>{% endfor %}</tbody></table>
</section>
{% endif %}

<footer>Dados pessoais (nome e CPF de empresário individual, e-mail e telefone) mascarados conforme a política de LGPD do projeto.
Gerado automaticamente por <code>executar.py</code>.</footer>
</main>
<div id="tip" role="tooltip"></div>
<script>
(function () {
  var tip = document.getElementById("tip");
  document.querySelectorAll("[data-tip]").forEach(function (el) {
    el.addEventListener("mousemove", function (e) {
      tip.textContent = el.getAttribute("data-tip");
      tip.style.opacity = 1;
      var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = x + "px"; tip.style.top = (e.clientY + 14) + "px";
    });
    el.addEventListener("mouseleave", function () { tip.style.opacity = 0; });
  });
})();
</script>
</body>
</html>
"""
