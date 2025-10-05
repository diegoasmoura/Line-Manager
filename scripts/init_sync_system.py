#!/usr/bin/env python3
"""
Script de Inicialização do Sistema de Sincronização Automática Ellox
Configura e testa o sistema de sincronização
"""

import os
import sys
import subprocess
from pathlib import Path

# Adicionar o diretório raiz ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_header():
    print("=" * 60)
    print("🔄 SISTEMA DE SINCRONIZAÇÃO AUTOMÁTICA ELLOX")
    print("   Script de Inicialização e Configuração")
    print("=" * 60)
    print()

def check_dependencies():
    """Verifica se as dependências estão instaladas"""
    print("📦 Verificando dependências...")
    
    try:
        import APScheduler
        print("✅ APScheduler instalado")
    except ImportError:
        print("❌ APScheduler não encontrado")
        print("   Execute: pip install APScheduler>=3.10.0")
        return False
    
    try:
        from ellox_sync_functions import get_sync_config
        print("✅ Módulos de sincronização carregados")
    except ImportError as e:
        print(f"❌ Erro ao carregar módulos: {e}")
        return False
    
    return True

def create_directories():
    """Cria diretórios necessários"""
    print("\n📁 Criando diretórios...")
    
    directories = ['logs', '.streamlit/sessions']
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}/")

def test_database_connection():
    """Testa conexão com o banco de dados"""
    print("\n🗄️ Testando conexão com banco de dados...")
    
    try:
        from database import get_database_connection
        conn = get_database_connection()
        conn.close()
        print("✅ Conexão com banco Oracle estabelecida")
        return True
    except Exception as e:
        print(f"❌ Erro na conexão com banco: {e}")
        return False

def create_tables():
    """Cria as tabelas necessárias"""
    print("\n🏗️ Criando tabelas de sincronização...")
    
    try:
        from database import get_database_connection
        from sqlalchemy import text
        
        # Ler script SQL
        sql_file = project_root / 'scripts' / 'create_sync_tables.sql'
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Executar comandos SQL
        conn = get_database_connection()
        try:
            # Dividir em comandos individuais
            commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
            
            for command in commands:
                if command.upper().startswith(('CREATE', 'INSERT', 'COMMENT')):
                    try:
                        conn.execute(text(command))
                        print(f"✅ Executado: {command[:50]}...")
                    except Exception as e:
                        if "already exists" in str(e).lower() or "already indexed" in str(e).lower():
                            print(f"ℹ️ Já existe: {command[:50]}...")
                        else:
                            print(f"⚠️ Aviso: {e}")
            
            conn.commit()
            print("✅ Tabelas criadas com sucesso")
            return True
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        return False

def test_sync_functions():
    """Testa as funções de sincronização"""
    print("\n🧪 Testando funções de sincronização...")
    
    try:
        from ellox_sync_functions import get_sync_config, get_active_voyages_for_sync
        
        # Testar configuração
        config = get_sync_config()
        print(f"✅ Configuração carregada: enabled={config['enabled']}, interval={config['interval_minutes']}min")
        
        # Testar busca de viagens ativas
        voyages = get_active_voyages_for_sync()
        print(f"✅ Viagens ativas encontradas: {len(voyages)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar funções: {e}")
        return False

def test_api_connection():
    """Testa conexão com API Ellox"""
    print("\n🌐 Testando conexão com API Ellox...")
    
    try:
        from ellox_api import ElloxAPI
        from app_config import ELLOX_API_CONFIG
        
        # Criar cliente de teste
        client = ElloxAPI(
            email=ELLOX_API_CONFIG['email'],
            password=ELLOX_API_CONFIG['password'],
            base_url=ELLOX_API_CONFIG['base_url']
        )
        
        # Testar conexão
        result = client.test_connection()
        
        if result.get('success'):
            print("✅ Conexão com API Ellox estabelecida")
            return True
        else:
            print(f"⚠️ API Ellox: {result.get('message', 'Erro desconhecido')}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na conexão com API Ellox: {e}")
        print("   Verifique as credenciais em app_config.py")
        return False

def show_next_steps():
    """Mostra próximos passos"""
    print("\n" + "=" * 60)
    print("🎉 CONFIGURAÇÃO CONCLUÍDA!")
    print("=" * 60)
    print()
    print("📋 PRÓXIMOS PASSOS:")
    print()
    print("1. 🔧 CONFIGURAR SINCRONIZAÇÃO:")
    print("   - Acesse o sistema Farol")
    print("   - Vá para Setup → Sincronização Automática")
    print("   - Configure intervalo e ative a sincronização")
    print()
    print("2. 🚀 INICIAR DAEMON:")
    print("   python ellox_sync_daemon.py")
    print()
    print("3. 📊 MONITORAR LOGS:")
    print("   - Tracking → Sync Logs (apenas ADMIN)")
    print("   - Ou: tail -f logs/ellox_sync_daemon.log")
    print()
    print("4. 🧪 TESTAR MANUALMENTE:")
    print("   python ellox_sync_daemon.py sync-now")
    print()
    print("5. 📈 VERIFICAR STATUS:")
    print("   python ellox_sync_daemon.py status")
    print()
    print("=" * 60)

def main():
    """Função principal"""
    print_header()
    
    # Verificar dependências
    if not check_dependencies():
        print("\n❌ Falha na verificação de dependências")
        return False
    
    # Criar diretórios
    create_directories()
    
    # Testar banco de dados
    if not test_database_connection():
        print("\n❌ Falha na conexão com banco de dados")
        return False
    
    # Criar tabelas
    if not create_tables():
        print("\n❌ Falha na criação de tabelas")
        return False
    
    # Testar funções
    if not test_sync_functions():
        print("\n❌ Falha no teste de funções")
        return False
    
    # Testar API (opcional)
    api_ok = test_api_connection()
    if not api_ok:
        print("\n⚠️ API Ellox não disponível - configure credenciais em app_config.py")
    
    # Mostrar próximos passos
    show_next_steps()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
