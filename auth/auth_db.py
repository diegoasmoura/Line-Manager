"""
Módulo de autenticação com banco de dados Oracle
Sistema de login seguro com bcrypt e controle de acesso por níveis
"""
import bcrypt
from datetime import datetime
from sqlalchemy import text
from typing import Optional, Dict, List
import streamlit as st

def get_db_connection():
    """Importa e retorna conexão do database.py"""
    from database import get_database_connection
    return get_database_connection()

# ========================================
# FUNÇÕES DE SENHA
# ========================================

def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

# ========================================
# AUTENTICAÇÃO
# ========================================

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Autentica usuário e retorna dados se sucesso.
    """
    conn = get_db_connection()
    
    try:
        # Buscar usuário
        query = text("""
            SELECT USER_ID, USERNAME, EMAIL, PASSWORD_HASH, FULL_NAME, 
                   BUSINESS_UNIT, ACCESS_LEVEL, IS_ACTIVE, 
                   PASSWORD_RESET_REQUIRED
            FROM LogTransp.F_CON_USERS
            WHERE UPPER(USERNAME) = UPPER(:username)
        """)
        result = conn.execute(query, {"username": username}).fetchone()
        
        if not result:
            return None
        
        user_data = dict(result._mapping)
        
        # Verificar se usuário está ativo
        if user_data['is_active'] != 1:
            return None
        
        # Verificar senha
        if not verify_password(password, user_data['password_hash']):
            return None
        
        # Atualizar último login
        update_query = text("""
            UPDATE LogTransp.F_CON_USERS
            SET LAST_LOGIN = SYSTIMESTAMP
            WHERE USER_ID = :user_id
        """)
        conn.execute(update_query, {"user_id": user_data['user_id']})
        conn.commit()
        
        # Remover hash da senha do retorno
        user_data.pop('password_hash', None)
        
        return user_data
        
    except Exception as e:
        print(f"Erro na autenticação: {str(e)}")
        return None
    finally:
        conn.close()

# ========================================
# GESTÃO DE USUÁRIOS (ADMIN)
# ========================================

def create_user(username: str, email: str, password: str, full_name: str,
                business_unit: Optional[str], access_level: str,
                created_by: str) -> bool:
    """Cria novo usuário (apenas admin)"""
    conn = get_db_connection()
    
    try:
        password_hash = hash_password(password)
        
        query = text("""
            INSERT INTO LogTransp.F_CON_USERS 
                (USER_ID, USERNAME, EMAIL, PASSWORD_HASH, FULL_NAME, BUSINESS_UNIT, 
                 ACCESS_LEVEL, CREATED_BY, PASSWORD_RESET_REQUIRED)
            VALUES (LogTransp.SEQ_F_CON_USERS.NEXTVAL, :username, :email, :password_hash, :full_name, :business_unit,
                    :access_level, :created_by, 1)
        """)
        
        conn.execute(query, {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "business_unit": business_unit,
            "access_level": access_level,
            "created_by": created_by
        })
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Erro ao criar usuário: {str(e)}")
        return False
    finally:
        conn.close()

def update_user(user_id: int, email: str, full_name: str,
                business_unit: Optional[str], access_level: str,
                is_active: int, updated_by: str) -> bool:
    """Atualiza dados do usuário (apenas admin)"""
    conn = get_db_connection()
    
    try:
        query = text("""
            UPDATE LogTransp.F_CON_USERS
            SET EMAIL = :email,
                FULL_NAME = :full_name,
                BUSINESS_UNIT = :business_unit,
                ACCESS_LEVEL = :access_level,
                IS_ACTIVE = :is_active,
                UPDATED_AT = SYSTIMESTAMP,
                UPDATED_BY = :updated_by
            WHERE USER_ID = :user_id
        """)
        
        conn.execute(query, {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "business_unit": business_unit,
            "access_level": access_level,
            "is_active": is_active,
            "updated_by": updated_by
        })
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Erro ao atualizar usuário: {str(e)}")
        return False
    finally:
        conn.close()

def reset_user_password(user_id: int, new_password: str, updated_by: str) -> bool:
    """Reset de senha do usuário (admin ou próprio usuário)"""
    conn = get_db_connection()
    
    try:
        password_hash = hash_password(new_password)
        
        query = text("""
            UPDATE LogTransp.F_CON_USERS
            SET PASSWORD_HASH = :password_hash,
                PASSWORD_RESET_REQUIRED = 0,
                UPDATED_AT = SYSTIMESTAMP,
                UPDATED_BY = :updated_by
            WHERE USER_ID = :user_id
        """)
        
        conn.execute(query, {
            "user_id": user_id,
            "password_hash": password_hash,
            "updated_by": updated_by
        })
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Erro ao resetar senha: {str(e)}")
        return False
    finally:
        conn.close()

def list_users() -> List[Dict]:
    """Lista todos os usuários (apenas admin)"""
    conn = get_db_connection()
    
    try:
        query = text("""
            SELECT USER_ID, USERNAME, EMAIL, FULL_NAME, BUSINESS_UNIT,
                   ACCESS_LEVEL, IS_ACTIVE, CREATED_AT, LAST_LOGIN
            FROM LogTransp.F_CON_USERS
            ORDER BY USERNAME
        """)
        result = conn.execute(query).fetchall()
        return [dict(row._mapping) for row in result]
        
    except Exception:
        return []
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Busca usuário por ID"""
    conn = get_db_connection()
    
    try:
        query = text("""
            SELECT USER_ID, USERNAME, EMAIL, FULL_NAME, BUSINESS_UNIT,
                   ACCESS_LEVEL, IS_ACTIVE, CREATED_AT, LAST_LOGIN
            FROM LogTransp.F_CON_USERS
            WHERE USER_ID = :user_id
        """)
        result = conn.execute(query, {"user_id": user_id}).fetchone()
        
        if result:
            return dict(result._mapping)
        return None
        
    except Exception:
        return None
    finally:
        conn.close()

def get_business_units() -> List[Dict]:
    """Lista unidades de negócio disponíveis"""
    # Por enquanto, retorna unidades hardcoded
    # Em produção, pode vir de uma tabela específica
    return [
        {"UNIT_CODE": "COTTON", "UNIT_NAME": "Cotton"},
        {"UNIT_CODE": "FOOD", "UNIT_NAME": "Food"},
        {"UNIT_CODE": "ALL", "UNIT_NAME": "Todas"}
    ]

def check_username_exists(username: str) -> bool:
    """Verifica se username já existe"""
    conn = get_db_connection()
    
    try:
        query = text("""
            SELECT COUNT(*) FROM LogTransp.F_CON_USERS 
            WHERE UPPER(USERNAME) = UPPER(:username)
        """)
        result = conn.execute(query, {"username": username}).fetchone()
        return result[0] > 0
    except Exception:
        return False
    finally:
        conn.close()

def check_email_exists(email: str) -> bool:
    """Verifica se email já existe"""
    conn = get_db_connection()
    
    try:
        query = text("""
            SELECT COUNT(*) FROM LogTransp.F_CON_USERS 
            WHERE UPPER(EMAIL) = UPPER(:email)
        """)
        result = conn.execute(query, {"email": email}).fetchone()
        return result[0] > 0
    except Exception:
        return False
    finally:
        conn.close()
