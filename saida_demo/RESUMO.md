# Resumo da execução (demonstração sintética)

Data de referência: 01/11/2026 · catálogo de regras v2.0 (20 regras). Arquivo gerado automaticamente por `executar.py`.

## Números principais

| Indicador | Valor |
|---|---|
| Registros de origem | 194 (Cartões CNPJ: 93, ERP: 51, Receita Federal: 50) |
| Registros no cadastro mestre | 51 estabelecimentos de 46 empresas |
| Redundância eliminada pelo MDM | 73.4% |
| Índice de qualidade: fontes → mestre | 97.5 → 99.84 |
| Não conformidades registradas | 122 (6 críticas) |
| Pares na fila de revisão do Steward | 1 |
| Clientes com CNPJ não ativo | 5 |
| CNPJs alfanuméricos (novo formato de 2026) | 4 |

## Scorecard por dimensão (todas as fontes)

| Dimensão | Conformidade | Meta | Status |
|---|---|---|---|
| Completude | 99.7% | 95% | ✅ atingiu |
| Validade | 98.5% | 98% | ✅ atingiu |
| Consistência | 99.6% | 97% | ✅ atingiu |
| Unicidade | 88.0% | 100% | ⚠️ abaixo da meta |
| Atualidade | 41.0% | 70% | ⚠️ abaixo da meta |

## Regras com falhas

| Regra | Severidade | Fonte | Falhas | Conformidade | Ação recomendada |
|---|---|---|---|---|---|
| DQ002 CNPJ com dígitos verificadores válidos | critica | ERP | 5/50 | 90.0% | Erro de digitação provável. Conferir no cartão CNPJ e corrigir na origem. |
| DQ001 CNPJ preenchido | critica | ERP | 1/51 | 98.0% | Recuperar o CNPJ no documento de origem ou junto ao cliente. |
| DQ003 CNPJ único na fonte | alta | ERP | 6/50 | 88.0% | Unificar os cadastros duplicados no ERP, mantendo o código mais antigo. |
| DQ010 Empresa com situação ATIVA *(alerta, fora do índice)* | alta | Receita Federal | 5/50 | 90.0% | Bloquear o cliente para faturamento e avisar a área comercial. |
| DQ013 CEP com 8 dígitos | alta | ERP | 4/50 | 92.0% | CEP truncado ou com dígitos a mais; conferir nos Correios. |
| DQ015 CEP pertence à UF informada | alta | ERP | 2/46 | 95.7% | CEP ou UF trocados. Prevalece o endereço da Receita. |
| DQ012 CEP preenchido | alta | ERP | 1/51 | 98.0% | Completar o endereço com o CEP. |
| DQ020 Informação com menos de 1 ano | media | Cartões CNPJ | 47/93 | 49.5% | Emitir um cartão CNPJ novo ou revalidar o cadastro com o cliente. |
| DQ020 Informação com menos de 1 ano | media | ERP | 38/51 | 25.5% | Emitir um cartão CNPJ novo ou revalidar o cadastro com o cliente. |
| DQ019 Telefone com DDD e número válidos | baixa | ERP | 7/50 | 86.0% | Completar o DDD ou corrigir o número. |
| DQ018 E-mail em formato válido | baixa | ERP | 5/44 | 88.6% | Corrigir o e-mail com o cliente. |
| DQ017 Pelo menos um contato (e-mail ou telefone) | baixa | ERP | 1/51 | 98.0% | Solicitar um contato ao cliente no próximo atendimento. |

## Acurácia contra a Receita (% de valores iguais)

| Campo | Cartões CNPJ | ERP |
|---|---|---|
| bairro | 97.8% | 100.0% |
| cep | 92.5% | 90.9% |
| cnae_principal | 100.0% | - |
| data_abertura | 100.0% | - |
| email | 100.0% | 94.4% |
| logradouro | 92.5% | 100.0% |
| municipio | 92.5% | 100.0% |
| nome_fantasia | 100.0% | 100.0% |
| numero | 92.5% | 100.0% |
| razao_social | 100.0% | 97.7% |
| situacao_cadastral | 91.4% | - |
| telefone | 100.0% | 86.4% |
| uf | 92.5% | 97.7% |

## Como os registros foram casados

| Método | Registros |
|---|---|
| CNPJ idêntico (determinístico) | 188 |
| Similaridade alta (automático) | 4 |
| Aguardando o Steward | 1 |
| Quarentena (sem correspondente) | 1 |

## Fila de revisão do Steward

| Origem | Nome na origem | Sugestão | Score |
|---|---|---|---|
| erp 1030 | ALFAQUIMICA MATERIAIS DE CONSTRUCAO LTDA. | ALFAQUIMICA MATERIAIS DE CONSTRUCAO LTDA (58.461.819/0001-36) | 0.775 |


*Dados pessoais (nome e CPF de empresário individual, e-mail, telefone) mascarados conforme a política de LGPD do projeto.*
