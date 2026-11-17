"""Esquema canônico e padronização de formatos.

Só padroniza formato (tira máscara, maiúsculas, datas ISO). Valor errado
continua errado, para as regras de qualidade apontarem."""
from __future__ import annotations

import re
import unicodedata

from .validadores import limpar_cnpj, para_data, so_digitos

# Colunas do esquema canônico (descritas em docs/DICIONARIO_DE_DADOS.md).
CAMPOS = [
    "cnpj", "razao_social", "nome_fantasia", "tipo_estabelecimento",
    "data_abertura", "situacao_cadastral", "data_situacao_cadastral",
    "natureza_juridica", "porte", "cnae_principal", "cnae_principal_descricao",
    "cnaes_secundarios", "logradouro", "numero", "complemento", "bairro",
    "municipio", "uf", "cep", "email", "telefone",
]
# Colunas de controle que acompanham todo registro silver.
CONTROLE = ["fonte", "id_origem", "data_referencia"]

SITUACOES = {"ATIVA", "BAIXADA", "INAPTA", "SUSPENSA", "NULA"}

# O cartão escreve o porte abreviado; a API, por extenso. Fica a forma curta.
PORTES = {"MICRO EMPRESA": "ME", "MICROEMPRESA": "ME", "EMPRESA DE PEQUENO PORTE": "EPP",
          "DEMAIS": "DEMAIS", "ME": "ME", "EPP": "EPP"}

# Cartão usa "R", "AV"; a API devolve "RUA", "AVENIDA". Padronizo no abreviado.
TIPOS_LOGRADOURO = {
    "RUA": "R", "AVENIDA": "AV", "AV.": "AV", "R.": "R", "RODOVIA": "ROD", "TRAVESSA": "TV",
    "ALAMEDA": "AL", "ESTRADA": "EST", "PRACA": "PCA", "VIELA": "VLA", "LARGO": "LGO",
    "VIA": "VIA", "SITIO": "SIT", "FAZENDA": "FAZ", "CHACARA": "CH",
}

# Valores que as fontes usam para dizer "não tem". Viram vazio.
_VAZIOS = {"", "********", "*****", "NAO INFORMADO", "NÃO INFORMADO", "NONE", "NULL", "NAN", "-"}


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def texto(valor: object) -> str:
    """Espaços colapsados, maiúsculas, marcadores de vazio viram ''."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKC", str(valor))
    s = re.sub(r"[\x00-\x1f\x7f-\x9f-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return "" if s in _VAZIOS or set(s) <= {"*"} else s


def data_iso(valor: object) -> str:
    d = para_data(valor)
    return d.isoformat() if d else ""


def situacao(valor: object) -> str:
    # Fora do domínio continua como veio, para a regra de domínio apontar.
    return sem_acento(texto(valor))


def tipo_estabelecimento(valor: object) -> str:
    s = texto(valor)
    if s in {"MATRIZ", "FILIAL"}:
        return s
    if s == "1":
        return "MATRIZ"
    if s == "2":
        return "FILIAL"
    return ""


def padronizar(bruto: dict, fonte: str, id_origem: str, data_referencia: object = "") -> dict:
    """Leva um dicionário com (algumas) chaves canônicas para o esquema silver completo."""
    r = {c: bruto.get(c, "") for c in CAMPOS}
    r["cnpj"] = limpar_cnpj(r["cnpj"])
    for c in ("razao_social", "nome_fantasia", "natureza_juridica", "porte",
              "cnae_principal_descricao", "logradouro", "numero", "complemento",
              "bairro", "municipio", "uf"):
        r[c] = texto(r[c])
    r["municipio"] = sem_acento(r["municipio"])
    partes = sem_acento(r["logradouro"]).split(" ", 1)
    if len(partes) == 2 and partes[0] in TIPOS_LOGRADOURO:
        r["logradouro"] = f"{TIPOS_LOGRADOURO[partes[0]]} {r['logradouro'].split(' ', 1)[1]}"
    r["porte"] = PORTES.get(sem_acento(r["porte"]), r["porte"])
    r["situacao_cadastral"] = situacao(r["situacao_cadastral"])
    r["tipo_estabelecimento"] = tipo_estabelecimento(r["tipo_estabelecimento"])
    r["data_abertura"] = data_iso(r["data_abertura"])
    r["data_situacao_cadastral"] = data_iso(r["data_situacao_cadastral"])
    r["cnae_principal"] = so_digitos(r["cnae_principal"])
    secs = r["cnaes_secundarios"]
    if isinstance(secs, str):
        secs = [s for s in re.split(r"[|;,]", secs) if s.strip()]
    r["cnaes_secundarios"] = "|".join(so_digitos(s) for s in (secs or []) if so_digitos(s))
    r["cep"] = so_digitos(r["cep"])
    r["telefone"] = so_digitos(r["telefone"])
    r["email"] = str(r["email"] or "").strip().lower()
    if r["email"] in {"none", "null", "nan"}:
        r["email"] = ""
    r["fonte"] = fonte
    r["id_origem"] = str(id_origem)
    r["data_referencia"] = data_iso(data_referencia)
    return r


# Sufixos jurídicos e palavras que não ajudam a distinguir empresas.
_RUIDO_NOME = {
    "LTDA", "ME", "EPP", "EIRELI", "SA", "S/A", "S.A", "MEI", "CIA", "COMPANHIA",
    "E", "DE", "DA", "DO", "DAS", "DOS", "EM", "LIMITADA", "SOCIEDADE", "UNIPESSOAL", "SLU",
}


def chave_nome(valor: object) -> str:
    """'Fertil-Max Ind. e Com. de Adubos Ltda.' -> 'FERTIL MAX IND COM ADUBOS'.

    Também remove sequências de 11 dígitos (o CPF que a Receita anexa ao nome
    de empresários individuais/MEI), para que o nome com e sem CPF casem.
    """
    s = sem_acento(texto(valor))
    s = re.sub(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", " ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s.replace("S/A", "SA").replace("S.A.", "SA"))
    return " ".join(t for t in s.split() if t not in _RUIDO_NOME)
