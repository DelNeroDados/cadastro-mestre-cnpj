"""Gera a base de demonstração, com dados inventados.

Os cartões reais são de clientes, então a demo monta uma carteira fictícia com
as três fontes (receita, cartao, erp) e erros parecidos com os que encontrei
nos dados reais. Semente fixa: sempre gera a mesma base.
Os CPFs nos nomes de MEI têm DV inválido de propósito."""
from __future__ import annotations

import csv
import json
import random
import string
from datetime import date, timedelta
from pathlib import Path

from .validadores import completar_dv, formatar_cnpj

DATA_DEMO = date(2026, 11, 1)  # "hoje" da demo, para os resultados serem reproduzíveis

ATIVIDADES = [
    ("2013402", "Fabricação de adubos e fertilizantes, exceto organo-minerais", "FERTILIZANTES"),
    ("4711302", "Comércio varejista de mercadorias em geral, com predominância de produtos "
                "alimentícios - supermercados", "SUPERMERCADOS"),
    ("1091101", "Fabricação de produtos de panificação industrial", "PANIFICACAO"),
    ("4930202", "Transporte rodoviário de carga, exceto produtos perigosos e mudanças, "
                "intermunicipal, interestadual e internacional", "TRANSPORTES"),
    ("6201501", "Desenvolvimento de programas de computador sob encomenda", "SISTEMAS"),
    ("2229399", "Fabricação de artefatos de material plástico para outros usos não "
                "especificados anteriormente", "PLASTICOS"),
    ("2539001", "Serviços de usinagem, tornearia e solda", "USINAGEM"),
    ("4744099", "Comércio varejista de materiais de construção em geral", "MATERIAIS DE CONSTRUCAO"),
    ("8630503", "Atividade médica ambulatorial restrita a consultas", "CLINICA MEDICA"),
    ("2063100", "Fabricação de cosméticos, produtos de perfumaria e de higiene pessoal", "COSMETICOS"),
    ("1412601", "Confecção de peças do vestuário, exceto roupas íntimas e as confeccionadas "
                "sob medida", "CONFECCOES"),
    ("4639701", "Comércio atacadista de produtos alimentícios em geral", "DISTRIBUIDORA DE ALIMENTOS"),
]
PREFIXOS = ["AGRO", "METAL", "TECNO", "BIO", "NOVA", "SUPER", "PRIME", "VALE", "ALFA",
            "TERRA", "LUZ", "RIO", "SERRA", "MAXI", "UNI", "ECO", "FORTE", "ATLAS"]
NUCLEOS = ["PLAST", "SUL", "NORTE", "VERDE", "LOG", "MED", "TEX", "FOOD", "TECH", "MAQ",
           "QUIMICA", "PAPEL", "VIDA", "BRASIL", "CAMPO", "MAR"]
NOMES = ["ANA", "BRUNO", "CARLA", "DANIEL", "ELISA", "FABIO", "GABRIELA", "HELIO", "IRENE",
         "JULIO", "KARINA", "LUCAS", "MARTA", "NELSON", "OLIVIA", "PAULO", "RITA", "SERGIO"]
SOBRENOMES = ["ALMEIDA", "BARROS", "CARDOSO", "DIAS", "FERRAZ", "GOMES", "LIMA", "MOURA",
              "NUNES", "PRADO", "RAMOS", "SOARES", "TEIXEIRA", "VIEIRA"]
# (município, UF, faixa de CEP de 5 dígitos, DDD)
CIDADES = [
    ("JAU", "SP", (17200, 17229), "14"), ("BAURU", "SP", (17000, 17099), "14"),
    ("SAO PAULO", "SP", (1000, 5999), "11"), ("CAMPINAS", "SP", (13000, 13139), "19"),
    ("RIBEIRAO PRETO", "SP", (14000, 14114), "16"), ("BELO HORIZONTE", "MG", (30000, 31999), "31"),
    ("CURITIBA", "PR", (80000, 82999), "41"), ("PORTO ALEGRE", "RS", (90000, 91999), "51"),
    ("GOIANIA", "GO", (74000, 74899), "62"), ("SALVADOR", "BA", (40000, 42599), "71"),
    ("RECIFE", "PE", (50000, 52999), "81"), ("FLORIANOPOLIS", "SC", (88000, 88099), "48"),
    ("RIO DE JANEIRO", "RJ", (20000, 23799), "21"),
]
RUAS = ["SETE DE SETEMBRO", "QUINZE DE NOVEMBRO", "DAS PALMEIRAS", "BRASIL", "DOS ANDRADAS",
        "SANTOS DUMONT", "DAS INDUSTRIAS", "JOAO PESSOA", "DOM PEDRO II", "DOS BANDEIRANTES"]
BAIRROS = ["CENTRO", "JARDIM AMERICA", "VILA NOVA", "DISTRITO INDUSTRIAL", "JARDIM EUROPA",
           "BELA VISTA", "SANTA CRUZ", "PARQUE DAS NACOES"]


def _cpf_ficticio(rnd: random.Random) -> str:
    """11 dígitos com DV errado de propósito: nunca é um CPF válido."""
    base = [rnd.randint(0, 9) for _ in range(9)]
    s1 = sum(d * p for d, p in zip(base, range(10, 1, -1)))
    dv1 = 0 if s1 % 11 < 2 else 11 - s1 % 11
    return "".join(map(str, base)) + str((dv1 + 1) % 10) + str(rnd.randint(0, 9))


def _endereco(rnd: random.Random, cidade=None) -> dict:
    mun, uf, (ini, fim), ddd = cidade or rnd.choice(CIDADES)
    return {
        "logradouro": f"{rnd.choice(['RUA', 'AVENIDA'])} {rnd.choice(RUAS)}",
        "numero": str(rnd.randint(10, 3500)), "bairro": rnd.choice(BAIRROS),
        "municipio": mun, "uf": uf, "cep": f"{rnd.randint(ini, fim):05d}{rnd.randint(0, 999):03d}",
        "ddd": ddd,
    }


def _empresas(rnd: random.Random) -> list[dict]:
    empresas, usados = [], set()
    for i in range(46):
        cnae, desc, segmento = rnd.choice(ATIVIDADES)
        alfanumerico = i < 3  # aberta depois de jul/2026: CNPJ alfanumérico
        while True:
            if alfanumerico:
                raiz = "".join(rnd.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            else:
                raiz = f"{rnd.randint(1, 99_999_999):08d}"
            if raiz not in usados:
                usados.add(raiz)
                break
        mei = i % 9 == 4
        if mei:
            razao = f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)} {rnd.choice(SOBRENOMES)} {_cpf_ficticio(rnd)}"
            natureza, porte, fantasia = "Empresário (Individual)", "MICRO EMPRESA", f"{segmento.title()} {rnd.choice(NOMES).title()}"
        else:
            marca = rnd.choice(PREFIXOS) + rnd.choice(NUCLEOS)
            razao = f"{marca} {segmento} {rnd.choice(['LTDA', 'LTDA', 'LTDA', 'S.A.', 'EIRELI'])}"
            natureza = "Sociedade Anônima Fechada" if "S.A." in razao else "Sociedade Empresária Limitada"
            porte = rnd.choice(["MICRO EMPRESA", "EMPRESA DE PEQUENO PORTE", "DEMAIS"])
            fantasia = marca if rnd.random() < 0.8 else ""
        abertura = (date(2026, 7, 15) + timedelta(days=rnd.randint(0, 90)) if alfanumerico
                    else date(1995, 1, 1) + timedelta(days=rnd.randint(0, 10500)))
        qtd_estab = 1 + (rnd.random() < 0.15) * rnd.randint(1, 2) if not mei else 1
        cidade_matriz = rnd.choice(CIDADES)
        for ordem in range(1, qtd_estab + 1):
            cnpj = completar_dv(f"{raiz}{ordem:04d}")
            end = _endereco(rnd, cidade_matriz if ordem == 1 else None)
            situacao, data_sit = "ATIVA", abertura
            sorte = rnd.random()
            if sorte < 0.06:
                situacao, data_sit = "BAIXADA", DATA_DEMO - timedelta(days=rnd.randint(30, 300))
            elif sorte < 0.10:
                situacao, data_sit = "INAPTA", DATA_DEMO - timedelta(days=rnd.randint(30, 500))
            empresas.append({
                "cnpj": cnpj, "razao_social": razao, "nome_fantasia": fantasia.upper(),
                "matriz": ordem == 1, "abertura": abertura, "situacao": situacao,
                "data_situacao": data_sit, "natureza": natureza, "porte": porte, "cnae": cnae,
                "cnae_desc": desc, "secundarios": rnd.sample([a for a in ATIVIDADES if a[0] != cnae],
                                                             rnd.randint(0, 2)),
                "end": end, "endereco_antigo": _endereco(rnd) if rnd.random() < 0.15 else None,
                "email": f"contato@{razao.split()[0].lower()}.com.br" if not mei else "",
                "telefone": f"{end['ddd']}3{rnd.randint(1000000, 9999999)}",
            })
    return empresas


# Receita: mesmo formato do cache real
def _receita(e: dict) -> dict:
    tipo, logr = e["end"]["logradouro"].split(" ", 1)
    return {
        "status": 200, "consultado_em": (DATA_DEMO - timedelta(days=2)).isoformat(),
        "dados": {
            "cnpj": e["cnpj"], "identificador_matriz_filial": 1 if e["matriz"] else 2,
            "descricao_identificador_matriz_filial": "MATRIZ" if e["matriz"] else "FILIAL",
            "razao_social": e["razao_social"], "nome_fantasia": e["nome_fantasia"],
            "descricao_situacao_cadastral": e["situacao"],
            "data_situacao_cadastral": e["data_situacao"].isoformat(),
            "data_inicio_atividade": e["abertura"].isoformat(), "natureza_juridica": e["natureza"],
            "porte": e["porte"], "cnae_fiscal": int(e["cnae"]), "cnae_fiscal_descricao": e["cnae_desc"],
            "cnaes_secundarios": [{"codigo": int(c), "descricao": d} for c, d, _ in e["secundarios"]],
            "descricao_tipo_de_logradouro": tipo, "logradouro": logr, "numero": e["end"]["numero"],
            "complemento": "", "bairro": e["end"]["bairro"], "municipio": e["end"]["municipio"],
            "uf": e["end"]["uf"], "cep": e["end"]["cep"], "email": e["email"] or None,
            "ddd_telefone_1": e["telefone"],
        },
    }


# Cartões: mesmo formato que extracao.extrair_pasta devolve
def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _cartoes(rnd: random.Random, e: dict, n: int) -> list[dict]:
    saida = []
    for k in range(n):
        emissao = DATA_DEMO - timedelta(days=rnd.randint(20, 1100))
        if emissao < e["abertura"]:
            emissao = e["abertura"] + timedelta(days=5)
        end = e["end"]
        # Cartão emitido antes da mudança de endereço mostra o endereço antigo.
        if e["endereco_antigo"] and emissao < DATA_DEMO - timedelta(days=200):
            end = e["endereco_antigo"]
        situacao, data_sit = e["situacao"], e["data_situacao"]
        if situacao != "ATIVA" and emissao < e["data_situacao"]:
            situacao, data_sit = "ATIVA", e["abertura"]  # o cartão é anterior à baixa
        c = e["cnpj"]
        tipo, logr = end["logradouro"].split(" ", 1)
        saida.append({
            "arquivo": f"cartao_{c[:8]}_{k + 1}.pdf", "sha256": f"demo-{c}-{k}",
            "cnpj": formatar_cnpj(c), "data_abertura": _br(e["abertura"]),
            "tipo_estabelecimento": "MATRIZ" if e["matriz"] else "FILIAL",
            "razao_social": e["razao_social"], "nome_fantasia": e["nome_fantasia"] or "********",
            "porte": {"MICRO EMPRESA": "ME", "EMPRESA DE PEQUENO PORTE": "EPP"}.get(e["porte"], "DEMAIS"),
            "cnae_principal_texto": f"{e['cnae'][:2]}.{e['cnae'][2:4]}-{e['cnae'][4]}-{e['cnae'][5:]} - {e['cnae_desc']}",
            "cnaes_secundarios_texto": " | ".join(
                f"{s[:2]}.{s[2:4]}-{s[4]}-{s[5:]} - {d}" for s, d, _ in e["secundarios"]) or "Não informada",
            "natureza_juridica_texto": f"206-2 - {e['natureza']}",
            "logradouro": f"{'R' if tipo == 'RUA' else 'AV'} {logr}", "numero": end["numero"],
            "complemento": "********", "cep": f"{end['cep'][:2]}.{end['cep'][2:5]}-{end['cep'][5:]}",
            "bairro": end["bairro"], "municipio": end["municipio"], "uf": end["uf"],
            "email": e["email"].upper(), "telefone": f"({e['telefone'][:2]}) {e['telefone'][2:6]}-{e['telefone'][6:]}",
            "situacao_cadastral": situacao, "data_situacao_cadastral": _br(data_sit),
            "data_emissao": _br(emissao),
        })
    return saida


# ERP com erros de digitação
def _trocar_digito(rnd: random.Random, cnpj: str) -> str:
    pos = rnd.randint(0, 11)
    if not cnpj[pos].isdigit():
        pos = 11
    novo = str((int(cnpj[pos]) + rnd.randint(1, 8)) % 10)
    return cnpj[:pos] + novo + cnpj[pos + 1:]


def _variar_nome(rnd: random.Random, nome: str) -> str:
    trocas = [("INDUSTRIA", "IND"), ("COMERCIO", "COM"), (" LTDA", " LTDA."), (" LTDA", ""),
              ("S.A.", "SA"), ("TRANSPORTES", "TRANSP")]
    for de, para in rnd.sample(trocas, len(trocas)):
        if de in nome:
            return nome.replace(de, para, 1)
    return nome.title()


def _erp(rnd: random.Random, empresas: list[dict]) -> list[dict]:
    linhas, cod = [], 1000
    for i, e in enumerate(empresas):
        if i % 10 == 7:  # cerca de 10% da carteira não está no ERP
            continue
        cod += 1
        end = e["end"]
        cep = end["cep"][:5] + "-" + end["cep"][5:]
        uf = end["uf"]
        if end["cep"].startswith("0"):
            cep = str(int(end["cep"]))  # o Excel comeu o zero à esquerda
        elif i % 17 == 3:
            uf = rnd.choice([u for u in ("MG", "PR", "RJ") if u != uf])  # UF trocada
        email = e["email"] or (f"{e['razao_social'].split()[0].lower()}@gmail.com" if i % 3 else "")
        if i % 13 == 5:
            email = email.replace(".com.br", "").replace(".com", "")  # sem domínio
        tel = e["telefone"]
        if i % 11 == 2:
            tel = tel[2:]  # sem DDD
        atualizado = DATA_DEMO - timedelta(days=rnd.randint(10, 1600))
        cnpj = formatar_cnpj(e["cnpj"])
        nome = e["razao_social"]
        if i % 8 == 1:
            nome = _variar_nome(rnd, nome)
        if i % 12 == 6:
            cnpj = formatar_cnpj(_trocar_digito(rnd, e["cnpj"]))  # dígito trocado
        if i == 30:
            # Dígito trocado + nome abreviado + endereço antigo: o score fica no meio
            # do caminho e o par vai para a fila de revisão do Steward.
            nome = _variar_nome(rnd, nome)
            antigo = _endereco(rnd)
            cep, uf, end = antigo["cep"][:5] + "-" + antigo["cep"][5:], antigo["uf"], antigo
        if i == 20:
            cnpj = ""  # cadastrado sem CNPJ
        linha = {
            "cod_cliente": cod, "cnpj_cpf": cnpj, "razao_social": nome,
            "nome_fantasia": e["nome_fantasia"].title(), "endereco": end["logradouro"].title(),
            "numero": end["numero"], "bairro": end["bairro"].title(), "cidade": end["municipio"].title(),
            "uf": uf, "cep": cep, "email": email, "telefone": tel,
            "dt_cadastro": _br(atualizado - timedelta(days=rnd.randint(0, 900))),
            "dt_atualizacao": _br(atualizado),
        }
        linhas.append(linha)
        if i % 15 == 9:  # o mesmo cliente cadastrado de novo, por outro vendedor
            cod += 1
            linhas.append({**linha, "cod_cliente": cod, "razao_social": _variar_nome(rnd, nome),
                           "email": "", "dt_atualizacao": _br(atualizado + timedelta(days=40))})

    # Um CNPJ válido que a Receita não conhece, e um cliente sem correspondência.
    fantasma = completar_dv("998877660001")
    cod += 1
    linhas.append({"cod_cliente": cod, "cnpj_cpf": formatar_cnpj(fantasma),
                   "razao_social": "COMERCIAL FANTASMA LTDA", "nome_fantasia": "", "endereco": "Rua A",
                   "numero": "1", "bairro": "Centro", "cidade": "Bauru", "uf": "SP", "cep": "17010-000",
                   "email": "", "telefone": "", "dt_cadastro": _br(DATA_DEMO + timedelta(days=30)),
                   "dt_atualizacao": _br(DATA_DEMO - timedelta(days=5))})
    cod += 1
    linhas.append({"cod_cliente": cod, "cnpj_cpf": "12.345.678/0001-00",
                   "razao_social": "OFICINA DO ZE", "nome_fantasia": "", "endereco": "", "numero": "",
                   "bairro": "", "cidade": "Bauru", "uf": "SP", "cep": "", "email": "ze@oficina",
                   "telefone": "99999999", "dt_cadastro": _br(DATA_DEMO - timedelta(days=2000)),
                   "dt_atualizacao": _br(DATA_DEMO - timedelta(days=2000))})
    return linhas


def gerar(pasta: Path, semente: int = 42) -> dict:
    rnd = random.Random(semente)
    pasta = Path(pasta)
    (pasta / "receita").mkdir(parents=True, exist_ok=True)
    for antigo in (pasta / "receita").glob("*.json"):
        antigo.unlink()

    empresas = _empresas(rnd)
    for e in empresas:
        (pasta / "receita" / f"{e['cnpj']}.json").write_text(
            json.dumps(_receita(e), ensure_ascii=False, indent=1), encoding="utf-8")
    # A Receita respondeu 404 para o CNPJ fantasma: o "não existe" também fica no cache.
    (pasta / "receita" / f"{completar_dv('998877660001')}.json").write_text(
        json.dumps({"status": 404, "consultado_em": DATA_DEMO.isoformat(), "dados": None}),
        encoding="utf-8")

    cartoes = []
    for i, e in enumerate(empresas):
        # As empresas com CNPJ digitado errado no ERP (i % 12 == 6, i == 20) quase
        # sempre têm cartão, para o match ter com quem comparar. A de i == 42 fica
        # sem: é o caso que acaba em quarentena.
        if rnd.random() < 0.75 or (i % 12 == 6 and i != 42) or i == 20:
            cartoes += _cartoes(rnd, e, rnd.choice([1, 1, 2, 3, 4]))
    rnd.shuffle(cartoes)
    (pasta / "cartoes_extraidos.json").write_text(
        json.dumps(cartoes, ensure_ascii=False, indent=1), encoding="utf-8")

    erp = _erp(rnd, empresas)
    with open(pasta / "clientes_erp.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(erp[0]), delimiter=";")
        w.writeheader()
        w.writerows(erp)
    return {"empresas": len(empresas), "cartoes": len(cartoes), "erp": len(erp)}
