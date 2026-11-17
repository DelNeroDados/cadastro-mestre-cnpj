"""Consulta do CNPJ na Receita: BrasilAPI, com a OpenCNPJ de reserva.

Em nov/2026 a BrasilAPI começou a devolver 404 para CNPJs ativos, então um 404
só vale quando os dois provedores dizem que o CNPJ não existe. As respostas
ficam em cache por CNPJ. O QSA (sócios) é descartado, não preciso dele."""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import re

PROVEDORES = [
    ("brasilapi", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
    ("opencnpj", "https://api.opencnpj.org/{cnpj}"),
]
CAMPOS_DESCARTADOS = {"qsa", "QSA", "socios"}


class ClienteReceita:
    def __init__(self, pasta_cache: Path, offline: bool = False, intervalo: float = 1.0,
                 tentativas: int = 3, avisar=print):
        self.pasta = Path(pasta_cache)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.intervalo = intervalo
        self.tentativas = tentativas
        self.avisar = avisar
        self._ultima = 0.0

    def _arquivo(self, cnpj: str) -> Path:
        return self.pasta / f"{cnpj}.json"

    def consultar(self, cnpj: str) -> dict | None:
        """Devolve {"status", "consultado_em", "dados"} ou None se não houver resposta."""
        arq = self._arquivo(cnpj)
        if arq.exists():
            return json.loads(arq.read_text(encoding="utf-8"))
        if self.offline:
            return None
        resposta = self._baixar(cnpj)
        if resposta is not None:
            arq.write_text(json.dumps(resposta, ensure_ascii=False, indent=1), encoding="utf-8")
        return resposta

    def _baixar(self, cnpj: str) -> dict | None:
        """Tenta cada provedor; 404 só vale se todos disserem 404."""
        statuses = []
        for nome, url in PROVEDORES:
            status, dados = self._baixar_de(nome, url.format(cnpj=cnpj), cnpj)
            statuses.append(status)
            if status == 200:
                if nome == "opencnpj":
                    dados = de_opencnpj(dados)
                dados = {k: v for k, v in dados.items() if k not in CAMPOS_DESCARTADOS}
                return {"status": 200, "provedor": nome, "consultado_em": date.today().isoformat(),
                        "dados": dados}
        if statuses and all(s == 404 for s in statuses):
            return {"status": 404, "provedor": "+".join(n for n, _ in PROVEDORES),
                    "consultado_em": date.today().isoformat(), "dados": None}
        return None  # falha transitória: não grava cache, tenta de novo na próxima execução

    def _baixar_de(self, nome: str, url: str, cnpj: str) -> tuple[int | None, dict | None]:
        import requests  # só o modo online precisa da biblioteca

        espera = 5.0
        for tentativa in range(1, self.tentativas + 1):
            pausa = self.intervalo - (time.monotonic() - self._ultima)
            if pausa > 0:
                time.sleep(pausa)
            self._ultima = time.monotonic()
            try:
                r = requests.get(url, timeout=15)
            except requests.RequestException as e:
                self.avisar(f"  [{cnpj}] {nome}: falha de rede ({type(e).__name__})")
                time.sleep(espera)
                espera *= 2
                continue
            if r.status_code == 200:
                return 200, r.json()
            if r.status_code in (400, 404):
                return r.status_code, None
            # 429 (limite) e 5xx (instabilidade): espera crescente e tenta de novo.
            self.avisar(f"  [{cnpj}] {nome}: HTTP {r.status_code}, nova tentativa em {espera:.0f}s")
            time.sleep(espera)
            espera *= 2
        return None, None


def de_opencnpj(d: dict) -> dict:
    """Converte a resposta da OpenCNPJ para o formato da BrasilAPI (o adaptador fica aqui,
    e o resto do pipeline continua conhecendo um formato só)."""
    principal = next((c for c in d.get("cnaes") or [] if c.get("is_principal")), {})
    secundarios = [c for c in d.get("cnaes") or [] if not c.get("is_principal")]
    tel = next((t for t in d.get("telefones") or [] if not t.get("is_fax")), {})
    return {
        "cnpj": d.get("cnpj", ""), "razao_social": d.get("razao_social", ""),
        "nome_fantasia": d.get("nome_fantasia", ""),
        "descricao_identificador_matriz_filial": (d.get("matriz_filial") or "").upper(),
        "descricao_situacao_cadastral": (d.get("situacao_cadastral") or "").upper(),
        "data_situacao_cadastral": d.get("data_situacao_cadastral", ""),
        "data_inicio_atividade": d.get("data_inicio_atividade", ""),
        "natureza_juridica": d.get("natureza_juridica", ""),
        "porte": re.sub(r"\s*\(.*\)", "", d.get("porte_empresa") or "").upper(),
        "cnae_fiscal": principal.get("codigo") or d.get("cnae_principal", ""),
        "cnae_fiscal_descricao": principal.get("descricao", ""),
        "cnaes_secundarios": [{"codigo": c.get("codigo"), "descricao": c.get("descricao")}
                              for c in secundarios],
        "descricao_tipo_de_logradouro": d.get("tipo_logradouro", ""),
        "logradouro": d.get("logradouro", ""), "numero": d.get("numero", ""),
        "complemento": d.get("complemento", ""), "bairro": d.get("bairro", ""),
        "municipio": d.get("municipio", ""), "uf": d.get("uf", ""), "cep": d.get("cep", ""),
        "email": d.get("email") or None,
        "ddd_telefone_1": f"{tel.get('ddd', '')}{tel.get('numero', '')}",
    }


def para_canonico(dados: dict) -> dict:
    """JSON da BrasilAPI -> chaves do esquema canônico."""
    tipo_logr = (dados.get("descricao_tipo_de_logradouro") or "").strip()
    logr = (dados.get("logradouro") or "").strip()
    if tipo_logr and logr and not logr.upper().startswith(tipo_logr.upper() + " "):
        logr = f"{tipo_logr} {logr}"
    return {
        "cnpj": dados.get("cnpj", ""),
        "razao_social": dados.get("razao_social", ""),
        "nome_fantasia": dados.get("nome_fantasia", ""),
        "tipo_estabelecimento": dados.get("descricao_identificador_matriz_filial")
                                or str(dados.get("identificador_matriz_filial", "")),
        "data_abertura": dados.get("data_inicio_atividade", ""),
        "situacao_cadastral": dados.get("descricao_situacao_cadastral", ""),
        "data_situacao_cadastral": dados.get("data_situacao_cadastral", ""),
        "natureza_juridica": dados.get("natureza_juridica", ""),
        "porte": dados.get("porte", ""),
        "cnae_principal": str(dados.get("cnae_fiscal") or ""),
        "cnae_principal_descricao": dados.get("cnae_fiscal_descricao", ""),
        "cnaes_secundarios": [str(c.get("codigo", "")) for c in dados.get("cnaes_secundarios") or []
                              if c.get("codigo")],
        "logradouro": logr,
        "numero": dados.get("numero", ""),
        "complemento": dados.get("complemento", ""),
        "bairro": dados.get("bairro", ""),
        "municipio": dados.get("municipio", ""),
        "uf": dados.get("uf", ""),
        "cep": dados.get("cep", ""),
        "email": dados.get("email") or "",
        "telefone": dados.get("ddd_telefone_1", ""),
    }
