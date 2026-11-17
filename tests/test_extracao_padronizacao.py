"""Extração do cartão a partir de palavras com coordenadas (sem PDF real)."""
from mdm_cnpj.extracao import Palavra, agrupar_linhas, classificar_rejeicao, extrair_cartao, para_canonico
from mdm_cnpj.padronizacao import chave_nome, padronizar


def _linha(top, *pares):
    return [Palavra(t, x, top) for t, x in pares]


def cartao_sintetico():
    """Mesmo desenho do comprovante da Receita: rótulo em cima, valor embaixo, colunas fixas."""
    linhas = [
        _linha(60, ("01/11/2026,", 20), ("10:00", 70), ("Comprovante", 120)),
        _linha(397, ("NÚMERO", 75), ("DE", 103), ("INSCRIÇÃO", 113), ("DATA", 431), ("DE", 448), ("ABERTURA", 457)),
        _linha(404, ("11.222.333/0001-81", 75), ("15/03/2010", 431)),
        _linha(412, ("MATRIZ", 75)),
        _linha(440, ("NOME", 75), ("EMPRESARIAL", 100)),
        _linha(447, ("ALFA", 75), ("PLASTICOS", 100), ("LTDA", 160)),
        _linha(466, ("TÍTULO", 75), ("DO", 98), ("ESTABELECIMENTO", 109), ("(NOME", 169), ("DE", 190),
               ("FANTASIA)", 200), ("PORTE", 497)),
        _linha(473, ("ALFA", 75), ("PLAST", 97), ("EPP", 497)),
        _linha(495, ("CÓDIGO", 75), ("E", 101), ("DESCRIÇÃO", 107), ("DA", 144), ("ATIVIDADE", 153),
               ("ECONÔMICA", 186), ("PRINCIPAL", 225)),
        _linha(502, ("22.29-3-99", 75), ("-", 120), ("Fabricação", 126), ("de", 170), ("plásticos", 182)),
        _linha(525, ("CÓDIGO", 75), ("E", 101), ("DESCRIÇÃO", 107), ("DAS", 144), ("ATIVIDADES", 160),
               ("ECONÔMICAS", 200), ("SECUNDÁRIAS", 250)),
        _linha(532, ("46.86-9-02", 75), ("-", 120), ("Comércio", 126), ("atacadista", 170), ("de", 220)),
        _linha(539, ("embalagens", 75)),  # descrição quebrada em duas linhas
        _linha(546, ("49.30-2-02", 75), ("-", 120), ("Transporte", 126)),
        _linha(555, ("CÓDIGO", 75), ("E", 101), ("DESCRIÇÃO", 107), ("DA", 144), ("NATUREZA", 154), ("JURÍDICA", 187)),
        _linha(562, ("206-2", 75), ("-", 105), ("Sociedade", 112), ("Empresária", 160), ("Limitada", 210)),
        _linha(584, ("LOGRADOURO", 75), ("NÚMERO", 319), ("COMPLEMENTO", 375)),
        _linha(591, ("AV", 75), ("DAS", 90), ("INDUSTRIAS", 112), ("1500", 319), ("GALPAO", 375), ("2", 410)),
        _linha(614, ("CEP", 75), ("BAIRRO/DISTRITO", 169), ("MUNICÍPIO", 319), ("UF", 506)),
        _linha(621, ("17.209-832", 75), ("DISTRITO", 169), ("INDUSTRIAL", 205), ("SAO", 319), ("JOSE", 340),
               ("DO", 365), ("RIO", 380), ("PRETO", 400), ("SP", 506)),
        _linha(644, ("ENDEREÇO", 75), ("ELETRÔNICO", 111), ("TELEFONE", 319)),
        _linha(651, ("contato@alfa.com.br", 75), ("(14)", 319), ("3621-0000", 340)),
        _linha(703, ("SITUAÇÃO", 75), ("CADASTRAL", 107), ("DATA", 419), ("DA", 435), ("SITUAÇÃO", 445),
               ("CADASTRAL", 477)),
        _linha(711, ("ATIVA", 75), ("15/03/2010", 419)),
        _linha(733, ("MOTIVO", 75), ("DE", 100), ("SITUAÇÃO", 110), ("CADASTRAL", 143)),
        _linha(800, ("Emitido", 75), ("no", 110), ("dia", 125), ("01/11/2026", 140)),
    ]
    return agrupar_linhas([p for l in linhas for p in l])


def test_colunas_separadas_pela_posicao():
    d = extrair_cartao(cartao_sintetico())
    assert d["cep"] == "17.209-832"
    assert d["bairro"] == "DISTRITO INDUSTRIAL"
    assert d["municipio"] == "SAO JOSE DO RIO PRETO"  # na v1 ficava vazio
    assert d["uf"] == "SP"
    assert (d["logradouro"], d["numero"], d["complemento"]) == ("AV DAS INDUSTRIAS", "1500", "GALPAO 2")
    assert (d["nome_fantasia"], d["porte"]) == ("ALFA PLAST", "EPP")


def test_data_de_abertura_nao_e_a_data_de_emissao():
    d = extrair_cartao(cartao_sintetico())
    assert d["data_abertura"] == "15/03/2010"  # na v1 vinha a data do cabeçalho do navegador
    assert d["cnpj"] == "11.222.333/0001-81"
    assert d["tipo_estabelecimento"] == "MATRIZ"


def test_cnaes_secundarios_com_quebra_de_linha():
    can = para_canonico(extrair_cartao(cartao_sintetico()))
    assert can["cnae_principal"] == "22.29-3-99"
    assert can["cnaes_secundarios"] == ["46.86-9-02", "49.30-2-02"]
    assert can["natureza_juridica"] == "Sociedade Empresária Limitada"


def test_pagina_sem_layout_de_cartao():
    assert extrair_cartao(agrupar_linhas([Palavra("CONTRATO", 10, 10), Palavra("SOCIAL", 80, 10)])) is None


def test_motivos_de_rejeicao():
    assert classificar_rejeicao("").startswith("imagem_sem_texto")
    assert classificar_rejeicao("(cid:1)" * 30).startswith("fonte_sem_mapa")
    assert classificar_rejeicao("Scanned with CamScanner").startswith("pouco_texto")
    assert classificar_rejeicao("x " * 300).startswith("outro_documento")


def test_padronizacao_do_cartao():
    r = padronizar(para_canonico(extrair_cartao(cartao_sintetico())), "cartao", "a.pdf", "01/11/2026")
    assert r["cnpj"] == "11222333000181"
    assert r["cep"] == "17209832"
    assert r["data_abertura"] == "2010-03-15"
    assert r["data_referencia"] == "2026-11-01"
    assert r["telefone"] == "1436210000"
    assert r["cnae_principal"] == "2229399"
    assert r["cnaes_secundarios"] == "4686902|4930202"
    assert r["porte"] == "EPP"


def test_padronizacao_alinha_formatos_da_api_e_do_cartao():
    api = padronizar({"logradouro": "RUA DAS PALMEIRAS", "porte": "MICRO EMPRESA", "complemento": "********",
                      "municipio": "JAÚ", "email": None}, "receita", "x")
    assert api["logradouro"] == "R DAS PALMEIRAS"
    assert api["porte"] == "ME"
    assert api["complemento"] == ""
    assert api["municipio"] == "JAU"
    assert api["email"] == ""


def test_chave_nome_ignora_sufixos_pontuacao_e_cpf():
    assert chave_nome("Fertil-Max Ind. e Com. de Adubos Ltda.") == "FERTIL MAX IND COM ADUBOS"
    assert chave_nome("MARIA SOUZA 12345678900") == chave_nome("Maria Souza")
    assert chave_nome("ALFA S.A.") == chave_nome("ALFA SA") == "ALFA"


def test_cartao_com_dois_telefones_fica_com_o_primeiro():
    d = extrair_cartao(cartao_sintetico())
    d["telefone"] = "(14) 3555-0101/ (14) 3555-0202"
    assert padronizar(para_canonico(d), "cartao", "a.pdf")["telefone"] == "1435550101"


def test_adaptador_opencnpj_produz_o_formato_da_brasilapi():
    from mdm_cnpj import receita
    bruto = {
        "cnpj": "11222333000181", "razao_social": "ALFA PLASTICOS LTDA", "situacao_cadastral": "Ativa",
        "matriz_filial": "Matriz", "porte_empresa": "Empresa de Pequeno Porte (EPP)",
        "cnaes": [{"codigo": "2229399", "descricao": "Plásticos", "is_principal": True},
                  {"codigo": "4686902", "descricao": "Embalagens", "is_principal": False}],
        "tipo_logradouro": "AVENIDA", "logradouro": "DAS INDUSTRIAS", "cep": "17209832",
        "telefones": [{"ddd": "14", "numero": "36210000", "is_fax": False}],
        "QSA": [{"nome_socio": "FULANO"}],
    }
    r = padronizar(receita.para_canonico(receita.de_opencnpj(bruto)), "receita", "x")
    assert r["situacao_cadastral"] == "ATIVA"
    assert r["tipo_estabelecimento"] == "MATRIZ"
    assert r["porte"] == "EPP"
    assert r["logradouro"] == "AV DAS INDUSTRIAS"
    assert r["cnae_principal"] == "2229399" and r["cnaes_secundarios"] == "4686902"
    assert r["telefone"] == "1436210000"
