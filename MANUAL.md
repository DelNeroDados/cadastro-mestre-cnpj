# Manual do usuário

Como instalar, rodar e usar os resultados. Para as seções 1 a 6 não precisa saber Python; da 7 em diante é para quem vai mexer nas regras ou no código.

**Sumário**

1. [Visão geral](#1-visão-geral)
2. [Instalação](#2-instalação)
3. [Rodando a demonstração](#3-rodando-a-demonstração)
4. [Rodando com dados reais](#4-rodando-com-dados-reais)
5. [Os arquivos gerados](#5-os-arquivos-gerados)
6. [Como ler o relatório](#6-como-ler-o-relatório)
7. [O trabalho do Data Steward](#7-o-trabalho-do-data-steward)
8. [Alterando as regras](#8-alterando-as-regras)
9. [O que acontece por dentro](#9-o-que-acontece-por-dentro)
10. [Problemas comuns](#10-problemas-comuns)
11. [Glossário](#11-glossário)

---

## 1. Visão geral

Uma empresa tem informações sobre os seus clientes (pessoas jurídicas) espalhadas em três lugares:

| Fonte | Exemplo | Problema típico |
|---|---|---|
| **Cartões CNPJ em PDF** | O "Comprovante de Inscrição e de Situação Cadastral" que o cliente manda | São fotos de um dia: um cartão de 2022 não sabe que a empresa mudou de endereço em 2024 |
| **Receita Federal** | Consulta online pelo CNPJ | É a fonte oficial, mas não tem o contato comercial do cliente |
| **ERP** (sistema da empresa) | Planilha de clientes exportada do sistema | Digitado à mão: CNPJ com dígito errado, cliente cadastrado duas vezes, CEP faltando dígito |

O programa:

1. **Lê** as três fontes e coloca todas no mesmo formato (o "esquema canônico").
2. **Verifica a qualidade** de cada registro com 20 regras (CNPJ válido? CEP pertence à UF? Informação recente?) e anota cada falha.
3. **Junta** os registros que são a mesma empresa (MDM) e monta um **cadastro mestre**: uma linha por estabelecimento, com o melhor valor de cada campo e a origem de cada valor anotada.
4. **Compara** os cartões e o ERP com a Receita para medir quanto cada fonte acerta.
5. **Gera** um relatório visual, um banco SQLite consultável e planilhas de trabalho.

Dois modos de execução:

- **Demonstração (`demo`)**: cria uma carteira de clientes fictícia, com defeitos parecidos com os reais, e roda tudo sem internet. É o modo para mostrar o projeto.
- **Real (`real`)**: lê os PDFs de verdade e consulta a Receita pela internet. Os resultados ficam só no seu computador.

---

## 2. Instalação

### 2.1. O que é preciso

- Windows, Linux ou macOS
- **Python 3.10 ou mais novo**
- Internet apenas para instalar as bibliotecas e para o modo real

### 2.2. Windows: o jeito mais fácil

Dê dois cliques em **`Iniciar.bat`**. Ele:

1. procura o Python, primeiro o portátil em `..\.python_embed\` (o deste computador), depois o comando `py`, depois `python`;
2. instala as bibliotecas que faltarem (só na primeira vez; leva um ou dois minutos);
3. roda a demonstração e abre o relatório no navegador.

Se aparecer "Não encontrei o Python", instale em <https://www.python.org/downloads/> e **marque a opção "Add python.exe to PATH"** durante a instalação.

### 2.3. Instalação manual (qualquer sistema)

Abra um terminal **na pasta do projeto** e rode:

```bash
pip install -r requirements.txt
```

Bibliotecas instaladas e para que servem:

| Biblioteca | Uso |
|---|---|
| pandas | Tabelas em memória: todas as etapas trabalham com elas |
| PyYAML | Lê os arquivos de regras em `config/` |
| RapidFuzz | Mede semelhança entre nomes de empresas (match do MDM) |
| Jinja2 | Monta o relatório HTML |
| pdfplumber | Lê o texto e a posição das palavras nos PDFs (só modo real) |
| requests | Consulta as APIs da Receita (só modo real) |
| pytest | Roda os testes automatizados |

> **Neste computador** o Python é o portátil em `C:\Users\...\Py_Projetos\.python_embed\python.exe`, que não está no PATH. Nos comandos deste manual, troque `python` por `..\.python_embed\python.exe`, ou simplesmente use o `Iniciar.bat`.

---

## 3. Rodando a demonstração

```bash
python executar.py demo
```

Passos:

1. **Gera a base fictícia** em `dados_demo/`:
   - `receita/`: um arquivo JSON por CNPJ, no mesmo formato que a API real devolve;
   - `cartoes_extraidos.json`: 93 cartões "já lidos", alguns antigos;
   - `clientes_erp.csv`: 51 linhas de ERP com defeitos de digitação.
2. **Roda o pipeline completo** (seção 9) sem acessar a internet.
3. **Grava os resultados** em `saida_demo/` e mostra um resumo no terminal:

```
================================================================
 Registros de origem ......... 194  {'cartao': 93, 'erp': 51, 'receita': 50}
 Cadastro mestre ............. 51 estabelecimentos (46 empresas)
 Redundância eliminada ....... 73.4%
 Índice de qualidade ......... fontes 97.5 -> mestre 99.84
 Não conformidades ........... 122 (6 críticas)
 Fila de revisão do Steward .. 1 pares
 Clientes em risco ........... 5 (CNPJ não ativo)
================================================================
```

A base fictícia é gerada sempre igual (semente fixa) e a "data de hoje" da demo é fixa em **01/11/2026**. Por isso os números acima se repetem em qualquer computador, e os testes conferem exatamente esses valores.

**Defeitos que a base fictícia contém de propósito** (e que o pipeline precisa encontrar):

| Defeito | Onde aparece | Quem detecta |
|---|---|---|
| CNPJ com um dígito trocado | ERP | regra DQ002 + match por similaridade |
| Cliente sem CNPJ | ERP | regra DQ001 + match por nome e CEP |
| Mesmo cliente cadastrado duas vezes | ERP | regra DQ003 + MDM |
| CEP que perdeu o zero à esquerda no Excel (`01310100` → `1310100`) | ERP | regra DQ013 |
| UF que não bate com o CEP | ERP | regra DQ015 |
| E-mail sem domínio, telefone sem DDD | ERP | regras DQ018 e DQ019 |
| Cadastro sem atualização há anos | ERP e cartões | regra DQ020 |
| Cartão antigo dizendo "ATIVA" para empresa já baixada | cartões | reconciliação com a Receita |
| Empresa que mudou de endereço depois do cartão | cartões | reconciliação + sobrevivência |
| CNPJ válido que a Receita não conhece | ERP | registro mestre "SEM_FONTE_AUTORITATIVA" |
| Cliente sem correspondência alguma | ERP | quarentena |
| CNPJs no novo formato alfanumérico | todas | validador de CNPJ |

Os nomes são combinações inventadas e os CPFs que aparecem nos nomes de empresários individuais têm dígito verificador propositalmente inválido, então não coincidem com o CPF de ninguém.

---

## 4. Rodando com dados reais

### 4.1. Só com cartões CNPJ

Coloque os PDFs em uma ou mais pastas e rode:

```bash
python executar.py real --pdfs extracted_cnpjs no_extracted_cnpjs
```

No Windows: `Iniciar.bat real` (usa essas duas pastas).

Etapas:

1. **Leitura dos PDFs.** Cada arquivo é lido e o resultado fica guardado em `.cache/extracao/`, identificado pelo conteúdo do arquivo (hash SHA-256), e não pelo nome. A primeira leitura leva cerca de 1 segundo por PDF; as seguintes são instantâneas, mesmo que o arquivo seja renomeado.
2. **Consulta à Receita.** Para cada CNPJ válido encontrado, consulta a **BrasilAPI**; se ela falhar ou disser "não encontrado", consulta a **OpenCNPJ**. A resposta fica em `.cache/receita/<cnpj>.json`, com a data da consulta e o provedor que respondeu. Leva de 1 a 3 segundos por CNPJ, mais se a API pedir para esperar (HTTP 429).
3. **Pipeline completo** e gravação em `saida_real/`.

Nenhum PDF é movido, renomeado ou apagado. Os que não puderam ser lidos aparecem no relatório com o motivo.

### 4.2. Incluindo uma planilha do ERP

```bash
python executar.py real --pdfs extracted_cnpjs --erp clientes.csv
```

O arquivo precisa ser **CSV separado por ponto e vírgula**, em UTF-8, com estas colunas (a ordem não importa):

| Coluna | Obrigatória | Exemplo |
|---|---|---|
| `cod_cliente` | sim | `1001` |
| `cnpj_cpf` | sim (pode estar vazia em alguma linha) | `11.222.333/0001-81` |
| `razao_social` | sim | `ALFA PLASTICOS LTDA` |
| `nome_fantasia` | sim (pode estar vazia) | `Alfa Plast` |
| `endereco` | sim | `Avenida das Industrias` |
| `numero` | sim | `1500` |
| `bairro` | sim | `Distrito Industrial` |
| `cidade` | sim | `Jau` |
| `uf` | sim | `SP` |
| `cep` | sim | `17209-832` |
| `email` | sim (pode estar vazia) | `compras@alfa.com.br` |
| `telefone` | sim (pode estar vazia) | `(14) 3621-0000` |
| `dt_atualizacao` | sim | `15/08/2026` |
| `dt_cadastro` | não (é ignorada) | `02/01/2020` |

Se faltar alguma coluna obrigatória, o programa para e diz quais estão faltando. Para ver um exemplo completo, rode a demo e abra `dados_demo/clientes_erp.csv`.

### 4.3. Sem internet

```bash
python executar.py real --pdfs extracted_cnpjs --offline
```

Usa só o que já está em `.cache/receita/`. CNPJs que nunca foram consultados aparecem como "sem_resposta".

### 4.4. Forçar uma nova consulta à Receita

O cache não expira sozinho. Para atualizar um CNPJ, apague o arquivo dele em `.cache/receita/`; para atualizar todos, apague a pasta inteira. Na próxima execução eles são consultados de novo.

---

## 5. Os arquivos gerados

Tudo vai para `saida_demo/` (demonstração) ou `saida_real/` (dados reais). Cada execução **substitui** os arquivos da anterior.

| Arquivo | Conteúdo | Para quem |
|---|---|---|
| `relatorio_qualidade.html` | Relatório visual (seção 6). Abre em qualquer navegador, funciona offline | Gestor, apresentação |
| `RESUMO.md` | Os mesmos números em texto, legível no GitHub | Quem visita o repositório |
| `cadastro_mestre.csv` | O cadastro mestre: uma linha por estabelecimento | Quem usa o dado |
| `nao_conformidades.csv` | Uma linha por registro reprovado em uma regra, com a ação recomendada | Data Steward |
| `fila_revisao_steward.csv` | Pares que o sistema não teve certeza se são a mesma empresa | Data Steward |
| `mdm.sqlite` | Banco com todas as tabelas e views (abaixo) | Analista |

Os CSVs usam `;` como separador e abrem direto no Excel com acentos corretos.

**Dados pessoais:** o HTML e o RESUMO.md mascaram nome e CPF de empresário individual (`M. S. L. [CPF OCULTO]`), e-mail (`c***@empresa.com.br`) e telefone (`(14) ****-**67`). Os CSVs e o SQLite guardam o dado completo, porque são bases de trabalho; por isso `saida_real/` nunca vai para o GitHub.

### 5.1. Tabelas do `mdm.sqlite`

| Tabela | Uma linha por... |
|---|---|
| `silver_registros` | registro de origem, já no formato padrão (todas as fontes juntas) |
| `dq_resultados` | regra × fonte: quantos avaliados, quantas falhas |
| `dq_nao_conformidades` | registro reprovado em uma regra |
| `dq_scorecard` | dimensão × fonte: % de conformidade e se bateu a meta |
| `dq_resultados_mestre` | regra aplicada ao cadastro mestre |
| `mdm_golden` | registro mestre (o mesmo conteúdo de `cadastro_mestre.csv`) |
| `mdm_linhagem` | campo de cada registro mestre: de qual fonte veio o valor e por qual critério |
| `mdm_crosswalk` | registro de origem: a qual registro mestre ele foi ligado e como |
| `mdm_hierarquia` | empresa (raiz do CNPJ): matriz e quantidade de filiais |
| `mdm_fila_revisao` | par aguardando decisão humana |
| `rec_acuracia` | fonte × campo: % de valores iguais aos da Receita |
| `rec_divergencias` | valor diferente do da Receita |
| `doc_rejeitados` | PDF que não pôde ser lido, com o motivo |
| `receita_sem_dados` | CNPJ que a Receita não encontrou ou não respondeu |

Views prontas (consultas salvas):

| View | Mostra |
|---|---|
| `vw_scorecard` | dimensões abaixo da meta primeiro |
| `vw_pendencias_steward` | não conformidades agrupadas por regra, das mais graves para as mais leves |
| `vw_clientes_em_risco` | clientes com CNPJ baixado, inapto, suspenso ou nulo |
| `vw_mestre_sem_validacao` | registros mestres que a Receita não confirmou |
| `vw_filiais_sem_matriz` | empresas com filial no cadastro e matriz fora dele |
| `vw_golden_com_origem` | cadastro mestre com a fonte do CEP, do e-mail e da situação |
| `vw_conflitos_por_campo` | campos em que as fontes mais discordam |

### 5.2. Como consultar o banco

1. Instale o **DB Browser for SQLite** (<https://sqlitebrowser.org>, gratuito) ou o **DBeaver**.
2. Abra `saida_demo/mdm.sqlite`.
3. Na aba de SQL, cole uma consulta. O arquivo `sql/consultas_steward.sql` tem sete prontas, por exemplo:

```sql
-- Cartões que ainda dizem ATIVA para empresas que a Receita já baixou
SELECT d.cnpj, d.id_origem AS arquivo, d.data_referencia_fonte AS emitido_em,
       d.valor_fonte AS situacao_no_cartao, d.valor_receita AS situacao_hoje
FROM rec_divergencias d
WHERE d.campo = 'situacao_cadastral' AND d.fonte = 'cartao';
```

---

## 6. Como ler o relatório

Abra `relatorio_qualidade.html`. De cima para baixo:

**Cartões de números.** O resumo da execução. Os dois mais importantes:
- *Redundância eliminada*: quantos registros de origem eram, na verdade, repetições da mesma empresa;
- *Índice de qualidade fontes → mestre*: a nota das fontes antes e do cadastro mestre depois. Se o segundo número não for maior, algo está errado no MDM.

**Conformidade por dimensão.** Uma barra por dimensão de qualidade; a marca vertical é a meta. "Abaixo da meta" significa que aquela dimensão precisa de plano de ação. Passe o mouse sobre a barra para ver quantas verificações foram feitas. A tabela logo abaixo abre o mesmo número por fonte; "n/a" quer dizer que a regra não se aplica àquela fonte.

**Índice por fonte.** A nota de cada fonte (0 a 100), ponderada pela gravidade das regras. A última barra é o cadastro mestre.

**Regras com falhas.** Cada regra que reprovou algum registro, com a severidade, quantos falharam e a ação recomendada. Regras marcadas como "alerta de negócio" (como empresa não ativa) aparecem aqui, mas não descontam pontos do índice: o dado está correto, o cliente é que é problemático.

**Como os registros foram casados.** Quantos registros entraram no cadastro mestre pelo CNPJ idêntico, quantos por semelhança, quantos esperam o Steward e quantos ficaram em quarentena.

**Campos em que as fontes mais discordam.** Onde as fontes têm valores diferentes para a mesma empresa. Campo com muito conflito é candidato a uma regra de sobrevivência específica.

**Acurácia contra a Receita.** Para cada campo, o percentual de valores iguais aos da Receita. O ▲ marca valores abaixo de 95%. Nos cartões, acurácia baixa em endereço geralmente quer dizer documento antigo, não erro.

**Fila do Data Steward e Quarentena.** Os casos que precisam de uma pessoa (seção 7).

**Clientes com CNPJ não ativo.** Lista para a área comercial agir.

**Documentos que não puderam ser lidos.** Só no modo real. Motivos possíveis:

| Motivo | Significado | O que fazer |
|---|---|---|
| `imagem_sem_texto` | PDF digitalizado (foto do papel) | Pedir o cartão original ao cliente ou aplicar OCR |
| `fonte_sem_mapa_unicode` | O PDF tem texto, mas em códigos que não viram letras | Idem |
| `pouco_texto` | Digitalização com marca d'água ou texto parcial | Idem |
| `outro_documento` | Tem texto, mas não é um cartão CNPJ (ex.: certidão da Junta) | Nada, se estiver na pasta por engano |
| `erro_leitura` | Arquivo corrompido ou protegido por senha | Pedir uma nova cópia |

---

## 7. O trabalho do Data Steward

### 7.1. Tratar as não conformidades

1. Abra `nao_conformidades.csv` no Excel (ou a view `vw_pendencias_steward`).
2. Filtre por `severidade` e comece pelas **críticas**, depois as **altas**.
3. Cada linha diz a fonte, o registro (`id_origem`: código do cliente no ERP ou nome do arquivo do cartão), o valor encontrado e a `acao_recomendada`.
4. Corrija **no sistema de origem** (no ERP, por exemplo), nunca no CSV de saída: na próxima execução o pipeline lê a fonte corrigida e a não conformidade desaparece.

### 7.2. Decidir os pares duvidosos

Quando um registro sem CNPJ válido se parece com uma empresa conhecida, mas não o suficiente para o sistema ter certeza (score entre 0,65 e 0,88), ele vai para `fila_revisao_steward.csv`:

| fonte | id_origem | razao_social_origem | razao_social_sugerida | cnpj_sugerido | score | decisao |
|---|---|---|---|---|---|---|
| erp | 1030 | ALFAQUIMICA MATERIAIS DE CONSTRUCAO LTDA. | ALFAQUIMICA MATERIAIS DE CONSTRUCAO LTDA | 58461819000136 | 0.775 | |

Para decidir:

1. Abra o arquivo no Excel.
2. Na coluna `decisao`, escreva **`UNIR`** (é a mesma empresa) ou **`SEPARAR`** (não é). Opcionalmente preencha `decidido_por` e `data_decisao`, para auditoria.
3. **Salve como `decisoes_steward.csv`** na mesma pasta (`saida_demo/` ou `saida_real/`), mantendo o formato CSV com `;`.
4. Rode o pipeline de novo. Os pares decididos saem da fila; os marcados como `UNIR` entram no cadastro mestre com o método `decisao_steward`, e os `SEPARAR` vão para a quarentena.

O arquivo de decisões não é apagado entre execuções: ele é o histórico das decisões humanas. Se uma nova execução gerar novos pares, acrescente as decisões novas ao mesmo arquivo.

### 7.3. Quarentena

Registros sem CNPJ válido e sem nenhuma empresa parecida **não entram no cadastro mestre**. Para tirá-los de lá, corrija o CNPJ na fonte (ERP).

---

## 8. Alterando as regras

As regras ficam em dois arquivos de texto em `config/`. Para mudá-las não é preciso mexer em código Python.

### 8.1. Regras de qualidade (`config/regras_qualidade.yaml`)

Cada regra é um bloco como este:

```yaml
  - id: DQ013
    nome: CEP com 8 dígitos
    dimensao: validade          # completude, validade, consistencia, unicidade ou atualidade
    tipo: validador             # o tipo de verificação (lista no topo do arquivo)
    validador: cep
    campo: cep
    opcional: true              # registros com CEP vazio não são avaliados aqui
    severidade: alta            # critica, alta, media ou baixa
    acao: CEP truncado ou com dígitos a mais; conferir nos Correios.
```

Exemplo: exigir e-mail no ERP. Acrescente ao final do arquivo:

```yaml
  - id: DQ021
    nome: E-mail preenchido no ERP
    dimensao: completude
    tipo: obrigatorio
    campo: email
    fontes: [erp]
    severidade: media
    acao: Pedir o e-mail ao cliente no próximo contato.
```

Depois:

```bash
python executar.py catalogo   # atualiza docs/CATALOGO_DE_REGRAS.md
python -m pytest              # confere se o arquivo continua válido
python executar.py demo       # vê o efeito
```

Outras coisas que se ajustam no mesmo arquivo:
- `metas`: o percentual mínimo de cada dimensão;
- `pesos_severidade`: quanto cada severidade pesa no índice;
- `no_score: true`: transforma a regra em alerta, sem descontar do índice.

O teste `test_qualidade_mdm.py` falha se houver id repetido, dimensão ou validador desconhecido, ou regra sem ação.

### 8.2. Regras de MDM (`config/sobrevivencia.yaml`)

- `match.limiares.automatico` e `match.limiares.revisao`: a partir de que score o sistema une sozinho e a partir de que score manda para o Steward. Subir o `automatico` deixa o sistema mais cauteloso (mais casos na fila); descer deixa mais agressivo.
- `match.pesos`: quanto cada atributo pesa no score (nome, dígitos do CNPJ, CEP, município).
- `sobrevivencia.padrao.prioridade`: a ordem de confiança das fontes.
- `sobrevivencia.campos`: exceções por campo. Por exemplo, para o telefone o ERP vence a Receita:

```yaml
    telefone:
      prioridade: [erp, receita, cartao]
      motivo: Mesmo motivo do e-mail.
```

- `validar_antes`: quais campos precisam passar no validador para concorrer.

---

## 9. O que acontece por dentro

### 9.1. As etapas

```
Fontes ──► Silver ──► Qualidade ──► MDM ──► Qualidade do mestre ──► Saídas
                 └──────────────► Acurácia vs. Receita ──────────────┘
```

| # | Etapa | Módulo | Explicação |
|---|---|---|---|
| 1 | Leitura dos cartões | `extracao.py` | Agrupa as palavras do PDF em linhas pela altura e atribui cada palavra à coluna cujo rótulo está acima dela (por isso bairro e município saem separados). Procura o cartão em qualquer página |
| 2 | Leitura da Receita | `receita.py` | BrasilAPI, depois OpenCNPJ. Cache por CNPJ; "não existe" só é aceito se as duas disserem isso. O quadro de sócios é descartado |
| 3 | Leitura do ERP | `fontes.py` | Renomeia as colunas para o padrão (mapa de-para) |
| 4 | Padronização | `padronizacao.py` | CNPJ e CEP só com dígitos, datas em `AAAA-MM-DD`, texto em maiúsculas, "RUA" vira "R", "MICRO EMPRESA" vira "ME". Padroniza o formato, mas **não corrige** valor errado |
| 5 | Qualidade | `qualidade.py` | Aplica as 20 regras; calcula scorecard, índice e uma nota de 0 a 100 por registro |
| 6 | Match | `mdm.py` | CNPJ válido igual = mesma empresa. Sem CNPJ válido: compara com candidatos que tenham a mesma UF, **ou** o mesmo começo de CEP, **ou** a mesma primeira palavra no nome, e calcula um score |
| 7 | Sobrevivência | `mdm.py` | Para cada campo, entre os valores válidos: vence a fonte de maior prioridade; empate, o mais recente; empate de novo, o registro de melhor nota. Anota a origem na linhagem |
| 8 | Hierarquia | `mdm.py` | Agrupa pelos 8 primeiros caracteres do CNPJ (a empresa); ordem 0001 é a matriz |
| 9 | Qualidade do mestre | `pipeline.py` | As mesmas regras sobre o cadastro mestre |
| 10 | Acurácia | `reconciliacao.py` | Compara cada campo do cartão e do ERP com a Receita |
| 11 | Saídas | `banco.py`, `relatorio.py`, `lgpd.py` | SQLite, CSVs, HTML e RESUMO.md (os dois últimos com dados pessoais mascarados) |

### 9.2. Como o score de semelhança é calculado

Para um registro do ERP sem CNPJ válido, comparado com uma empresa candidata:

| Atributo | Peso | Como compara |
|---|---|---|
| Nome | 0,45 | Semelhança das palavras, ignorando ordem, acentos, pontuação, "LTDA", "ME", "EIRELI" e CPF |
| CNPJ | 0,35 | Quantos caracteres precisam mudar para um virar o outro (um dígito trocado dá cerca de 0,93) |
| CEP | 0,15 | Igual ou diferente |
| Município | 0,05 | Igual ou diferente |

Se um atributo falta em um dos lados, o peso dele é redistribuído entre os demais; sem nome, o score é zero. Exemplo da demo: nome quase igual (0,99), CNPJ com um dígito trocado (0,93), CEP e município diferentes porque o ERP tem o endereço antigo → score 0,775 → fila do Steward.

### 9.3. Como o índice de qualidade é calculado

Para cada regra: registros conformes ÷ registros avaliados. O índice é a média ponderada pelo peso da severidade (crítica 8, alta 4, média 2, baixa 1). Regras com `no_score: true` ficam de fora.

A nota por registro (usada no desempate do MDM) é `100 − 5 × soma dos pesos das regras em que ele falhou`, com mínimo zero.

### 9.4. Validação do CNPJ

Desde julho de 2026 a Receita emite CNPJs com letras nas 12 primeiras posições (ex.: `12.ABC.345/01DE-35`). O cálculo dos dígitos verificadores é o mesmo módulo 11 de sempre, trocando cada caractere pelo seu código ASCII menos 48 (`0` vale 0, `A` vale 17). Assim, CNPJs antigos e novos são validados pela mesma função (`validadores.cnpj_valido`).

### 9.5. Testes

```bash
python -m pytest
```

São 76 testes, em quatro arquivos:

| Arquivo | Testa |
|---|---|
| `test_validadores.py` | CNPJ (inclusive o exemplo oficial alfanumérico), CEP × UF, telefone, e-mail, datas |
| `test_extracao_padronizacao.py` | Leitura de um cartão montado palavra por palavra (sem PDF real), padronização, adaptador da OpenCNPJ |
| `test_qualidade_mdm.py` | Cada tipo de regra, scorecard, match, sobrevivência, decisões do Steward, hierarquia, mascaramento |
| `test_pipeline_demo.py` | A demo inteira: números esperados, arquivos gerados, consultas SQL e ausência de CPF ou e-mail nas saídas compartilháveis |

---

## 10. Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `No module named mdm_cnpj` | Rodou `python -m mdm_cnpj` com o Python portátil, que não enxerga a pasta atual | Use `python executar.py ...` |
| `ModuleNotFoundError: No module named 'pandas'` (ou outra biblioteca) | Bibliotecas não instaladas nesse Python | `python -m pip install -r requirements.txt` |
| Acentos estranhos no terminal do Windows | Console em outra codificação | Só visual; os arquivos gerados estão corretos. O `executar.py` já força UTF-8 |
| Muitos `HTTP 429, nova tentativa em ...` | A API limitou o número de consultas | Normal: o programa espera e tenta de novo. Se persistir, rode mais tarde; o que já foi consultado fica no cache |
| CNPJs em `receita_sem_dados` com `sem_resposta` | As duas APIs falharam naquele momento | Rode de novo: respostas que falharam não ficam no cache |
| CNPJ ativo aparecendo como `http_404` | Nenhum dos dois provedores encontrou o CNPJ | Confira no site da Receita; se existir, apague o arquivo dele em `.cache/receita/` e rode de novo |
| Muitos PDFs rejeitados com `imagem_sem_texto` | PDFs digitalizados | Ver a tabela de motivos na seção 6 |
| A primeira execução real demora | Leitura de cada PDF (~1 s) + consultas | As próximas usam o cache e levam segundos |
| Mudei uma regra e nada mudou | Abriu o relatório antigo | Rode o pipeline de novo e recarregue a página (F5) |
| A decisão do Steward não foi aplicada | Arquivo com outro nome, outra pasta ou separador `,` | Precisa ser `decisoes_steward.csv`, na pasta de saída, separado por `;` |

---

## 11. Glossário

| Termo | Significado |
|---|---|
| **Acurácia** | Quanto o valor está *certo*, comparado com uma fonte de referência. Diferente de validade: um CEP pode ter 8 dígitos (válido) e ser de outra rua (inexato) |
| **Atualidade** | Quão recente é a informação |
| **Blocagem** | Comparar cada registro só com candidatos que compartilham alguma pista, em vez de com a base inteira |
| **Completude** | Se o campo está preenchido |
| **Consistência** | Se campos relacionados combinam entre si (CEP × UF, data de abertura × data da situação) |
| **Crosswalk** | Tabela de-para entre o código do registro em cada fonte e o registro mestre |
| **Data Steward** | Responsável por cuidar da qualidade e das definições de um conjunto de dados |
| **Dono do dado** | Área que decide o que o dado significa e quais metas ele deve cumprir |
| **Esquema canônico** | O formato único para o qual todas as fontes são convertidas |
| **Fonte autoritativa** | A fonte considerada oficial para um dado; aqui, a Receita Federal |
| **Golden record / registro mestre** | A melhor versão consolidada de uma entidade |
| **Linhagem** | O registro de onde cada valor veio |
| **Match** | Decidir se dois registros são a mesma entidade |
| **MDM** | *Master Data Management*, gestão de dados mestres |
| **Não conformidade** | Um registro que falhou em uma regra de qualidade |
| **Quarentena** | Registros que não entram no cadastro mestre até serem tratados |
| **Silver / gold** | Camadas do dado: padronizado (silver) e consolidado (gold) |
| **Sobrevivência** | A regra que escolhe qual valor vai para o registro mestre quando as fontes discordam |
| **Unicidade** | Se a mesma entidade não aparece repetida |
| **Validade** | Se o valor tem o formato e o domínio corretos |
