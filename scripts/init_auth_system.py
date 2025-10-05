"""
Script de inicialização do sistema de autenticação Farol
Cria a tabela de usuários e o usuário administrador inicial
"""
import os
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import get_database_connection
from sqlalchemy import text
import bcrypt

def check_table_exists():
    """Verifica se a tabela F_CON_USERS já existe"""
    conn = get_database_connection()
    try:
        query = text("""
            SELECT COUNT(*) as table_count
            FROM user_tables 
            WHERE table_name = 'F_CON_USERS'
        """)
        result = conn.execute(query).fetchone()
        return result[0] > 0
    except Exception:
        return False
    finally:
        conn.close()

def create_auth_table():
    """Executa o DDL para criar a tabela de usuários"""
    conn = get_database_connection()
    try:
        # Comandos SQL separados
        sql_commands = [
            "CREATE SEQUENCE LogTransp.SEQ_F_CON_USERS START WITH 1 INCREMENT BY 1",
            """CREATE TABLE LogTransp.F_CON_USERS (
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
            )""",
            "CREATE INDEX IX_USERS_USERNAME ON LogTransp.F_CON_USERS(USERNAME)",
            "CREATE INDEX IX_USERS_EMAIL ON LogTransp.F_CON_USERS(EMAIL)",
            "CREATE INDEX IX_USERS_BUSINESS_UNIT ON LogTransp.F_CON_USERS(BUSINESS_UNIT)",
            "CREATE INDEX IX_USERS_ACTIVE ON LogTransp.F_CON_USERS(IS_ACTIVE)",
            "CREATE INDEX IX_USERS_ACCESS_LEVEL ON LogTransp.F_CON_USERS(ACCESS_LEVEL)"
        ]
        
        # Executar cada comando separadamente
        for sql in sql_commands:
            try:
                conn.execute(text(sql))
            except Exception as e:
                if "already exists" in str(e) or "already indexed" in str(e):
                    print(f"ℹ️ {sql.split()[1]} já existe, pulando...")
                    continue
                else:
                    raise e
        
        conn.commit()
        print("✅ Tabela F_CON_USERS criada com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {str(e)}")
        return False
    finally:
        conn.close()

def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_admin_user():
    """Cria o usuário administrador inicial"""
    conn = get_database_connection()
    try:
        # Verificar se admin já existe
        check_query = text("""
            SELECT COUNT(*) FROM LogTransp.F_CON_USERS 
            WHERE USERNAME = 'admin'
        """)
        result = conn.execute(check_query).fetchone()
        
        if result[0] > 0:
            print("⚠️ Usuário 'admin' já existe. Pulando criação.")
            return True
        
        # Criar usuário admin
        password_hash = hash_password("Admin@2025")
        
        insert_query = text("""
            INSERT INTO LogTransp.F_CON_USERS 
                (USER_ID, USERNAME, EMAIL, PASSWORD_HASH, FULL_NAME, 
                 BUSINESS_UNIT, ACCESS_LEVEL, CREATED_BY, PASSWORD_RESET_REQUIRED)
            VALUES (LogTransp.SEQ_F_CON_USERS.NEXTVAL, :username, :email, :password_hash, :full_name,
                    :business_unit, :access_level, :created_by, 1)
        """)
        
        conn.execute(insert_query, {
            "username": "admin",
            "email": "admin@farol.com",
            "password_hash": password_hash,
            "full_name": "Administrador do Sistema",
            "business_unit": None,  # Acesso a todas as unidades
            "access_level": "ADMIN",
            "created_by": "system"
        })
        conn.commit()
        
        print("✅ Usuário administrador criado com sucesso!")
        print("   Username: admin")
        print("   Password: Admin@2025")
        print("   Nível: Administrador")
        print("   ⚠️ IMPORTANTE: Troque a senha após o primeiro login!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar usuário admin: {str(e)}")
        return False
    finally:
        conn.close()

def init_auth_system():
    """Inicializa o sistema de autenticação completo"""
    print("🚀 Inicializando sistema de autenticação Farol...")
    print("=" * 50)
    
    # Verificar se tabela já existe
    if check_table_exists():
        print("ℹ️ Tabela F_CON_USERS já existe. Pulando criação.")
    else:
        print("📋 Criando tabela F_CON_USERS...")
        if not create_auth_table():
            print("❌ Falha na criação da tabela. Abortando.")
            return False
    
    # Criar usuário admin
    print("👤 Criando usuário administrador inicial...")
    if not create_admin_user():
        print("❌ Falha na criação do usuário admin.")
        return False
    
    print("=" * 50)
    print("✅ Sistema de autenticação inicializado com sucesso!")
    print("\n📝 Próximos passos:")
    print("1. Execute o sistema Farol")
    print("2. Faça login com: admin / Admin@2025")
    print("3. Acesse Setup > Administração de Usuários")
    print("4. Troque a senha do admin e crie outros usuários")
    
    return True

if __name__ == "__main__":
    success = init_auth_system()
    sys.exit(0 if success else 1)
