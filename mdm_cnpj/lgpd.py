"""Mascaramento de dados pessoais nas saídas compartilháveis (HTML e RESUMO.md).

Razão social de MEI é o nome da pessoa, às vezes com o CPF no final; e-mail e
telefone também podem ser do dono. CSVs e SQLite ficam com o dado completo."""
from __future__ import annotations

import re

import pandas as pd

# Classificação de cada campo do esquema canônico.
CLASSIFICACAO = {
    "cnpj": "público",
    "razao_social": "pessoal quando empresário individual/MEI (nome e CPF da pessoa)",
    "nome_fantasia": "público",
    "email": "pessoal (pode identificar o titular)",
    "telefone": "pessoal (pode identificar o titular)",
    "logradouro": "pessoal quando empresário individual/MEI (endereço residencial frequente)",
    "numero": "pessoal quando empresário individual/MEI",
}

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def tem_cpf(texto: str) -> bool:
    return bool(_CPF.search(str(texto or "")))


def mascarar_cpf(texto: str) -> str:
    return _CPF.sub("[CPF OCULTO]", str(texto or ""))


def mascarar_nome_pessoa(texto: str) -> str:
    """'MARIA SOUZA LIMA 12345678900' -> 'M. S. L. [CPF OCULTO]'."""
    sem_cpf = _CPF.sub("", str(texto or "")).split()
    iniciais = " ".join(f"{p[0]}." for p in sem_cpf if p)
    return f"{iniciais} [CPF OCULTO]" if tem_cpf(texto) else iniciais


def mascarar_email(email: str) -> str:
    email = str(email or "")
    if "@" not in email:
        return "***" if email else ""
    usuario, dominio = email.split("@", 1)
    return f"{usuario[:1]}***@{dominio}"


def mascarar_telefone(tel: str) -> str:
    d = re.sub(r"\D", "", str(tel or ""))
    if len(d) < 6:
        return "***" if d else ""
    return f"({d[:2]}) ****-**{d[-2:]}"


def eh_pessoa(razao_social: str, natureza: str = "") -> bool:
    return tem_cpf(razao_social) or "INDIVIDUAL" in str(natureza or "").upper()


def mascarar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Cópia com os campos pessoais mascarados. Colunas ausentes são ignoradas."""
    out = df.copy()
    natureza = out["natureza_juridica"] if "natureza_juridica" in out else pd.Series("", index=out.index)
    for col in [c for c in out.columns if "razao_social" in c]:
        out[col] = [mascarar_nome_pessoa(v) if eh_pessoa(v, n) else v
                    for v, n in zip(out[col], natureza)]
    for col in [c for c in out.columns if "email" in c]:
        out[col] = out[col].map(mascarar_email)
    for col in [c for c in out.columns if "telefone" in c]:
        out[col] = out[col].map(mascarar_telefone)
    # Tabelas "longas" (uma linha por campo) dizem na coluna `campo` o que é o valor.
    campos = out["campo"] if "campo" in out else pd.Series("", index=out.index)
    for col in ("valor_encontrado", "valor_fonte", "valor_receita", "valor", "alternativas"):
        if col in out:
            out[col] = [_por_campo(c, v) for c, v in zip(campos, out[col])]
    return out


def _por_campo(campo: str, valor) -> str:
    partes = str(valor or "").split(" | ")
    if "email" in campo:
        return " | ".join(mascarar_email(p) for p in partes)
    if "telefone" in campo:
        return " | ".join(mascarar_telefone(p) for p in partes)
    if "razao_social" in campo:
        return " | ".join(mascarar_nome_pessoa(p) if tem_cpf(p) else p for p in partes)
    return mascarar_cpf(valor)
