"""Orquestra as etapas: fontes -> qualidade -> MDM -> qualidade do mestre ->
reconciliação -> saídas.

A qualidade roda antes do MDM porque a nota de cada registro é usada no
desempate da sobrevivência."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from . import banco, mdm, qualidade, reconciliacao, relatorio
from .fontes import COLUNAS_SILVER
from .relatorio import SITUACOES_RISCO

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config"


@dataclass
class Execucao:
    silver: pd.DataFrame
    dq: qualidade.ResultadoQualidade
    dq_mestre: qualidade.ResultadoQualidade
    mdm: mdm.ResultadoMDM
    acuracia: pd.DataFrame
    divergencias: pd.DataFrame
    rejeitados: pd.DataFrame
    receita_sem_dados: pd.DataFrame
    catalogo: qualidade.Catalogo
    hoje: date
    modo: str
    metricas: dict = field(default_factory=dict)


def executar(silver: pd.DataFrame, rejeitados: list[dict], receita_sem_dados: list[dict],
             pasta_saida: Path, hoje: date, modo: str) -> Execucao:
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    catalogo = qualidade.carregar_catalogo(CONFIG / "regras_qualidade.yaml")
    cfg_mdm = mdm.carregar_config(CONFIG / "sobrevivencia.yaml")

    # 1. Qualidade das fontes
    dq = qualidade.avaliar(silver, catalogo, hoje)
    silver = silver.assign(score_registro=qualidade.score_por_registro(silver, dq.nao_conformidades,
                                                                       catalogo))

    # 2. MDM, incorporando decisões do Steward, se houver
    arq_decisoes = pasta_saida / "decisoes_steward.csv"
    decisoes = ler_csv_excel(arq_decisoes) if arq_decisoes.exists() else None
    res_mdm = mdm.executar(silver, cfg_mdm, decisoes)

    # 3. Qualidade do cadastro mestre (as mesmas regras, agora sobre o golden)
    golden = res_mdm.golden
    mestre = golden.assign(fonte="mestre", id_origem=golden["id_mestre"],
                           data_referencia=golden["data_ultima_evidencia"])[COLUNAS_SILVER]
    dq_mestre = qualidade.avaliar(mestre, catalogo, hoje)

    # 4. Acurácia contra a Receita
    acuracia, divergencias = reconciliacao.reconciliar(silver)

    ex = Execucao(silver, dq, dq_mestre, res_mdm, acuracia, divergencias,
                  pd.DataFrame(rejeitados, columns=["arquivo", "sha256", "motivo"]),
                  pd.DataFrame(receita_sem_dados, columns=["cnpj", "status"]),
                  catalogo, hoje, modo)
    ex.metricas = metricas(ex)

    # 5. Saídas
    banco.gravar(pasta_saida / "mdm.sqlite", {
        "silver_registros": silver,
        "dq_resultados": dq.resultados, "dq_nao_conformidades": dq.nao_conformidades,
        "dq_scorecard": dq.scorecard, "dq_resultados_mestre": dq_mestre.resultados,
        "mdm_crosswalk": res_mdm.crosswalk, "mdm_golden": golden,
        "mdm_linhagem": res_mdm.linhagem, "mdm_hierarquia": res_mdm.hierarquia,
        "mdm_fila_revisao": res_mdm.fila_revisao,
        "rec_acuracia": acuracia, "rec_divergencias": divergencias,
        "doc_rejeitados": ex.rejeitados, "receita_sem_dados": ex.receita_sem_dados,
    })
    csv = {"sep": ";", "index": False, "encoding": "utf-8-sig"}
    golden.to_csv(pasta_saida / "cadastro_mestre.csv", **csv)
    dq.nao_conformidades.to_csv(pasta_saida / "nao_conformidades.csv", **csv)
    res_mdm.fila_revisao.to_csv(pasta_saida / "fila_revisao_steward.csv", **csv)
    relatorio.gerar(ex, pasta_saida)
    return ex


def ler_csv_excel(caminho: Path) -> pd.DataFrame:
    """CSV editado no Excel: pode voltar em UTF-8 (com BOM) ou em ANSI (Windows-1252)."""
    import io

    bruto = Path(caminho).read_bytes()
    try:  # decodificação estrita: o pandas trocaria acentos inválidos por "�" sem avisar
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("cp1252")
    return pd.read_csv(io.StringIO(texto), sep=";", dtype=str).fillna("")


def metricas(ex: Execucao) -> dict:
    cross = ex.mdm.crosswalk
    vinculados = cross[cross["id_mestre"] != ""]
    golden = ex.mdm.golden
    return {
        "registros_origem": len(ex.silver),
        "por_fonte": ex.silver["fonte"].value_counts().sort_index().to_dict(),
        "documentos_rejeitados": len(ex.rejeitados),
        "registros_mestres": len(golden),
        "taxa_redundancia": round(1 - len(golden) / len(vinculados), 3) if len(vinculados) else 0,
        "match": cross["metodo_match"].value_counts().to_dict(),
        "fila_revisao": len(ex.mdm.fila_revisao),
        "indice_fontes": ex.dq.indice_geral,
        "indice_por_fonte": ex.dq.indice_por_fonte,
        "indice_mestre": ex.dq_mestre.indice_geral,
        "nao_conformidades": len(ex.dq.nao_conformidades),
        "nao_conformidades_criticas": int((ex.dq.nao_conformidades["severidade"] == "critica").sum()),
        "mestres_validados_receita": int((golden["status_mestre"] == "VALIDADO_RECEITA").sum()),
        "clientes_em_risco": int(golden["situacao_cadastral"].isin(SITUACOES_RISCO).sum()),
        "empresas": int(ex.mdm.hierarquia.shape[0]),
        "cnpjs_alfanumericos": int(golden["cnpj"].str.contains("[A-Z]", regex=True).sum()),
        "cartoes_desatualizados_situacao": int((ex.divergencias["motivo_provavel"] != "").sum()),
    }
