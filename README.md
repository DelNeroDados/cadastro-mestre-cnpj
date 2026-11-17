# Cadastro mestre de empresas (CNPJ)

Pipeline em Python que junta três fontes de cadastro de clientes PJ (cartões CNPJ em PDF, Receita Federal e uma planilha de ERP), mede a qualidade de cada uma e monta um cadastro mestre com um registro por estabelecimento.

Para rodar sem internet, com dados fictícios:

```bash
pip install -r requirements.txt
python executar.py demo
```

No Windows, dá para usar o `Iniciar.bat`. O resultado da demo está em [saida_demo/RESUMO.md](saida_demo/RESUMO.md). Instruções completas no [MANUAL.md](MANUAL.md).

## Como começou

Eu tinha uma pasta com 304 PDFs de cartões CNPJ de clientes, juntados ao longo de anos, e precisava saber quantos clientes eram de verdade, quais estavam com CNPJ baixado e qual era o endereço atual de cada um.

A primeira versão foi um script de regex que extraía os campos para um CSV. Quando comparei o resultado com a Receita, vi que ele errava sem dar nenhum erro: em vários arquivos a "data de abertura" era a data em que o PDF tinha sido impresso, e o município saía sempre vazio, porque no texto do PDF bairro e município ficam na mesma linha. Reescrevi a leitura usando a posição das palavras na página. A partir daí o projeto virou o que ele é hoje: em vez de um extrator, um processo de qualidade de dados e MDM com três fontes.

## O que ele faz

1. **Lê as fontes e padroniza o formato.** CNPJ e CEP só com dígitos, datas em ISO, "RUA" vira "R" etc.
2. **Aplica 20 regras de qualidade**, definidas em [config/regras_qualidade.yaml](config/regras_qualidade.yaml). Elas cobrem completude, validade, consistência, unicidade e atualidade. Cada regra tem severidade, meta e uma ação recomendada. As falhas viram uma lista de não conformidades para tratar.
3. **Junta os registros da mesma empresa (MDM).**
   - Mesmo CNPJ válido é a mesma empresa.
   - Sem CNPJ válido, calculo um score de semelhança com nome, dígitos do CNPJ e CEP. Score alto une automaticamente; score médio vai para uma fila de revisão manual; o resto fica em quarentena.
   - O valor de cada campo é escolhido por regras de prioridade entre as fontes ([config/sobrevivencia.yaml](config/sobrevivencia.yaml)), e fica anotado de qual fonte e de qual arquivo ele veio.
4. **Compara os cartões e o ERP com a Receita** campo a campo, para medir a acurácia de cada fonte.
5. **Gera** um relatório HTML, um banco SQLite com views e CSVs para trabalho. E-mail, telefone e nome/CPF de MEI saem mascarados no relatório.

A documentação de apoio está em [docs/](docs/): dicionário de dados, catálogo das regras (gerado a partir do YAML) e um documento de governança com papéis, metas e o tratamento de dados pessoais.

## Resultados

**Demo** (dados fictícios, sempre os mesmos números):

- 194 registros de origem viraram 51 registros no cadastro mestre;
- foram registradas 122 não conformidades, 6 delas críticas;
- 1 par ficou para revisão manual;
- o índice de qualidade foi de 97,5 nas fontes para 99,8 no cadastro mestre.

**Dados reais** (só os totais; os PDFs não estão no repositório):

- **Leitura:** dos 304 PDFs, 63 eram cópias idênticas e 38 não puderam ser lidos (32 são digitalizações sem texto).
- **Cadastro mestre:** o resultado foi de 66 estabelecimentos de 64 empresas; cerca de 80% dos registros eram repetidos.
- **Atualidade:** 97% dos cartões tinham mais de um ano.
- **Situação cadastral:** 6 clientes estão com CNPJ baixado, e 16 cartões ainda diziam "ATIVA" porque foram emitidos antes da baixa.
- **Acurácia do cartão contra a Receita:** 100% na data de abertura, mas só 73 a 77% em logradouro e CEP, porque muita empresa mudou de endereço depois de emitir o cartão.

Na execução real tive um problema que não esperava: a BrasilAPI respondeu "não encontrado" para 48 dos 66 CNPJs, inclusive de empresas ativas que ela tinha encontrado meses antes. Se eu tivesse aceitado essas respostas, quase três quartos da carteira apareceriam como empresa inexistente. Por isso coloquei a OpenCNPJ como segunda fonte, e agora um "não existe" só é aceito quando nenhuma das duas encontra o CNPJ.

## Estrutura

```
config/      regras de qualidade e de MDM (YAML)
docs/        dicionário de dados, governança, catálogo de regras
mdm_cnpj/    código: extração, Receita, padronização, qualidade, MDM, relatório
sql/         views do SQLite e consultas de apoio
tests/       testes (pytest)
```

## O que ainda falta

- OCR para os cartões digitalizados.
- Validar município × UF com a tabela do IBGE.
- Agendar a execução e guardar o histórico do índice para acompanhar a evolução.

## Privacidade

Os cartões reais são de clientes e não estão aqui; as pastas de PDFs, o cache e a saída real estão no `.gitignore`. A demo usa nomes inventados, e os CPFs que aparecem nela têm dígito verificador inválido de propósito.
