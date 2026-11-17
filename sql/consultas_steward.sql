-- =====================================================================
-- Consultas de apoio ao Data Steward (rode no saida_demo/mdm.sqlite)
-- Todas são executadas pelos testes automatizados, então não quebram em silêncio.
-- =====================================================================

-- 1. Perfil de completude: % de preenchimento de cada campo por fonte.
SELECT fonte,
       COUNT(*)                                                         AS registros,
       ROUND(100.0 * SUM(cnpj         <> '') / COUNT(*), 1)             AS pct_cnpj,
       ROUND(100.0 * SUM(razao_social <> '') / COUNT(*), 1)             AS pct_razao_social,
       ROUND(100.0 * SUM(cep          <> '') / COUNT(*), 1)             AS pct_cep,
       ROUND(100.0 * SUM(municipio    <> '') / COUNT(*), 1)             AS pct_municipio,
       ROUND(100.0 * SUM(email        <> '') / COUNT(*), 1)             AS pct_email,
       ROUND(100.0 * SUM(telefone     <> '') / COUNT(*), 1)             AS pct_telefone
FROM silver_registros
GROUP BY fonte;

-- 2. Duplicidade: CNPJs que aparecem mais de uma vez na mesma fonte.
SELECT fonte, cnpj, COUNT(*) AS ocorrencias, GROUP_CONCAT(id_origem, ', ') AS ids
FROM silver_registros
WHERE cnpj <> ''
GROUP BY fonte, cnpj
HAVING COUNT(*) > 1
ORDER BY ocorrencias DESC;

-- 3. Versão mais recente de cada cartão CNPJ (função de janela).
SELECT cnpj, id_origem AS arquivo, data_referencia AS emitido_em, situacao_cadastral
FROM (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY cnpj ORDER BY data_referencia DESC) AS rn
    FROM silver_registros s
    WHERE fonte = 'cartao'
)
WHERE rn = 1;

-- 4. Cartões que ainda dizem ATIVA para empresas que a Receita já baixou ou inabilitou.
SELECT d.cnpj, d.id_origem AS arquivo, d.data_referencia_fonte AS emitido_em,
       d.valor_fonte AS situacao_no_cartao, d.valor_receita AS situacao_hoje
FROM rec_divergencias d
WHERE d.campo = 'situacao_cadastral' AND d.fonte = 'cartao';

-- 5. Taxa de redundância: quantos registros de origem viram cada registro mestre.
SELECT COUNT(*)                                        AS registros_origem,
       COUNT(DISTINCT id_mestre)                       AS registros_mestres,
       ROUND(1 - 1.0 * COUNT(DISTINCT id_mestre) / COUNT(*), 3) AS taxa_redundancia
FROM mdm_crosswalk
WHERE id_mestre <> '';

-- 6. Como cada registro foi casado com o mestre.
SELECT metodo_match, fonte, COUNT(*) AS registros, ROUND(AVG(score_match), 3) AS score_medio
FROM mdm_crosswalk
GROUP BY metodo_match, fonte
ORDER BY metodo_match, fonte;

-- 7. Linhagem completa de um registro mestre (troque o id).
SELECT campo, valor, fonte, id_origem, data_referencia, criterio, alternativas
FROM mdm_linhagem
WHERE id_mestre = (SELECT MIN(id_mestre) FROM mdm_golden)
ORDER BY campo;
