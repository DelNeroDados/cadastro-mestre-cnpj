"""Leitura dos cartões CNPJ em PDF.

O cartão tem colunas fixas (rótulo em cima, valor embaixo), então uso a
posição x de cada palavra para saber de qual campo ela é. Pelo texto corrido
não dá para separar bairro de município."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .padronizacao import sem_acento

# pdfminer reclama de fonte malformada em quase todo cartão; não afeta o texto.
logging.getLogger("pdfminer").setLevel(logging.ERROR)


@dataclass(frozen=True)
class Palavra:
    texto: str
    x0: float
    top: float


def agrupar_linhas(palavras: list[Palavra], tolerancia: float = 3.0) -> list[list[Palavra]]:
    """Palavras cuja altura (top) difere até `tolerancia` pontos ficam na mesma linha."""
    linhas: list[list[Palavra]] = []
    for p in sorted(palavras, key=lambda w: (w.top, w.x0)):
        if linhas and abs(linhas[-1][0].top - p.top) <= tolerancia:
            linhas[-1].append(p)
        else:
            linhas.append([p])
    return [sorted(linha, key=lambda w: w.x0) for linha in linhas]


def _norm(s: str) -> str:
    return sem_acento(s).upper()


def _texto_linha(linha: list[Palavra]) -> str:
    return " ".join(p.texto for p in linha)


# Rótulos do cartão. "colunas": (primeira palavra do rótulo da coluna, campo).
ROTULOS = [
    ("NUMERO DE INSCRICAO", "identificacao", None),
    ("NOME EMPRESARIAL", "texto", "razao_social"),
    ("TITULO DO ESTABELECIMENTO", "colunas", [("TITULO", "nome_fantasia"), ("PORTE", "porte")]),
    ("CODIGO E DESCRICAO DA ATIVIDADE ECONOMICA PRINCIPAL", "texto", "cnae_principal_texto"),
    ("CODIGO E DESCRICAO DAS ATIVIDADES ECONOMICAS SECUNDARIAS", "linhas", "cnaes_secundarios_texto"),
    ("CODIGO E DESCRICAO DA NATUREZA JURIDICA", "texto", "natureza_juridica_texto"),
    ("LOGRADOURO", "colunas", [("LOGRADOURO", "logradouro"), ("NUMERO", "numero"),
                                ("COMPLEMENTO", "complemento")]),
    ("CEP", "colunas", [("CEP", "cep"), ("BAIRRO/DISTRITO", "bairro"),
                        ("MUNICIPIO", "municipio"), ("UF", "uf")]),
    ("ENDERECO ELETRONICO", "colunas", [("ENDERECO", "email"), ("TELEFONE", "telefone")]),
    ("ENTE FEDERATIVO", "ignorar", None),
    ("SITUACAO CADASTRAL", "colunas", [("SITUACAO", "situacao_cadastral"),
                                       ("DATA", "data_situacao_cadastral")]),
    ("MOTIVO DE SITUACAO CADASTRAL", "texto", "motivo_situacao"),
    ("SITUACAO ESPECIAL", "ignorar", None),
    ("APROVADO PELA", "fim", None),
    ("EMITIDO NO DIA", "fim", None),
]

_RE_CNPJ = re.compile(r"[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-[0-9]{2}")
_RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_RE_TELEFONE = re.compile(r"\(?\d{2}\)?\s*\d{4,5}-?\d{4}")
_RE_CNAE = re.compile(r"^(\d{2}\.\d{2}-\d-\d{2})\s*-\s*(.*)$")


def _rotulo_da_linha(linha: list[Palavra]):
    t = _norm(_texto_linha(linha))
    for rotulo, tipo, alvo in ROTULOS:
        if t.startswith(rotulo):
            return rotulo, tipo, alvo
    return None


def _colunas(linha_rotulo: list[Palavra], specs) -> list[tuple[float, str]]:
    """Acha o x de cada coluna procurando a palavra-chave da esquerda para a direita."""
    cols, inicio = [], 0
    for chave, campo in specs:
        for i in range(inicio, len(linha_rotulo)):
            if _norm(linha_rotulo[i].texto).startswith(chave):
                cols.append((linha_rotulo[i].x0, campo))
                inicio = i + 1
                break
    return cols


def _distribuir(valores: list[list[Palavra]], cols: list[tuple[float, str]]) -> dict[str, str]:
    """Cada palavra vai para a coluna mais à direita cujo rótulo começa antes dela."""
    saida = {campo: [] for _, campo in cols}
    for linha in valores:
        for p in linha:
            escolhida = cols[0][1]
            for x, campo in cols:
                if p.x0 >= x - 2:  # 2 pt de folga para arredondamentos do PDF
                    escolhida = campo
            saida[escolhida].append(p.texto)
    return {k: " ".join(v) for k, v in saida.items()}


def extrair_cartao(linhas: list[list[Palavra]]) -> dict | None:
    """Devolve os campos do cartão ou None se a página não tiver o layout do cartão."""
    blocos = []  # (indice_linha, rotulo, tipo, alvo)
    for i, linha in enumerate(linhas):
        r = _rotulo_da_linha(linha)
        if r:
            blocos.append((i, *r))
    if not any(b[1] == "NUMERO DE INSCRICAO" for b in blocos):
        return None

    dados: dict[str, str] = {}
    for n, (i, rotulo, tipo, alvo) in enumerate(blocos):
        fim = blocos[n + 1][0] if n + 1 < len(blocos) else len(linhas)
        valores = linhas[i + 1:fim]
        if tipo in ("ignorar", "fim"):
            continue
        if tipo == "identificacao":
            texto = " ".join(_texto_linha(l) for l in valores)
            m = _RE_CNPJ.search(texto)
            dados["cnpj"] = m.group(0) if m else ""
            datas = _RE_DATA.findall(texto)
            dados["data_abertura"] = datas[0] if datas else ""
            tipo_est = re.search(r"\b(MATRIZ|FILIAL)\b", texto)
            dados["tipo_estabelecimento"] = tipo_est.group(1) if tipo_est else ""
        elif tipo == "texto":
            dados[alvo] = " ".join(_texto_linha(l) for l in valores)
        elif tipo == "linhas":
            # Uma atividade por linha; descrições longas quebram para a linha de baixo.
            itens: list[str] = []
            for l in valores:
                t = _texto_linha(l)
                if _RE_CNAE.match(t) or not itens:
                    itens.append(t)
                else:
                    itens[-1] += " " + t
            dados[alvo] = " | ".join(itens)
        elif tipo == "colunas":
            cols = _colunas(linhas[i], alvo)
            if cols:
                dados.update(_distribuir(valores, cols))
    return dados


def _separar_codigo(texto: str) -> tuple[str, str]:
    m = _RE_CNAE.match(texto.strip())
    return (m.group(1), m.group(2)) if m else ("", texto.strip())


def para_canonico(dados: dict) -> dict:
    """Bronze do cartão -> chaves do esquema canônico (ainda sem padronizar formatos)."""
    cod, desc = _separar_codigo(dados.get("cnae_principal_texto", ""))
    secundarios = [
        _separar_codigo(s)[0] for s in dados.get("cnaes_secundarios_texto", "").split(" | ")
    ]
    natureza = re.sub(r"^\d{3}-\d\s*-\s*", "", dados.get("natureza_juridica_texto", ""))
    # Alguns cartões trazem dois telefones ("(14) 3555-0101/ (14) 3555-0202"):
    # fica o primeiro, senão os dígitos dos dois se juntam num número inválido.
    tel = _RE_TELEFONE.search(dados.get("telefone", ""))
    return {
        **{k: dados.get(k, "") for k in (
            "cnpj", "razao_social", "nome_fantasia", "tipo_estabelecimento", "data_abertura",
            "situacao_cadastral", "data_situacao_cadastral", "porte", "logradouro", "numero",
            "complemento", "bairro", "municipio", "uf", "cep", "email")},
        "telefone": tel.group(0) if tel else "",
        "natureza_juridica": natureza,
        "cnae_principal": cod,
        "cnae_principal_descricao": desc,
        "cnaes_secundarios": [s for s in secundarios if s],
    }


def hash_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_pdf(caminho: Path) -> tuple[dict | None, str]:
    """Procura o cartão em qualquer página (há contratos sociais com o cartão anexado).

    Devolve (dados, motivo). `motivo` explica a rejeição quando dados é None.
    """
    import pdfplumber  # importado aqui para os testes rodarem sem PDFs

    amostra = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            palavras = [Palavra(w["text"], w["x0"], w["top"]) for w in pagina.extract_words()]
            if not palavras:
                continue
            amostra.extend(p.texto for p in palavras)
            dados = extrair_cartao(agrupar_linhas(palavras))
            if dados:
                texto = pagina.extract_text() or ""
                emissao = re.search(r"Emitido no dia (\d{2}/\d{2}/\d{4})", texto)
                dados["data_emissao"] = emissao.group(1) if emissao else ""
                return dados, ""
    return None, classificar_rejeicao(" ".join(amostra))


def classificar_rejeicao(texto: str) -> str:
    """Motivo da rejeição, pensado para quem vai tratar o arquivo depois."""
    if not texto.strip():
        return "imagem_sem_texto (precisa de OCR)"
    if texto.count("(cid:") > 20:
        return "fonte_sem_mapa_unicode (precisa de OCR)"
    if len(texto) < 200:
        return "pouco_texto (digitalizacao parcial; precisa de OCR)"
    return "outro_documento (nao e cartao CNPJ)"


def extrair_pasta(pasta: Path, pasta_cache: Path | None = None,
                  avisar=lambda msg: None) -> tuple[list[dict], list[dict]]:
    """Lê todos os PDFs da pasta. Nada é movido nem apagado: rejeições viram registro.

    Com `pasta_cache`, o resultado de cada arquivo fica guardado pelo hash do
    conteúdo: reexecutar não relê o PDF (a leitura custa ~1 s por arquivo), e um
    arquivo renomeado continua sendo reconhecido.
    """
    import json

    lidos, rejeitados = [], []
    arquivos = sorted(p for p in Path(pasta).iterdir() if p.suffix.lower() == ".pdf")
    if pasta_cache:
        Path(pasta_cache).mkdir(parents=True, exist_ok=True)
    for n, caminho in enumerate(arquivos, 1):
        sha = hash_arquivo(caminho)
        cache = Path(pasta_cache) / f"{sha}.json" if pasta_cache else None
        if cache and cache.exists():
            dados, motivo = json.loads(cache.read_text(encoding="utf-8"))
        else:
            avisar(f"  lendo {n}/{len(arquivos)}: {caminho.name}")
            try:
                dados, motivo = ler_pdf(caminho)
            except Exception as e:  # PDF corrompido ou protegido
                dados, motivo = None, f"erro_leitura: {type(e).__name__}"
            if cache:
                cache.write_text(json.dumps([dados, motivo], ensure_ascii=False), encoding="utf-8")
        if dados is None:
            rejeitados.append({"arquivo": caminho.name, "sha256": sha, "motivo": motivo})
        else:
            lidos.append({"arquivo": caminho.name, "sha256": sha, **dados})
    return lidos, rejeitados
