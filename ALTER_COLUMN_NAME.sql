-- =====================================================
-- Script: Renomear coluna B_DATA_TRANSBORDO_ATTD para B_DATA_TRANSBORDO_ATD
-- Descrição: Alteração do nome da coluna para padronizar com ATD
-- Autor: Sistema Farol
-- Data: 2025
-- =====================================================

-- STATUS: ✅ CONCLUÍDO - A coluna já foi renomeada no banco de dados
-- A coluna B_DATA_TRANSBORDO_ATTD foi renomeada para B_DATA_TRANSBORDO_ATD
-- O código foi atualizado para usar os nomes corretos das colunas

-- Verificar se a alteração foi aplicada
SELECT COLUMN_NAME 
FROM ALL_TAB_COLUMNS 
WHERE TABLE_NAME = 'F_CON_SALES_BOOKING_DATA' 
  AND OWNER = 'LOGTRANSP' 
  AND COLUMN_NAME LIKE '%TRANSBORDO%'
ORDER BY COLUMN_NAME;

-- Resultado atual:
-- B_DATA_ESTIMADA_TRANSBORDO_ETD
-- B_DATA_TRANSBORDO_ATD

-- ✅ Todas as colunas estão funcionando corretamente:
-- - B_DATA_CONFIRMACAO_EMBARQUE
-- - B_DATA_ESTIMADA_TRANSBORDO_ETD  
-- - B_DATA_TRANSBORDO_ATD
