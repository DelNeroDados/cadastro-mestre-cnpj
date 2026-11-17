"""Validadores de CNPJ, CEP, UF, CNAE, e-mail, telefone e datas."""
from __future__ import annotations

import re
from datetime import date, datetime

# CNPJ alfanumérico (IN RFB 2.229/2024, vale desde jul/2026): mesmo módulo 11,
# mas cada caractere vale ord(c) - 48 ("0" = 0, "A" = 17). Serve para os numéricos também.

_PESOS_DV1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_PESOS_DV2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_FORMATO_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def limpar_cnpj(valor: object) -> str:
    """Tira pontuação e espaços e põe em maiúsculas: "12.abc.345/01de-35" vira "12ABC34501DE35"."""
    if valor is None:
        return ""
    return re.sub(r"[^0-9A-Za-z]", "", str(valor)).upper()


def _dv(base: str, pesos: list[int]) -> int:
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(valor: object) -> bool:
    """Confere formato e dígitos verificadores (numérico ou alfanumérico)."""
    cnpj = limpar_cnpj(valor)
    if not _FORMATO_CNPJ.match(cnpj):
        return False
    if len(set(cnpj)) == 1:  # 00000000000000, 11111111111111... passam na conta mas não existem
        return False
    dv1 = _dv(cnpj[:12], _PESOS_DV1)
    dv2 = _dv(cnpj[:12] + str(dv1), _PESOS_DV2)
    return cnpj[12:] == f"{dv1}{dv2}"


def completar_dv(base12: str) -> str:
    """Recebe as 12 primeiras posições e devolve o CNPJ de 14 com os DVs (usado pela demo)."""
    base12 = limpar_cnpj(base12)
    dv1 = _dv(base12, _PESOS_DV1)
    dv2 = _dv(base12 + str(dv1), _PESOS_DV2)
    return f"{base12}{dv1}{dv2}"


def formatar_cnpj(valor: object) -> str:
    """Máscara oficial XX.XXX.XXX/XXXX-XX. Se não tiver 14 posições, devolve limpo."""
    c = limpar_cnpj(valor)
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def cnpj_raiz(valor: object) -> str:
    """As 8 primeiras posições identificam a empresa; o resto, o estabelecimento."""
    return limpar_cnpj(valor)[:8]


def eh_matriz(valor: object) -> bool:
    """Ordem 0001 é a matriz por convenção da Receita."""
    return limpar_cnpj(valor)[8:12] == "0001"


UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Faixas de CEP (5 primeiros dígitos) por UF, dos Correios.
FAIXAS_CEP = {
    "SP": [(1000, 19999)], "RJ": [(20000, 28999)], "ES": [(29000, 29999)],
    "MG": [(30000, 39999)], "BA": [(40000, 48999)], "SE": [(49000, 49999)],
    "PE": [(50000, 56999)], "AL": [(57000, 57999)], "PB": [(58000, 58999)],
    "RN": [(59000, 59999)], "CE": [(60000, 63999)], "PI": [(64000, 64999)],
    "MA": [(65000, 65999)], "PA": [(66000, 68899)], "AP": [(68900, 68999)],
    "AM": [(69000, 69299), (69400, 69899)], "RR": [(69300, 69399)],
    "AC": [(69900, 69999)], "DF": [(70000, 72799), (73000, 73699)],
    "GO": [(72800, 72999), (73700, 76799)], "RO": [(76800, 76999)],
    "TO": [(77000, 77999)], "MT": [(78000, 78899)], "MS": [(79000, 79999)],
    "PR": [(80000, 87999)], "SC": [(88000, 89999)], "RS": [(90000, 99999)],
}


def so_digitos(valor: object) -> str:
    if valor is None:
        return ""
    return re.sub(r"\D", "", str(valor))


def cep_valido(valor: object) -> bool:
    cep = so_digitos(valor)
    return len(cep) == 8 and cep != "00000000"


def uf_valida(valor: object) -> bool:
    return str(valor or "").strip().upper() in UFS


def cep_pertence_uf(cep: object, uf: object) -> bool:
    """Falso também quando um dos dois é inválido; a regra decide se avalia ou não."""
    cep_d = so_digitos(cep)
    uf_s = str(uf or "").strip().upper()
    if len(cep_d) != 8 or uf_s not in FAIXAS_CEP:
        return False
    prefixo = int(cep_d[:5])
    return any(ini <= prefixo <= fim for ini, fim in FAIXAS_CEP[uf_s])


# Atividade econômica, contato e datas
def cnae_valido(valor: object) -> bool:
    """CNAE-Subclasse tem 7 dígitos (ex.: 32.99-0-05 -> 3299005)."""
    return len(so_digitos(valor)) == 7


_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def email_valido(valor: object) -> bool:
    return bool(_EMAIL.match(str(valor or "").strip().lower()))


def telefone_valido(valor: object) -> bool:
    """DDD + número: 10 dígitos (fixo) ou 11 começando por 9 (celular). DDD não começa com 0."""
    tel = so_digitos(valor)
    if len(tel) == 10:
        return tel[0] != "0"
    if len(tel) == 11:
        return tel[0] != "0" and tel[2] == "9"
    return False


def para_data(valor: object) -> date | None:
    """Aceita ISO (2008-09-02), brasileiro (02/09/2008) e datetime. Devolve None se não der."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def data_valida(valor: object, minimo: date = date(1900, 1, 1), hoje: date | None = None) -> bool:
    """Data interpretável, não anterior a `minimo` e não futura."""
    d = para_data(valor)
    if d is None:
        return False
    return minimo <= d <= (hoje or date.today())


# Validadores que as regras de qualidade podem citar pelo nome no YAML.
VALIDADORES = {
    "cnpj": cnpj_valido,
    "cep": cep_valido,
    "uf": uf_valida,
    "cnae": cnae_valido,
    "email": email_valido,
    "telefone": telefone_valido,
    "data": data_valida,
}
