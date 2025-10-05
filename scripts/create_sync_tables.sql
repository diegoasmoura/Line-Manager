-- =====================================================
-- Script para criação das tabelas de sincronização Ellox
-- Sistema de Sincronização Automática Ellox API
-- =====================================================

-- Tabela de logs de sincronização
CREATE TABLE LogTransp.F_ELLOX_SYNC_LOGS (
    ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SYNC_TIMESTAMP TIMESTAMP DEFAULT SYSTIMESTAMP,
    VESSEL_NAME VARCHAR2(200),
    VOYAGE_CODE VARCHAR2(100),
    TERMINAL VARCHAR2(200),
    STATUS VARCHAR2(50) NOT NULL,
    CHANGES_DETECTED NUMBER DEFAULT 0,
    ERROR_MESSAGE CLOB,
    RETRY_ATTEMPT NUMBER DEFAULT 0,
    EXECUTION_TIME_MS NUMBER,
    USER_ID VARCHAR2(50) DEFAULT 'SYSTEM',
    FIELDS_CHANGED CLOB
);

-- Índices para performance
CREATE INDEX IX_SYNC_LOGS_TIMESTAMP ON LogTransp.F_ELLOX_SYNC_LOGS(SYNC_TIMESTAMP);
CREATE INDEX IX_SYNC_LOGS_STATUS ON LogTransp.F_ELLOX_SYNC_LOGS(STATUS);
CREATE INDEX IX_SYNC_LOGS_VESSEL ON LogTransp.F_ELLOX_SYNC_LOGS(VESSEL_NAME);
CREATE INDEX IX_SYNC_LOGS_VOYAGE ON LogTransp.F_ELLOX_SYNC_LOGS(VOYAGE_CODE);

-- Tabela de configuração (singleton)
CREATE TABLE LogTransp.F_ELLOX_SYNC_CONFIG (
    ID NUMBER DEFAULT 1 PRIMARY KEY,
    SYNC_ENABLED NUMBER(1) DEFAULT 1,
    SYNC_INTERVAL_MINUTES NUMBER DEFAULT 60,
    MAX_RETRIES NUMBER DEFAULT 3,
    LAST_EXECUTION TIMESTAMP,
    NEXT_EXECUTION TIMESTAMP,
    UPDATED_BY VARCHAR2(50),
    UPDATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT CHK_SINGLE_CONFIG CHECK (ID = 1)
);

-- Inserir configuração padrão
INSERT INTO LogTransp.F_ELLOX_SYNC_CONFIG (ID) VALUES (1);

-- Comentários para documentação
COMMENT ON TABLE LogTransp.F_ELLOX_SYNC_LOGS IS 'Logs de execução da sincronização automática com API Ellox';
COMMENT ON TABLE LogTransp.F_ELLOX_SYNC_CONFIG IS 'Configuração do sistema de sincronização automática Ellox';

COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_LOGS.STATUS IS 'Status da execução: SUCCESS, NO_CHANGES, API_ERROR, AUTH_ERROR, RETRY';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_LOGS.CHANGES_DETECTED IS 'Número de campos alterados na sincronização';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_LOGS.FIELDS_CHANGED IS 'Lista JSON dos campos que foram alterados';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_LOGS.RETRY_ATTEMPT IS 'Número da tentativa (0 = primeira tentativa)';

COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_CONFIG.SYNC_ENABLED IS 'Flag para ativar/desativar sincronização (1=ativo, 0=inativo)';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_CONFIG.SYNC_INTERVAL_MINUTES IS 'Intervalo entre sincronizações em minutos';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_CONFIG.MAX_RETRIES IS 'Número máximo de tentativas em caso de erro';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_CONFIG.LAST_EXECUTION IS 'Timestamp da última execução da sincronização';
COMMENT ON COLUMN LogTransp.F_ELLOX_SYNC_CONFIG.NEXT_EXECUTION IS 'Timestamp da próxima execução agendada';
