"""
Funções de sincronização automática Ellox API - VERSÃO CORRIGIDA
Integração com database.py para gerenciar logs e configurações
"""

from database import get_database_connection
from sqlalchemy import text
import json
from datetime import datetime, timedelta


def get_sync_config():
    """
    Retorna a configuração atual de sincronização automática Ellox.
    
    Returns:
        dict: Configuração com campos enabled, interval_minutes, max_retries, 
              last_execution, next_execution
    """
    conn = get_database_connection()
    try:
        query = text("""
            SELECT SYNC_ENABLED, SYNC_INTERVAL_MINUTES, MAX_RETRIES, 
                   LAST_EXECUTION, NEXT_EXECUTION, UPDATED_AT
            FROM LogTransp.F_ELLOX_SYNC_CONFIG 
            WHERE ID = 1
        """)
        result = conn.execute(query).fetchone()
        
        if result:
            return {
                'enabled': bool(result[0]),
                'interval_minutes': result[1],
                'max_retries': result[2],
                'last_execution': result[3],
                'next_execution': result[4],
                'updated_at': result[5]
            }
        else:
            # Configuração padrão se não existir
            return {
                'enabled': True,
                'interval_minutes': 60,
                'max_retries': 3,
                'last_execution': None,
                'next_execution': None,
                'updated_at': None
            }
    finally:
        conn.close()


def update_sync_config(enabled, interval_minutes, updated_by="SYSTEM"):
    """
    Atualiza a configuração de sincronização automática.
    
    Args:
        enabled (bool): Se a sincronização está ativa
        interval_minutes (int): Intervalo entre sincronizações em minutos
        updated_by (str): Usuário que fez a alteração
    """
    conn = get_database_connection()
    try:
        query = text("""
            UPDATE LogTransp.F_ELLOX_SYNC_CONFIG 
            SET SYNC_ENABLED = :enabled,
                SYNC_INTERVAL_MINUTES = :interval_minutes,
                UPDATED_BY = :updated_by,
                UPDATED_AT = SYSTIMESTAMP
            WHERE ID = 1
        """)
        conn.execute(query, {
            'enabled': 1 if enabled else 0,
            'interval_minutes': interval_minutes,
            'updated_by': updated_by
        })
        conn.commit()
    finally:
        conn.close()


def log_sync_execution(vessel, voyage, terminal, status, changes_detected=0, 
                      error_message=None, retry_attempt=0, execution_time_ms=0, 
                      fields_changed=None, user_id="SYSTEM"):
    """
    Registra uma execução de sincronização no log.
    
    Args:
        vessel (str): Nome do navio
        voyage (str): Código da viagem
        terminal (str): Terminal
        status (str): Status da execução (SUCCESS, NO_CHANGES, API_ERROR, etc.)
        changes_detected (int): Número de campos alterados
        error_message (str): Mensagem de erro se houver
        retry_attempt (int): Número da tentativa (0 = primeira)
        execution_time_ms (int): Tempo de execução em milissegundos
        fields_changed (str): JSON com campos alterados
        user_id (str): ID do usuário que executou
    """
    conn = get_database_connection()
    try:
        query = text("""
            INSERT INTO LogTransp.F_ELLOX_SYNC_LOGS 
            (VESSEL_NAME, VOYAGE_CODE, TERMINAL, STATUS, CHANGES_DETECTED, 
             ERROR_MESSAGE, RETRY_ATTEMPT, EXECUTION_TIME_MS, USER_ID, FIELDS_CHANGED)
            VALUES (:vessel, :voyage, :terminal, :status, :changes, 
                    :error, :retry, :execution_time, :user_id, :fields_changed)
        """)
        conn.execute(query, {
            'vessel': vessel,
            'voyage': voyage,
            'terminal': terminal,
            'status': status,
            'changes': changes_detected,
            'error': error_message,
            'retry': retry_attempt,
            'execution_time': execution_time_ms,
            'user_id': user_id,
            'fields_changed': fields_changed
        })
        conn.commit()
    finally:
        conn.close()


def get_sync_logs(filters=None, limit=1000):
    """
    Busca logs de sincronização com filtros opcionais.
    
    Args:
        filters (dict): Filtros opcionais com keys: 
                       start_date, end_date, status, vessel, voyage, terminal
        limit (int): Limite de registros retornados
    
    Returns:
        list: Lista de dicionários com os logs
    """
    conn = get_database_connection()
    try:
        where_conditions = []
        params = {}
        
        if filters:
            if filters.get('start_date'):
                where_conditions.append("SYNC_TIMESTAMP >= :start_date")
                params['start_date'] = filters['start_date']
            
            if filters.get('end_date'):
                where_conditions.append("SYNC_TIMESTAMP <= :end_date")
                params['end_date'] = filters['end_date']
            
            if filters.get('status'):
                where_conditions.append("STATUS = :status")
                params['status'] = filters['status']
            
            if filters.get('vessel'):
                where_conditions.append("UPPER(VESSEL_NAME) LIKE UPPER(:vessel)")
                params['vessel'] = f"%{filters['vessel']}%"
            
            if filters.get('voyage'):
                where_conditions.append("UPPER(VOYAGE_CODE) LIKE UPPER(:voyage)")
                params['voyage'] = f"%{filters['voyage']}%"
            
            if filters.get('terminal'):
                where_conditions.append("UPPER(TERMINAL) LIKE UPPER(:terminal)")
                params['terminal'] = f"%{filters['terminal']}%"
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        query = text(f"""
            SELECT ID, SYNC_TIMESTAMP, VESSEL_NAME, VOYAGE_CODE, TERMINAL, 
                   STATUS, CHANGES_DETECTED, ERROR_MESSAGE, RETRY_ATTEMPT, 
                   EXECUTION_TIME_MS, USER_ID, FIELDS_CHANGED
            FROM LogTransp.F_ELLOX_SYNC_LOGS 
            {where_clause}
            ORDER BY SYNC_TIMESTAMP DESC
            FETCH FIRST :limit ROWS ONLY
        """)
        
        params['limit'] = limit
        result = conn.execute(query, params).fetchall()
        
        logs = []
        for row in result:
            logs.append({
                'id': row[0],
                'sync_timestamp': row[1],
                'vessel_name': row[2],
                'voyage_code': row[3],
                'terminal': row[4],
                'status': row[5],
                'changes_detected': row[6],
                'error_message': row[7],
                'retry_attempt': row[8],
                'execution_time_ms': row[9],
                'user_id': row[10],
                'fields_changed': row[11]
            })
        
        return logs
    finally:
        conn.close()


def get_sync_statistics(days=30):
    """
    Retorna estatísticas de sincronização para o período especificado.
    
    Args:
        days (int): Número de dias para análise (padrão: 30)
    
    Returns:
        dict: Estatísticas com total_executions, success_rate, active_voyages, etc.
    """
    conn = get_database_connection()
    try:
        # Calcular data de início
        from datetime import datetime, timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        # Estatísticas gerais
        stats_query = text("""
            SELECT 
                COUNT(*) as total_executions,
                SUM(CASE WHEN STATUS = 'SUCCESS' THEN 1 ELSE 0 END) as successful_executions,
                SUM(CASE WHEN STATUS = 'NO_CHANGES' THEN 1 ELSE 0 END) as no_changes_executions,
                SUM(CASE WHEN STATUS LIKE '%ERROR%' THEN 1 ELSE 0 END) as error_executions,
                AVG(EXECUTION_TIME_MS) as avg_execution_time_ms,
                SUM(CHANGES_DETECTED) as total_changes_detected
            FROM LogTransp.F_ELLOX_SYNC_LOGS 
            WHERE SYNC_TIMESTAMP >= :start_date
        """)
        
        stats_result = conn.execute(stats_query, {'start_date': start_date}).fetchone()
        
        # Viagens ativas (sem B_DATA_CHEGADA_DESTINO_ATA)
        active_voyages_query = text("""
            SELECT COUNT(DISTINCT NAVIO || '|' || VIAGEM || '|' || TERMINAL) as active_voyages
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS 
            WHERE B_DATA_CHEGADA_DESTINO_ATA IS NULL
              AND NAVIO IS NOT NULL 
              AND VIAGEM IS NOT NULL
        """)
        
        active_result = conn.execute(active_voyages_query).fetchone()
        
        # Última execução
        last_execution_query = text("""
            SELECT MAX(SYNC_TIMESTAMP) as last_execution
            FROM LogTransp.F_ELLOX_SYNC_LOGS
        """)
        
        last_result = conn.execute(last_execution_query).fetchone()
        
        total_executions = stats_result[0] or 0
        successful_executions = stats_result[1] or 0
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'no_changes_executions': stats_result[2] or 0,
            'error_executions': stats_result[3] or 0,
            'success_rate': round(success_rate, 2),
            'avg_execution_time_ms': round(stats_result[4] or 0, 2),
            'total_changes_detected': stats_result[5] or 0,
            'active_voyages': active_result[0] or 0,
            'last_execution': last_result[0],
            'period_days': days
        }
    finally:
        conn.close()


def get_active_voyages_for_sync():
    """
    Retorna lista de viagens ativas que precisam ser sincronizadas.
    Viagens ativas = sem B_DATA_CHEGADA_DESTINO_ATA preenchido.
    
    Returns:
        list: Lista de dicionários com vessel, voyage, terminal
    """
    conn = get_database_connection()
    try:
        query = text("""
            SELECT DISTINCT NAVIO, VIAGEM, TERMINAL
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS 
            WHERE B_DATA_CHEGADA_DESTINO_ATA IS NULL
              AND NAVIO IS NOT NULL 
              AND VIAGEM IS NOT NULL
              AND TERMINAL IS NOT NULL
            ORDER BY NAVIO, VIAGEM, TERMINAL
        """)
        
        result = conn.execute(query).fetchall()
        
        voyages = []
        for row in result:
            voyages.append({
                'vessel': row[0],
                'voyage': row[1],
                'terminal': row[2]
            })
        
        return voyages
    finally:
        conn.close()
