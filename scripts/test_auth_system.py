"""
Script de teste para o sistema de autenticação Farol
Valida todas as funcionalidades implementadas
"""
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auth.auth_db import (
    hash_password, verify_password, authenticate_user,
    create_user, update_user, reset_user_password,
    list_users, get_user_by_id, check_username_exists,
    check_email_exists, get_business_units
)
from auth.login import has_access_level, get_user_info
import bcrypt

def test_password_functions():
    """Testa funções de hash e verificação de senhas"""
    print("🔐 Testando funções de senha...")
    
    # Teste 1: Hash de senha
    password = "TestPassword123"
    hashed = hash_password(password)
    
    assert len(hashed) == 60, f"Hash deve ter 60 caracteres, tem {len(hashed)}"
    assert hashed.startswith('$2b$'), "Hash deve começar com $2b$"
    print("✅ Hash de senha funcionando")
    
    # Teste 2: Verificação de senha
    assert verify_password(password, hashed), "Verificação de senha correta falhou"
    assert not verify_password("WrongPassword", hashed), "Verificação de senha incorreta passou"
    print("✅ Verificação de senha funcionando")
    
    # Teste 3: Compatibilidade com bcrypt
    bcrypt_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    assert verify_password(password, bcrypt_hash), "Compatibilidade com bcrypt falhou"
    print("✅ Compatibilidade com bcrypt funcionando")

def test_database_connection():
    """Testa conexão com banco de dados"""
    print("\n🗄️ Testando conexão com banco...")
    
    try:
        users = list_users()
        print(f"✅ Conexão com banco funcionando. {len(users)} usuários encontrados")
        return True
    except Exception as e:
        print(f"❌ Erro na conexão com banco: {str(e)}")
        return False

def test_user_management():
    """Testa funções de gestão de usuários"""
    print("\n👥 Testando gestão de usuários...")
    
    try:
        # Teste 1: Listar usuários
        users = list_users()
        print(f"✅ Listagem de usuários: {len(users)} usuários")
        
        # Teste 2: Verificar usuário admin
        admin_users = [u for u in users if u['USERNAME'] == 'admin']
        if admin_users:
            admin = admin_users[0]
            assert admin['ACCESS_LEVEL'] == 'ADMIN', "Usuário admin deve ter nível ADMIN"
            print("✅ Usuário admin encontrado e configurado corretamente")
        else:
            print("⚠️ Usuário admin não encontrado")
        
        # Teste 3: Verificar unidades de negócio
        business_units = get_business_units()
        assert len(business_units) > 0, "Deve haver unidades de negócio disponíveis"
        print(f"✅ Unidades de negócio: {[u['UNIT_NAME'] for u in business_units]}")
        
        return True
    except Exception as e:
        print(f"❌ Erro na gestão de usuários: {str(e)}")
        return False

def test_authentication():
    """Testa autenticação de usuários"""
    print("\n🔑 Testando autenticação...")
    
    try:
        # Teste 1: Autenticação com usuário admin
        user_data = authenticate_user("admin", "Admin@2025")
        if user_data:
            assert user_data['USERNAME'] == 'admin', "Username deve ser 'admin'"
            assert user_data['ACCESS_LEVEL'] == 'ADMIN', "Nível deve ser ADMIN"
            assert 'PASSWORD_HASH' not in user_data, "Hash não deve estar no retorno"
            print("✅ Autenticação do admin funcionando")
        else:
            print("❌ Falha na autenticação do admin")
            return False
        
        # Teste 2: Autenticação com credenciais incorretas
        user_data = authenticate_user("admin", "WrongPassword")
        assert user_data is None, "Autenticação com senha incorreta deve falhar"
        print("✅ Rejeição de senha incorreta funcionando")
        
        # Teste 3: Autenticação com usuário inexistente
        user_data = authenticate_user("nonexistent", "password")
        assert user_data is None, "Autenticação com usuário inexistente deve falhar"
        print("✅ Rejeição de usuário inexistente funcionando")
        
        return True
    except Exception as e:
        print(f"❌ Erro na autenticação: {str(e)}")
        return False

def test_access_control():
    """Testa controle de acesso"""
    print("\n🛡️ Testando controle de acesso...")
    
    try:
        # Simular dados de usuário no session_state
        import streamlit as st
        
        # Teste 1: Usuário ADMIN
        st.session_state.user_data = {
            'ACCESS_LEVEL': 'ADMIN',
            'USERNAME': 'admin',
            'FULL_NAME': 'Administrador'
        }
        
        assert has_access_level('VIEW'), "ADMIN deve ter acesso VIEW"
        assert has_access_level('EDIT'), "ADMIN deve ter acesso EDIT"
        assert has_access_level('ADMIN'), "ADMIN deve ter acesso ADMIN"
        print("✅ Controle de acesso ADMIN funcionando")
        
        # Teste 2: Usuário EDIT
        st.session_state.user_data = {
            'ACCESS_LEVEL': 'EDIT',
            'USERNAME': 'editor',
            'FULL_NAME': 'Editor'
        }
        
        assert has_access_level('VIEW'), "EDIT deve ter acesso VIEW"
        assert has_access_level('EDIT'), "EDIT deve ter acesso EDIT"
        assert not has_access_level('ADMIN'), "EDIT não deve ter acesso ADMIN"
        print("✅ Controle de acesso EDIT funcionando")
        
        # Teste 3: Usuário VIEW
        st.session_state.user_data = {
            'ACCESS_LEVEL': 'VIEW',
            'USERNAME': 'viewer',
            'FULL_NAME': 'Visualizador'
        }
        
        assert has_access_level('VIEW'), "VIEW deve ter acesso VIEW"
        assert not has_access_level('EDIT'), "VIEW não deve ter acesso EDIT"
        assert not has_access_level('ADMIN'), "VIEW não deve ter acesso ADMIN"
        print("✅ Controle de acesso VIEW funcionando")
        
        # Teste 4: Usuário não logado
        if 'user_data' in st.session_state:
            del st.session_state.user_data
        
        assert not has_access_level('VIEW'), "Usuário não logado não deve ter acesso"
        print("✅ Controle de acesso para usuário não logado funcionando")
        
        return True
    except Exception as e:
        print(f"❌ Erro no controle de acesso: {str(e)}")
        return False

def test_user_info():
    """Testa função get_user_info"""
    print("\nℹ️ Testando informações do usuário...")
    
    try:
        import streamlit as st
        from datetime import datetime
        
        # Simular usuário logado
        st.session_state.user_data = {
            'USERNAME': 'testuser',
            'FULL_NAME': 'Test User',
            'EMAIL': 'test@example.com',
            'BUSINESS_UNIT': 'COTTON',
            'ACCESS_LEVEL': 'EDIT'
        }
        st.session_state.login_time = datetime.now()
        
        user_info = get_user_info()
        
        assert user_info['username'] == 'testuser', "Username incorreto"
        assert user_info['full_name'] == 'Test User', "Nome completo incorreto"
        assert user_info['email'] == 'test@example.com', "Email incorreto"
        assert user_info['business_unit'] == 'COTTON', "Unidade de negócio incorreta"
        assert user_info['access_level'] == 'EDIT', "Nível de acesso incorreto"
        assert 'session_duration' in user_info, "Duração da sessão deve estar presente"
        
        print("✅ Informações do usuário funcionando")
        
        # Teste com usuário não logado
        if 'user_data' in st.session_state:
            del st.session_state.user_data
        if 'login_time' in st.session_state:
            del st.session_state.login_time
        
        user_info = get_user_info()
        assert user_info == {}, "Usuário não logado deve retornar dict vazio"
        print("✅ Informações do usuário não logado funcionando")
        
        return True
    except Exception as e:
        print(f"❌ Erro nas informações do usuário: {str(e)}")
        return False

def run_all_tests():
    """Executa todos os testes"""
    print("🧪 Iniciando testes do sistema de autenticação Farol")
    print("=" * 60)
    
    tests = [
        ("Funções de Senha", test_password_functions),
        ("Conexão com Banco", test_database_connection),
        ("Gestão de Usuários", test_user_management),
        ("Autenticação", test_authentication),
        ("Controle de Acesso", test_access_control),
        ("Informações do Usuário", test_user_info)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ Erro inesperado em {test_name}: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"📊 Resultado dos Testes: {passed}/{total} passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! Sistema de autenticação funcionando corretamente.")
        return True
    else:
        print("⚠️ Alguns testes falharam. Verifique os erros acima.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
