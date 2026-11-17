from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from mdm_cnpj import lgpd, mdm, qualidade
from mdm_cnpj.fontes import COLUNAS_SILVER
from mdm_cnpj.padronizacao import padronizar
from mdm_cnpj.validadores import completar_dv

RAIZ = Path(__file__).resolve().parent.parent
HOJE = date(2026, 11, 1)
CNPJ_A = completar_dv("112223330001")
CNPJ_A_FILIAL = completar_dv("112223330002")
CNPJ_B = completar_dv("445556660001")


def reg(fonte, id_origem, data_ref="2026-10-01", **campos):
    base = {"razao_social": "ALFA PLASTICOS LTDA", "cep": "17209832", "uf": "SP", "municipio": "JAU",
            "situacao_cadastral": "ATIVA", "tipo_estabelecimento": "MATRIZ"}
    return padronizar({**base, **campos}, fonte, id_origem, data_ref)


def silver(*registros):
    return pd.DataFrame(list(registros), columns=COLUNAS_SILVER).fillna("")


@pytest.fixture(scope="module")
def catalogo():
    return qualidade.carregar_catalogo(RAIZ / "config" / "regras_qualidade.yaml")


@pytest.fixture(scope="module")
def cfg():
    return mdm.carregar_config(RAIZ / "config" / "sobrevivencia.yaml")


# ---------------------------------------------------------------- qualidade
def test_catalogo_valido(catalogo):
    assert len(catalogo.regras) >= 20
    assert set(catalogo.metas) == set(qualidade.DIMENSOES)
    assert all(r.acao for r in catalogo.regras), "toda regra precisa de ação recomendada"


def test_catalogo_rejeita_id_repetido(tmp_path):
    (tmp_path / "c.yaml").write_text(
        "metas: {}\npesos_severidade: {}\nregras:\n"
        "  - {id: X1, nome: a, dimensao: validade, tipo: obrigatorio, campo: cnpj, severidade: alta}\n"
        "  - {id: X1, nome: b, dimensao: validade, tipo: obrigatorio, campo: cnpj, severidade: alta}\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="repetido"):
        qualidade.carregar_catalogo(tmp_path / "c.yaml")


def test_regras_apontam_cada_defeito(catalogo):
    df = silver(
        reg("erp", "1", cnpj=CNPJ_A, email="ok@alfa.com.br"),
        reg("erp", "2", cnpj=CNPJ_A),                                  # duplicado do 1
        reg("erp", "3", cnpj="11222333000180"),                        # DV inválido
        reg("erp", "4", cnpj=CNPJ_B, cep="1310100"),                   # CEP sem zero à esquerda
        reg("erp", "5", cnpj=completar_dv("778889990001"), uf="RJ"),   # CEP de SP com UF RJ
        reg("erp", "6", data_ref="2020-01-01", cnpj=completar_dv("121212120001"), email="ze@oficina"),
        reg("cartao", "c1", cnpj=CNPJ_A_FILIAL, tipo_estabelecimento="MATRIZ"),  # ordem 0002 não é matriz
    )
    nc = qualidade.avaliar(df, catalogo, HOJE).nao_conformidades
    falhas = set(zip(nc["id_origem"], nc["regra_id"]))
    assert {("1", "DQ003"), ("2", "DQ003")} <= falhas
    assert ("3", "DQ002") in falhas
    assert ("4", "DQ013") in falhas
    assert ("5", "DQ015") in falhas
    assert ("6", "DQ020") in falhas and ("6", "DQ018") in falhas
    assert ("c1", "DQ005") in falhas
    assert ("4", "DQ015") not in falhas, "CEP inválido não deve ser julgado na consistência CEP×UF"


def test_scorecard_e_meta(catalogo):
    df = silver(reg("erp", "1", cnpj=CNPJ_A), reg("erp", "2", cnpj=CNPJ_A))
    res = qualidade.avaliar(df, catalogo, HOJE)
    uni = res.scorecard.query("fonte == 'erp' and dimensao == 'unicidade'").iloc[0]
    assert uni["conformidade"] == 0 and not uni["atingiu_meta"]
    assert 0 <= res.indice_geral <= 100


# ---------------------------------------------------------------- MDM
def test_match_exato_e_sobrevivencia_por_prioridade(cfg):
    df = silver(
        reg("receita", CNPJ_A, "2026-10-30", cnpj=CNPJ_A, razao_social="ALFA PLASTICOS LTDA",
            email="contador@escritorio.com.br", situacao_cadastral="BAIXADA"),
        reg("cartao", "a.pdf", "2024-01-01", cnpj=CNPJ_A, situacao_cadastral="ATIVA"),
        reg("erp", "10", "2026-09-01", cnpj=CNPJ_A, razao_social="Alfa Plast", cep="1720983",
            email="compras@alfa.com.br"),
    ).assign(score_registro=100)
    res = mdm.executar(df, cfg)
    assert len(res.golden) == 1
    g = res.golden.iloc[0]
    assert g["situacao_cadastral"] == "BAIXADA"          # Receita vence o cartão antigo
    assert g["razao_social"] == "ALFA PLASTICOS LTDA"
    assert g["email"] == "compras@alfa.com.br"          # exceção: contato do ERP vence
    assert g["cep"] == "17209832"                       # CEP inválido do ERP nunca concorre
    lin = res.linhagem.set_index("campo")
    assert lin.loc["email", "fonte"] == "erp"
    assert lin.loc["situacao_cadastral", "valores_distintos"] == 2
    assert set(res.crosswalk["id_mestre"]) == {mdm.id_mestre(CNPJ_A)}


def test_desempate_pela_recencia(cfg):
    df = silver(
        reg("cartao", "velho.pdf", "2022-01-01", cnpj=CNPJ_A, cep="17200000"),
        reg("cartao", "novo.pdf", "2026-06-01", cnpj=CNPJ_A, cep="17209832"),
    ).assign(score_registro=100)
    g = mdm.executar(df, cfg).golden.iloc[0]
    assert g["cep"] == "17209832"


def test_match_fuzzy_automatico_revisao_e_quarentena(cfg):
    df = silver(
        reg("receita", CNPJ_A, cnpj=CNPJ_A),
        reg("erp", "typo", cnpj="11222333000180"),                       # 1 dígito errado, resto igual
        reg("erp", "duvida", cnpj="", razao_social="ALFA PLASTICOS IND", cep="17200000"),
        reg("erp", "outro", cnpj="", razao_social="OFICINA DO ZE", cep="", municipio="BAURU"),
    ).assign(score_registro=100)
    res = mdm.executar(df, cfg)
    metodo = res.crosswalk.set_index("id_origem")["metodo_match"]
    assert metodo["typo"] == "fuzzy_automatico"
    assert metodo["duvida"] == "revisao_steward"
    assert metodo["outro"] == "sem_correspondente"
    assert list(res.fila_revisao["id_origem"]) == ["duvida"]


def test_decisao_do_steward_fecha_o_ciclo(cfg):
    df = silver(
        reg("receita", CNPJ_A, cnpj=CNPJ_A),
        reg("erp", "duvida", cnpj="", razao_social="ALFA PLASTICOS IND", cep="17200000"),
    ).assign(score_registro=100)
    decisoes = pd.DataFrame([{"fonte": "erp", "id_origem": "duvida", "decisao": "UNIR",
                              "id_mestre_sugerido": mdm.id_mestre(CNPJ_A)}])
    res = mdm.executar(df, cfg, decisoes)
    assert res.fila_revisao.empty
    assert res.golden.iloc[0]["qtd_registros_origem"] == 2


def test_blocagem_nao_depende_so_da_uf(cfg):
    """O registro sujo tem a UF errada; o CEP e o nome ainda o levam ao candidato certo."""
    df = silver(
        reg("receita", CNPJ_A, cnpj=CNPJ_A),
        reg("erp", "uf_errada", cnpj="", uf="MG"),
    ).assign(score_registro=100)
    metodo = mdm.executar(df, cfg).crosswalk.set_index("id_origem")["metodo_match"]
    assert metodo["uf_errada"] == "fuzzy_automatico"


def test_hierarquia(cfg):
    df = silver(reg("receita", CNPJ_A, cnpj=CNPJ_A),
                reg("receita", CNPJ_A_FILIAL, cnpj=CNPJ_A_FILIAL, tipo_estabelecimento="FILIAL"),
                reg("receita", CNPJ_B, cnpj=completar_dv("445556660003"), tipo_estabelecimento="FILIAL")
                ).assign(score_registro=100)
    h = mdm.executar(df, cfg).hierarquia.set_index("cnpj_raiz")
    assert h.loc["11222333", "qtd_filiais"] == 1 and h.loc["11222333", "matriz_no_cadastro"]
    assert not h.loc["44555666", "matriz_no_cadastro"]


def test_id_mestre_estavel():
    assert mdm.id_mestre(CNPJ_A) == mdm.id_mestre(CNPJ_A)
    assert mdm.id_mestre(CNPJ_A) != mdm.id_mestre(CNPJ_B)


# ---------------------------------------------------------------- LGPD
def test_mascaramento():
    assert lgpd.mascarar_nome_pessoa("MARIA SOUZA LIMA 12345678900") == "M. S. L. [CPF OCULTO]"
    assert lgpd.mascarar_email("compras@alfa.com.br") == "c***@alfa.com.br"
    assert lgpd.mascarar_telefone("14991234567") == "(14) ****-**67"
    df = pd.DataFrame({"razao_social": ["MARIA SOUZA 12345678900", "ALFA LTDA"],
                       "natureza_juridica": ["Empresário (Individual)", ""],
                       "email": ["m@x.com", ""]})
    out = lgpd.mascarar_df(df)
    assert "12345678900" not in out.to_string()
    assert out.loc[1, "razao_social"] == "ALFA LTDA"


@pytest.mark.parametrize("codificacao", ["cp1252", "utf-8-sig", "utf-8"])
def test_decisoes_editadas_no_excel_em_qualquer_codificacao(tmp_path, codificacao):
    from mdm_cnpj.pipeline import ler_csv_excel
    arq = tmp_path / "decisoes_steward.csv"
    arq.write_text("fonte;id_origem;decisao;decidido_por\nerp;1030;UNIR;João Conceição\n",
                   encoding=codificacao)
    df = ler_csv_excel(arq)
    assert df.loc[0, "decidido_por"] == "João Conceição"
    assert df.loc[0, "id_origem"] == "1030"
