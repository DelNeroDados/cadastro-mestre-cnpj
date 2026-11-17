# Catálogo de regras de qualidade

> Gerado automaticamente de `config/regras_qualidade.yaml` por `python executar.py catalogo`. Não edite à mão.

- **Versão do catálogo:** 2.0
- **Dono do dado:** Área Comercial / Cadastro de Clientes
- **Steward responsável:** Analista de Qualidade de Dados
- **Pesos por severidade no índice:** critica = 8, alta = 4, media = 2, baixa = 1

| Dimensão | Meta de conformidade |
|---|---|
| Completude | 95% |
| Validade | 98% |
| Consistência | 97% |
| Unicidade | 100% |
| Atualidade | 70% |

## Completude

| ID | Regra | Severidade | Fontes | Ação recomendada |
|---|---|---|---|---|
| DQ001 | CNPJ preenchido | critica | todas | Recuperar o CNPJ no documento de origem ou junto ao cliente. |
| DQ004 | Razão social preenchida | critica | todas | Preencher com a razão social da Receita. |
| DQ006 | Situação cadastral preenchida | alta | cartao, receita, mestre | Consultar a situação na Receita. |
| DQ012 | CEP preenchido | alta | todas | Completar o endereço com o CEP. |
| DQ016 | Município preenchido | media | todas | Completar o município a partir do CEP. |
| DQ017 | Pelo menos um contato (e-mail ou telefone) | baixa | erp, mestre | Solicitar um contato ao cliente no próximo atendimento. |

## Validade

| ID | Regra | Severidade | Fontes | Ação recomendada |
|---|---|---|---|---|
| DQ002 | CNPJ com dígitos verificadores válidos<br><sub>Módulo 11 da Receita; aceita o CNPJ alfanumérico (julho/2026).</sub> | critica | todas | Erro de digitação provável. Conferir no cartão CNPJ e corrigir na origem. |
| DQ007 | Situação cadastral dentro do domínio da Receita | alta | todas | Padronizar para um dos valores oficiais. |
| DQ008 | Data de abertura válida e não futura | media | todas | Conferir a data de início de atividade na Receita. |
| DQ011 | CNAE principal com 7 dígitos | media | cartao, receita | Corrigir o código CNAE conforme a Receita. |
| DQ013 | CEP com 8 dígitos | alta | todas | CEP truncado ou com dígitos a mais; conferir nos Correios. |
| DQ014 | UF válida | alta | todas | Informar a sigla oficial da UF. |
| DQ018 | E-mail em formato válido | baixa | todas | Corrigir o e-mail com o cliente. |
| DQ019 | Telefone com DDD e número válidos | baixa | todas | Completar o DDD ou corrigir o número. |

## Consistência

| ID | Regra | Severidade | Fontes | Ação recomendada |
|---|---|---|---|---|
| DQ005 | Matriz/filial coerente com o CNPJ<br><sub>A ordem 0001 do CNPJ identifica a matriz.</sub> | media | todas | Corrigir o tipo de estabelecimento conforme a ordem do CNPJ. |
| DQ009 | Situação cadastral posterior à abertura | media | todas | Uma das datas está errada; prevalece a da Receita. |
| DQ010 | Empresa com situação ATIVA<br><sub>Regra de negócio. CNPJ baixado ou inapto não pode receber nota fiscal.</sub><br><sub>Alerta de negócio: não entra no índice de qualidade.</sub> | alta | todas | Bloquear o cliente para faturamento e avisar a área comercial. |
| DQ015 | CEP pertence à UF informada<br><sub>Faixas de CEP dos Correios por UF.</sub> | alta | todas | CEP ou UF trocados. Prevalece o endereço da Receita. |

## Unicidade

| ID | Regra | Severidade | Fontes | Ação recomendada |
|---|---|---|---|---|
| DQ003 | CNPJ único na fonte<br><sub>Aplicada ao ERP e ao cadastro mestre. Nos cartões, vários PDFs do mesmo CNPJ são esperados (versões emitidas em datas diferentes) e são resolvidos pelo MDM.</sub> | alta | erp, mestre | Unificar os cadastros duplicados no ERP, mantendo o código mais antigo. |

## Atualidade

| ID | Regra | Severidade | Fontes | Ação recomendada |
|---|---|---|---|---|
| DQ020 | Informação com menos de 1 ano<br><sub>Cartão emitido ou cadastro do ERP atualizado nos últimos 365 dias. A Receita não entra: é consultada no momento da carga.</sub> | media | cartao, erp | Emitir um cartão CNPJ novo ou revalidar o cadastro com o cliente. |
