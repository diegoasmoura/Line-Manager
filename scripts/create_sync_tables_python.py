#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para criar tabelas de sincronização Ellox
Sistema: Farol v3.9.11
Data: 2025-10-05
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path para importar módulos
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import get_database_connection
from sqlalchemy import text

def create_sync_tables():
    """Cria as tabelas necessárias para o sistema de sincronização Ellox"""
    
    print("🚀 Iniciando criação das tabelas de sincronização Ellox...")
    
    try:
        with get_database_connection() as conn:
            # 1. Criar tabela F_ELLOX_SYNC_LOGS
            print("📊 Criando tabela F_ELLOX_SYNC_LOGS...")
            create_logs_table = text("""
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
                )
            """)
            conn.execute(create_logs_table)
            print("✅ Tabela F_ELLOX_SYNC_LOGS criada com sucesso!")
            
            # 2. Criar índices para F_ELLOX_SYNC_LOGS
            print("🔍 Criando índices para F_ELLOX_SYNC_LOGS...")
            indexes = [
                "CREATE INDEX LogTransp.IX_ELLOX_SYNC_LOGS_STATUS ON LogTransp.F_ELLOX_SYNC_LOGS (STATUS)",
                "CREATE INDEX LogTransp.IX_ELLOX_SYNC_LOGS_VESSEL ON LogTransp.F_ELLOX_SYNC_LOGS (VESSEL_NAME)",
                "CREATE INDEX LogTransp.IX_ELLOX_SYNC_LOGS_VOYAGE ON LogTransp.F_ELLOX_SYNC_LOGS (VOYAGE_CODE)",
                "CREATE INDEX LogTransp.IX_ELLOX_SYNC_LOGS_TERMINAL ON LogTransp.F_ELLOX_SYNC_LOGS (TERMINAL)",
                "CREATE INDEX LogTransp.IX_ELLOX_SYNC_LOGS_TIMESTAMP ON LogTransp.F_ELLOX_SYNC_LOGS (SYNC_TIMESTAMP DESC)"
            ]
            
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                except Exception as e:
                    if "already exists" in str(e).lower() or "already indexed" in str(e).lower():
                        print(f"⚠️  Índice já existe: {index_sql.split()[-1]}")
                    else:
                        raise e
            
            print("✅ Índices criados com sucesso!")
            
            # 3. Criar tabela F_ELLOX_SYNC_CONFIG
            print("⚙️  Criando tabela F_ELLOX_SYNC_CONFIG...")
            create_config_table = text("""
                CREATE TABLE LogTransp.F_ELLOX_SYNC_CONFIG (
                    ID NUMBER DEFAULT 1 PRIMARY KEY,
                    SYNC_ENABLED NUMBER(1) DEFAULT 1,
                    SYNC_INTERVAL_MINUTES NUMBER DEFAULT 60,
                    MAX_RETRIES NUMBER DEFAULT 3,
                    LAST_EXECUTION TIMESTAMP,
                    NEXT_EXECUTION TIMESTAMP,
                    UPDATED_BY VARCHAR2(50),
                    UPDATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
                )
            """)
            conn.execute(create_config_table)
            print("✅ Tabela F_ELLOX_SYNC_CONFIG criada com sucesso!")
            
            # 4. Inserir configuração inicial
            print("🔧 Inserindo configuração inicial...")
            insert_config = text("""
                INSERT INTO LogTransp.F_ELLOX_SYNC_CONFIG (ID, SYNC_ENABLED, SYNC_INTERVAL_MINUTES, MAX_RETRIES, UPDATED_BY)
                SELECT 1, 1, 60, 3, 'SYSTEM' FROM DUAL
                WHERE NOT EXISTS (SELECT 1 FROM LogTransp.F_ELLOX_SYNC_CONFIG WHERE ID = 1)
            """)
            conn.execute(insert_config)
            print("✅ Configuração inicial inserida!")
            
            # 5. Commit das alterações
            conn.commit()
            print("💾 Alterações commitadas com sucesso!")
            
            # 6. Verificar criação das tabelas
            print("\n📋 Verificando tabelas criadas...")
            check_tables = text("""
                SELECT 'F_ELLOX_SYNC_LOGS' as TABELA, COUNT(*) as REGISTROS FROM LogTransp.F_ELLOX_SYNC_LOGS
                UNION ALL
                SELECT 'F_ELLOX_SYNC_CONFIG' as TABELA, COUNT(*) as REGISTROS FROM LogTransp.F_ELLOX_SYNC_CONFIG
            """)
            result = conn.execute(check_tables).fetchall()
            
            for row in result:
                print(f"   {row[0]}: {row[1]} registros")
            
            print("\n🎉 Todas as tabelas de sincronização foram criadas com sucesso!")
            print("\n📝 Próximos passos:")
            print("   1. Acesse Setup → Sincronização Automática")
            print("   2. Configure o intervalo de sincronização")
            print("   3. Ative a sincronização automática")
            print("   4. Monitore os logs em Sync Logs")
            
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {str(e)}")
        print("\n🔧 Possíveis soluções:")
        print("   1. Verifique se tem permissões para criar tabelas no schema LogTransp")
        print("   2. Verifique se as tabelas já existem")
        print("   3. Verifique a conexão com o banco de dados")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 CRIADOR DE TABELAS DE SINCRONIZAÇÃO ELLOX")
    print("=" * 60)
    
    success = create_sync_tables()
    
    if success:
        print("\n✅ Script executado com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)
