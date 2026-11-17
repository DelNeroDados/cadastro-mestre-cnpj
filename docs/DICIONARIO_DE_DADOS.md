# Dicionário de dados

Esquema canônico do cadastro de empresas: o formato comum para o qual as três fontes são convertidas na camada *silver*. O cadastro mestre (*gold*) também usa estas colunas e acrescenta as colunas de controle do MDM.

## Fontes

| Fonte | O que é | Confiabilidade | Data de referência |
|---|---|---|---|
| `receita` | Cadastro da Receita Federal consultado pela BrasilAPI, com a OpenCNPJ como segundo provedor | **Autoritativa**: define razão social, situação e endereço fiscal | Data da consulta |
| `cartao` | Cartão CNPJ (Comprovante de Inscrição e de Situação Cadastral) em PDF | Alta, mas envelhece: é uma foto da Receita no dia em que foi emitido | Data de emissão impressa no rodapé |
| `erp` | Cadastro de clientes do sistema comercial, digitado por pessoas | Média para dados fiscais; **a melhor** para o contato comercial | Última atualização do cadastro |

## Campos do esquema canônico

| Campo | Tipo e formato | Descrição | Validação | Classificação (LGPD) |
|---|---|---|---|---|
| `cnpj` | texto, 14 posições sem máscara | Identificador do estabelecimento. Desde julho/2026 as 12 primeiras posições podem ter letras | DV módulo 11 (DQ002) | público |
| `razao_social` | texto em maiúsculas | Nome empresarial registrado na Receita | obrigatório (DQ004) | **pessoal** quando empresário individual/MEI (nome e CPF da pessoa) |
| `nome_fantasia` | texto em maiúsculas | Título do estabelecimento | - | público |
| `tipo_estabelecimento` | `MATRIZ` ou `FILIAL` | Deve bater com a ordem do CNPJ (0001 = matriz) | DQ005 | público |
| `data_abertura` | data ISO `AAAA-MM-DD` | Início de atividade | data válida, não futura (DQ008) | público |
| `situacao_cadastral` | domínio: ATIVA, BAIXADA, INAPTA, SUSPENSA, NULA | Situação na Receita | DQ006, DQ007, alerta DQ010 | público |
| `data_situacao_cadastral` | data ISO | Desde quando vale a situação | ≥ data de abertura (DQ009) | público |
| `natureza_juridica` | texto | Ex.: Sociedade Empresária Limitada, Empresário (Individual) | - | público |
| `porte` | `ME`, `EPP` ou `DEMAIS` | Porte declarado. A API escreve por extenso; padronizamos na forma curta | - | público |
| `cnae_principal` | texto, 7 dígitos | CNAE-Subclasse da atividade principal | 7 dígitos (DQ011) | público |
| `cnae_principal_descricao` | texto | Descrição da atividade | - | público |
| `cnaes_secundarios` | lista de códigos separados por `\|` | Atividades secundárias | - | público |
| `logradouro` | texto, tipo abreviado (`R`, `AV`, `ROD`...) | Endereço. A API devolve "RUA", o cartão "R"; padronizamos na forma do cartão | - | **pessoal** quando MEI (endereço residencial frequente) |
| `numero` | texto | Número do endereço | - | idem |
| `complemento` | texto | Complemento (`********` do cartão vira vazio) | - | público |
| `bairro` | texto | Bairro ou distrito | - | público |
| `municipio` | texto sem acento | Município | obrigatório (DQ016) | público |
| `uf` | sigla de 2 letras | Unidade federativa | domínio (DQ014), CEP×UF (DQ015) | público |
| `cep` | texto, 8 dígitos | CEP sem máscara | obrigatório (DQ012), 8 dígitos (DQ013) | público |
| `email` | texto em minúsculas | E-mail de contato | formato (DQ018) | **pessoal** (pode identificar o titular) |
| `telefone` | texto, DDD + número | Telefone principal | DDD e tamanho (DQ019) | **pessoal** |

## Colunas de controle

| Coluna | Onde | Descrição |
|---|---|---|
| `fonte` | silver | `receita`, `cartao` ou `erp` |
| `id_origem` | silver | Chave do registro na fonte: o CNPJ (Receita), o nome do arquivo (cartão) ou o código do cliente (ERP) |
| `data_referencia` | silver | Até quando a informação é sabidamente verdadeira (ver tabela de fontes) |
| `score_registro` | silver | Nota de 0 a 100 do registro, derivada das não conformidades. Desempate na sobrevivência |
| `id_mestre` | gold | Identificador estável do registro mestre: `MDM-` + 8 caracteres do SHA-1 do CNPJ |
| `cnpj_raiz` | gold | 8 primeiras posições do CNPJ (a empresa, não o estabelecimento) |
| `eh_matriz` | gold | Verdadeiro para a ordem 0001 |
| `fontes` | gold | Fontes que contribuíram para o registro |
| `qtd_registros_origem` | gold | Quantos registros de origem viraram este registro mestre |
| `status_mestre` | gold | `VALIDADO_RECEITA` ou `SEM_FONTE_AUTORITATIVA` |
| `completude_pct` | gold | % dos campos canônicos preenchidos |
| `data_ultima_evidencia` | gold | Data de referência mais recente entre as fontes |

## Mapa de-para do ERP

| Coluna no ERP | Campo canônico |
|---|---|
| `cod_cliente` | `id_origem` |
| `cnpj_cpf` | `cnpj` |
| `razao_social`, `nome_fantasia`, `numero`, `bairro`, `uf`, `cep`, `email`, `telefone` | mesmo nome |
| `endereco` | `logradouro` |
| `cidade` | `municipio` |
| `dt_atualizacao` | `data_referencia` |
| `dt_cadastro` | não mapeado: é a data do cadastro no ERP, **não** a data de abertura da empresa |
