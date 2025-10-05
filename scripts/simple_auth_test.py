"""
Teste simples do sistema de autenticação (sem Streamlit)
"""
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auth.auth_db import (
    hash_password, verify_password, authenticate_user,
    list_users, get_business_units, get_db_connection
)

def test_basic_functions():
    """Testa funções básicas sem Streamlit"""
    print("🧪 Teste Simples do Sistema de Autenticação")
    print("=" * 50)
    
    # Teste 1: Funções de senha
    print("🔐 Testando funções de senha...")
    password = "TestPassword123"
    hashed = hash_password(password)
    assert verify_password(password, hashed), "Verificação de senha falhou"
    print("✅ Funções de senha funcionando")
    
    # Teste 2: Conexão com banco
    print("\n🗄️ Testando conexão com banco...")
    users = list_users()
    print(f"✅ {len(users)} usuários encontrados no banco")
    if users:
        print(f"   Chaves disponíveis: {list(users[0].keys())}")
        print(f"   Primeiro usuário: {users[0]}")
    
    # Teste 3: Usuário admin
    print("\n👤 Testando usuário admin...")
    admin_users = [u for u in users if u['username'] == 'admin']
    if admin_users:
        admin = admin_users[0]
        print(f"✅ Usuário admin encontrado: {admin['full_name']}")
        print(f"   Nível de acesso: {admin['access_level']}")
        print(f"   Status: {'Ativo' if admin['is_active'] == 1 else 'Inativo'}")
    else:
        print("❌ Usuário admin não encontrado")
        return False
    
    # Teste 4: Autenticação
    print("\n🔑 Testando autenticação...")
    
    # Primeiro, vamos verificar o hash da senha no banco
    print("   Verificando hash da senha no banco...")
    from sqlalchemy import text
    conn = get_db_connection()
    try:
        query = text("SELECT PASSWORD_HASH FROM LogTransp.F_CON_USERS WHERE USERNAME = 'admin'")
        result = conn.execute(query).fetchone()
        if result:
            stored_hash = result[0]
            print(f"   Hash armazenado: {stored_hash[:20]}...")
            
            # Testar verificação de senha diretamente
            is_valid = verify_password("Admin@2025", stored_hash)
            print(f"   Verificação direta da senha: {'✅' if is_valid else '❌'}")
        else:
            print("   ❌ Usuário admin não encontrado no banco")
    finally:
        conn.close()
    
    user_data = authenticate_user("admin", "Admin@2025")
    if user_data:
        print("✅ Autenticação do admin funcionando")
        print(f"   Dados retornados: {list(user_data.keys())}")
    else:
        print("❌ Falha na autenticação do admin")
        return False
    
    # Teste 5: Unidades de negócio
    print("\n🏢 Testando unidades de negócio...")
    business_units = get_business_units()
    print(f"✅ Unidades disponíveis: {[u['UNIT_NAME'] for u in business_units]}")
    
    print("\n🎉 Todos os testes básicos passaram!")
    return True

if __name__ == "__main__":
    success = test_basic_functions()
    sys.exit(0 if success else 1)
