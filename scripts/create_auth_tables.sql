-- ========================================
-- Sistema de Autenticação Farol
-- DDL para criação das tabelas de usuários
-- ========================================

-- Sequência para USER_ID
CREATE SEQUENCE LogTransp.SEQ_F_CON_USERS START WITH 1 INCREMENT BY 1;

-- Tabela principal de usuários do sistema
CREATE TABLE LogTransp.F_CON_USERS (
  USER_ID           NUMBER PRIMARY KEY,
  USERNAME          VARCHAR2(150 CHAR) NOT NULL UNIQUE,
  EMAIL             VARCHAR2(255 CHAR) NOT NULL UNIQUE,
  PASSWORD_HASH     VARCHAR2(255 CHAR) NOT NULL,
  FULL_NAME         VARCHAR2(255 CHAR) NOT NULL,
  BUSINESS_UNIT     VARCHAR2(50 CHAR),
  ACCESS_LEVEL      VARCHAR2(20 CHAR) NOT NULL,
  IS_ACTIVE         NUMBER(1) DEFAULT 1 NOT NULL,
  CREATED_AT        TIMESTAMP(6) DEFAULT SYSTIMESTAMP NOT NULL,
  CREATED_BY        VARCHAR2(150 CHAR),
  UPDATED_AT        TIMESTAMP(6),
  UPDATED_BY        VARCHAR2(150 CHAR),
  LAST_LOGIN        TIMESTAMP(6),
  PASSWORD_RESET_REQUIRED NUMBER(1) DEFAULT 0,
  CONSTRAINT CK_ACCESS_LEVEL CHECK (ACCESS_LEVEL IN ('VIEW', 'EDIT', 'ADMIN')),
  CONSTRAINT CK_IS_ACTIVE CHECK (IS_ACTIVE IN (0, 1)),
  CONSTRAINT CK_RESET_REQUIRED CHECK (PASSWORD_RESET_REQUIRED IN (0, 1))
);

-- Comentários da tabela e colunas
COMMENT ON TABLE LogTransp.F_CON_USERS IS 'Usuários do sistema Farol com autenticação e controle de acesso.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.USER_ID IS 'Chave primária (auto-incremento).';
COMMENT ON COLUMN LogTransp.F_CON_USERS.USERNAME IS 'Nome de usuário único para login.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.EMAIL IS 'Email único do usuário.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.PASSWORD_HASH IS 'Hash bcrypt da senha (60 caracteres).';
COMMENT ON COLUMN LogTransp.F_CON_USERS.FULL_NAME IS 'Nome completo do usuário.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.BUSINESS_UNIT IS 'Unidade de negócio (Cotton, Food, etc). NULL = acesso a todas.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.ACCESS_LEVEL IS 'Nível de acesso: VIEW (visualização), EDIT (edição), ADMIN (administrador).';
COMMENT ON COLUMN LogTransp.F_CON_USERS.IS_ACTIVE IS '1 = ativo, 0 = inativo/desabilitado.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.CREATED_AT IS 'Data/hora de criação do usuário.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.CREATED_BY IS 'Quem criou o usuário (username do admin).';
COMMENT ON COLUMN LogTransp.F_CON_USERS.UPDATED_AT IS 'Data/hora da última atualização.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.UPDATED_BY IS 'Quem fez a última atualização (username do admin).';
COMMENT ON COLUMN LogTransp.F_CON_USERS.LAST_LOGIN IS 'Data/hora do último login bem-sucedido.';
COMMENT ON COLUMN LogTransp.F_CON_USERS.PASSWORD_RESET_REQUIRED IS '1 = usuário deve trocar senha no próximo login.';

-- Índices para performance
CREATE INDEX IX_USERS_USERNAME ON LogTransp.F_CON_USERS(USERNAME);
CREATE INDEX IX_USERS_EMAIL ON LogTransp.F_CON_USERS(EMAIL);
CREATE INDEX IX_USERS_BUSINESS_UNIT ON LogTransp.F_CON_USERS(BUSINESS_UNIT);
CREATE INDEX IX_USERS_ACTIVE ON LogTransp.F_CON_USERS(IS_ACTIVE);
CREATE INDEX IX_USERS_ACCESS_LEVEL ON LogTransp.F_CON_USERS(ACCESS_LEVEL);

-- Verificar se a tabela foi criada com sucesso
SELECT 'Tabela F_CON_USERS criada com sucesso!' AS STATUS FROM DUAL;
