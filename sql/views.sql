-- =====================================================================
-- Views criadas automaticamente em saida_*/mdm.sqlite
--
-- Tabelas que o pipeline grava:
--   silver_registros       todas as fontes no esquema canônico
--   dq_resultados          uma linha por regra x fonte
--   dq_nao_conformidades   uma linha por registro reprovado em uma regra
--   dq_scorecard           conformidade por dimensão x fonte, com a meta
--   mdm_crosswalk          (fonte, id_origem) -> id_mestre
--   mdm_golden             o cadastro mestre
--   mdm_linhagem           de onde veio cada valor do cadastro mestre
--   mdm_hierarquia         matriz e filiais por raiz de CNPJ
--   mdm_fila_revisao       pares duvidosos que esperam decisão humana
--   rec_acuracia           acurácia por fonte x campo contra a Receita
--   rec_divergencias       cada divergência encontrada
--   doc_rejeitados         PDFs que não puderam ser lidos, com o motivo
-- =====================================================================

-- Painel do gestor: as dimensões abaixo da meta aparecem primeiro.
CREATE VIEW vw_scorecard AS
SELECT fonte, dimensao, avaliados, conformes, conformidade, meta,
       CASE WHEN atingiu_meta THEN 'OK' ELSE 'ABAIXO DA META' END AS status
FROM dq_scorecard
ORDER BY atingiu_meta, fonte, dimensao;

-- Fila de trabalho do Data Steward, agrupada por regra e ordenada por gravidade.
CREATE VIEW vw_pendencias_steward AS
SELECT regra_id, regra, severidade, fonte, COUNT(*) AS registros, acao_recomendada
FROM dq_nao_conformidades
GROUP BY regra_id, regra, severidade, fonte, acao_recomendada
ORDER BY CASE severidade WHEN 'critica' THEN 1 WHEN 'alta' THEN 2
                         WHEN 'media' THEN 3 ELSE 4 END,
         registros DESC;

-- Clientes que exigem ação comercial: CNPJ não ativo na Receita.
CREATE VIEW vw_clientes_em_risco AS
SELECT g.id_mestre, g.cnpj, g.razao_social, g.situacao_cadastral,
       g.data_situacao_cadastral, g.fontes
FROM mdm_golden g
WHERE g.situacao_cadastral IN ('BAIXADA', 'INAPTA', 'SUSPENSA', 'NULA');

-- Registros mestres que a Receita não confirmou (CNPJ desconhecido ou não consultado).
CREATE VIEW vw_mestre_sem_validacao AS
SELECT id_mestre, cnpj, razao_social, fontes
FROM mdm_golden
WHERE status_mestre <> 'VALIDADO_RECEITA';

-- Estabelecimentos cuja matriz não está no cadastro (lacuna de hierarquia).
CREATE VIEW vw_filiais_sem_matriz AS
SELECT h.cnpj_raiz, h.razao_social, h.qtd_filiais
FROM mdm_hierarquia h
WHERE h.matriz_no_cadastro = 0;

-- Golden record com a origem de três campos-chave lado a lado.
CREATE VIEW vw_golden_com_origem AS
SELECT g.id_mestre, g.cnpj, g.razao_social,
       g.cep,      l_cep.fonte   AS origem_cep,
       g.email,    l_mail.fonte  AS origem_email,
       g.situacao_cadastral, l_sit.fonte AS origem_situacao
FROM mdm_golden g
LEFT JOIN mdm_linhagem l_cep  ON l_cep.id_mestre  = g.id_mestre AND l_cep.campo  = 'cep'
LEFT JOIN mdm_linhagem l_mail ON l_mail.id_mestre = g.id_mestre AND l_mail.campo = 'email'
LEFT JOIN mdm_linhagem l_sit  ON l_sit.id_mestre  = g.id_mestre AND l_sit.campo  = 'situacao_cadastral';

-- Campos em que as fontes mais discordam (candidatos a regra de sobrevivência específica).
CREATE VIEW vw_conflitos_por_campo AS
SELECT campo,
       COUNT(*) AS registros_mestres,
       SUM(CASE WHEN valores_distintos > 1 THEN 1 ELSE 0 END) AS com_conflito,
       ROUND(100.0 * SUM(CASE WHEN valores_distintos > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_conflito
FROM mdm_linhagem
GROUP BY campo
ORDER BY pct_conflito DESC;
