from datetime import date

import pytest

from mdm_cnpj.validadores import (cep_pertence_uf, cep_valido, cnpj_raiz, cnpj_valido, completar_dv,
                                  data_valida, eh_matriz, email_valido, formatar_cnpj, limpar_cnpj,
                                  telefone_valido)


class TestCNPJ:
    def test_exemplo_oficial_alfanumerico_da_receita(self):
        assert cnpj_valido("12.ABC.345/01DE-35")

    def test_aceita_minusculas_e_sem_mascara(self):
        assert cnpj_valido("12abc34501de35")

    def test_numerico_classico(self):
        cnpj = completar_dv("112223330001")
        assert cnpj == "11222333000181"
        assert cnpj_valido(formatar_cnpj(cnpj))

    @pytest.mark.parametrize("posicao", range(14))
    def test_qualquer_digito_trocado_invalida(self, posicao):
        cnpj = "11222333000181"
        trocado = cnpj[:posicao] + str((int(cnpj[posicao]) + 1) % 10) + cnpj[posicao + 1:]
        assert not cnpj_valido(trocado)

    @pytest.mark.parametrize("valor", ["", None, "123", "00000000000000", "11111111111111",
                                       "12ABC34501DEAB", "1122233300018"])
    def test_invalidos(self, valor):
        assert not cnpj_valido(valor)

    def test_raiz_e_matriz(self):
        assert cnpj_raiz("11.222.333/0001-81") == "11222333"
        assert eh_matriz("11.222.333/0001-81")
        assert not eh_matriz(completar_dv("112223330002"))

    def test_limpar(self):
        assert limpar_cnpj(" 12.abc.345/01de-35 ") == "12ABC34501DE35"


class TestEndereco:
    def test_cep(self):
        assert cep_valido("17.209-832")
        assert not cep_valido("1310100")  # zero à esquerda perdido no Excel
        assert not cep_valido("00000000")

    @pytest.mark.parametrize("cep,uf,esperado", [
        ("01310-100", "SP", True), ("17209832", "SP", True), ("20040002", "RJ", True),
        ("70040010", "DF", True), ("73700000", "GO", True), ("69301000", "RR", True),
        ("17209832", "RJ", False), ("1310100", "SP", False), ("17209832", "XX", False),
    ])
    def test_cep_pertence_uf(self, cep, uf, esperado):
        assert cep_pertence_uf(cep, uf) is esperado


class TestContatoEDatas:
    @pytest.mark.parametrize("tel,ok", [("(14) 3555-0142", True), ("14991234567", True),
                                        ("35550142", False), ("14891234567", False), ("0135550142", False)])
    def test_telefone(self, tel, ok):
        assert telefone_valido(tel) is ok

    @pytest.mark.parametrize("email,ok", [("Contato@Empresa.com.br", True), ("ze@oficina", False),
                                          ("joao.gmail.com", False), ("", False)])
    def test_email(self, email, ok):
        assert email_valido(email) is ok

    def test_data(self):
        hoje = date(2026, 11, 1)
        assert data_valida("02/09/2008", hoje=hoje)
        assert data_valida("2008-09-02", hoje=hoje)
        assert not data_valida("2027-01-01", hoje=hoje)
        assert not data_valida("31/02/2020", hoje=hoje)
        assert not data_valida("1850-01-01", hoje=hoje)
