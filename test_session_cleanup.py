#!/usr/bin/env python3
"""
Script de teste para verificar a limpeza de sessões
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

def create_test_session():
    """Cria uma sessão de teste para verificar a limpeza"""
    sessions_dir = Path(".streamlit/sessions")
    sessions_dir.mkdir(exist_ok=True)
    
    # Criar sessão de teste
    test_session = {
        "username": "test_user",
        "user_data": {
            "user_id": 999,
            "username": "test_user",
            "email": "test@example.com",
            "full_name": "Test User",
            "business_unit": "TEST",
            "access_level": "ADMIN",
            "is_active": 1,
            "password_reset_required": 0
        },
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=8)).isoformat(),
        "last_activity": datetime.now().isoformat(),
        "streamlit_session_id": "test-session-id-12345"
    }
    
    # Salvar arquivo de sessão
    session_file = sessions_dir / "session_test-12345.json"
    with open(session_file, 'w') as f:
        json.dump(test_session, f, indent=2)
    
    print(f"✅ Sessão de teste criada: {session_file}")
    return session_file

def check_sessions():
    """Verifica quantas sessões existem"""
    sessions_dir = Path(".streamlit/sessions")
    if not sessions_dir.exists():
        print("❌ Pasta de sessões não existe")
        return 0
    
    session_files = list(sessions_dir.glob("session_*.json"))
    print(f"📊 Total de sessões encontradas: {len(session_files)}")
    
    for session_file in session_files:
        print(f"   - {session_file.name}")
    
    return len(session_files)

def main():
    print("🧪 Teste de Limpeza de Sessões")
    print("=" * 40)
    
    # Verificar estado inicial
    print("\n1. Estado inicial:")
    initial_count = check_sessions()
    
    # Criar sessão de teste
    print("\n2. Criando sessão de teste:")
    test_file = create_test_session()
    
    # Verificar se foi criada
    print("\n3. Após criação:")
    after_create_count = check_sessions()
    
    print(f"\n📈 Resumo:")
    print(f"   - Inicial: {initial_count} sessões")
    print(f"   - Após criar: {after_create_count} sessões")
    print(f"   - Diferença: +{after_create_count - initial_count}")
    
    print(f"\n💡 Próximos passos:")
    print(f"   1. Acesse http://localhost:8501")
    print(f"   2. Faça login (admin/Admin@2025)")
    print(f"   3. Faça logout")
    print(f"   4. Verifique se o arquivo de sessão foi removido")
    print(f"   5. Reinicie a aplicação para testar limpeza automática")

if __name__ == "__main__":
    main()
