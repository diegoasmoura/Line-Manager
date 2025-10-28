"""
Serviço de Sincronização Automática Ellox API
Lógica core para sincronização de dados de viagens com detecção de mudanças
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ellox_sync_functions import (
    get_active_voyages_for_sync, 
    log_sync_execution,
    get_sync_config
)

from database import get_database_connection, validate_and_collect_voyage_monitoring
from sqlalchemy import text

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ellox_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_current_voyage_data(vessel: str, voyage: str, terminal: str) -> Optional[Dict]:
    """
    Busca dados atuais de uma viagem no banco de dados.
    
    Args:
        vessel (str): Nome do navio
        voyage (str): Código da viagem
        terminal (str): Terminal
    
    Returns:
        dict: Dados atuais da viagem ou None se não encontrado
    """
    conn = get_database_connection()
    try:
        query = text("""
            SELECT * FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS 
            WHERE NAVIO = :vessel 
              AND VIAGEM = :voyage 
              AND TERMINAL = :terminal
            ORDER BY ROW_INSERTED_DATE DESC
            FETCH FIRST 1 ROWS ONLY
        """)
        
        result = conn.execute(query, {
            'vessel': vessel,
            'voyage': voyage,
            'terminal': terminal
        }).fetchone()
        
        if result:
            # Converte para dicionário e garante chaves em maiúsculas
            return {k.upper(): v for k, v in dict(result._mapping).items()}
        return None
    finally:
        conn.close()


def detect_changes(current_data: Dict, new_data: Dict) -> Tuple[int, List[str]]:
    """
    Detecta mudanças entre dados atuais e novos dados da API.
    
    Args:
        current_data (dict): Dados atuais do banco
        new_data (dict): Novos dados da API
    
    Returns:
        tuple: (número_de_mudanças, lista_de_campos_alterados)
    """
    if not current_data or not new_data:
        return 0, []
    
    changes = []
    fields_to_compare = [
        'NAVIO', 'VIAGEM', 'TERMINAL', 'AGENCIA',
        'DATA_DEADLINE', 'DATA_DRAFT_DEADLINE', 'DATA_ABERTURA_GATE',
        'DATA_ABERTURA_GATE_REEFER', 'DATA_ESTIMATIVA_SAIDA',
        'DATA_ESTIMATIVA_CHEGADA', 'DATA_CHEGADA', 'DATA_ESTIMATIVA_ATRACACAO',
        'DATA_ATRACACAO', 'DATA_PARTIDA', 'DATA_ATUALIZACAO'
    ]
    
    for field in fields_to_compare:
        # Acessar chaves em minúsculas, como retornado por .mappings().fetchone() ou dict(result._mapping)
        current_value = current_data.get(field.lower())
        new_value = new_data.get(field.lower())
        
        # Normaliza valores para comparação (incluindo tratamento de datetime)
        current_normalized = str(current_value).strip() if current_value is not None else ''
        new_normalized = str(new_value).strip() if new_value is not None else ''
        
        if current_normalized != new_normalized:
            changes.append(field)
    
    return len(changes), changes





def sync_single_voyage(vessel: str, voyage: str, terminal: str) -> Dict:
    """
    Sincroniza uma única viagem com a API Ellox.
    
    Args:
        vessel (str): Nome do navio
        voyage (str): Código da viagem
        terminal (str): Terminal
    
    Returns:
        dict: Resultado da sincronização com status, mudanças, erro, etc.
    """
    start_time = time.time()
    result = {
        'vessel': vessel,
        'voyage': voyage,
        'terminal': terminal,
        'status': 'UNKNOWN',
        'changes_detected': 0,
        'fields_changed': [],
        'error_message': None,
        'execution_time_ms': 0
    }
    
    try:
        logger.info(f"Iniciando sincronização: {vessel} - {voyage} - {terminal}")
        
        # 1. Busca dados atuais
        current_data = get_current_voyage_data(vessel, voyage, terminal)
        
        # 2. Consulta API Ellox usando a função centralizada
        api_result = validate_and_collect_voyage_monitoring(
            vessel_name=vessel,
            voyage_code=voyage,
            terminal=terminal,
            save_to_db=True # A sincronização automática sempre salva no DB
        )

        if not api_result["success"]:
            result['status'] = 'API_ERROR'
            result['error_message'] = api_result["message"]
            logger.error(f"Erro na API para {vessel}-{voyage}: {api_result["message"]}")
            return result
        
        # Se a API retornou sucesso, mas sem dados (ex: voyage encontrada, mas sem monitoramento ativo)
        if not api_result["data"]:
            result['status'] = 'NO_DATA'
            result['error_message'] = api_result["message"]
            logger.warning(f"Nenhum dado de monitoramento ativo retornado pela API para {vessel}-{voyage}: {api_result["message"]}")
            return result
        
        api_data = api_result["data"] # Os dados detalhados vêm aqui
        
        # 3. Detecta mudanças
        # api_data já contém os dados da API (ou do cache local) no formato esperado
        changes_count, fields_changed = detect_changes(current_data, api_data)
        result['changes_detected'] = changes_count
        result['fields_changed'] = fields_changed
        
        if changes_count == 0:
            result['status'] = 'NO_CHANGES'
            logger.info(f"Nenhuma mudança para {vessel}-{voyage}")
        else:
            # Se houve mudanças, validate_and_collect_voyage_monitoring já salvou os dados
            result['status'] = 'SUCCESS'
            logger.info(f"Sincronização bem-sucedida para {vessel}-{voyage}: {changes_count} mudanças")
        
    except Exception as e:
        result['status'] = 'ERROR'
        result['error_message'] = f"Erro inesperado: {str(e)}"
        logger.error(f"Erro inesperado para {vessel}-{voyage}: {str(e)}")
    
    finally:
        # Calcula tempo de execução
        execution_time = (time.time() - start_time) * 1000
        result['execution_time_ms'] = round(execution_time, 2)
        
        # Log da execução
        log_sync_execution(
            vessel=vessel,
            voyage=voyage,
            terminal=terminal,
            status=result['status'],
            changes_detected=result['changes_detected'],
            error_message=result['error_message'],
            execution_time_ms=result['execution_time_ms'],
            fields_changed=json.dumps(result['fields_changed']) if result['fields_changed'] else None
        )
    
    return result


def sync_all_active_voyages() -> Dict:
    """
    Sincroniza todas as viagens ativas com a API Ellox.
    
    Returns:
        dict: Resumo da execução com estatísticas
    """
    logger.info("=== INICIANDO SINCRONIZAÇÃO DE TODAS AS VIAGENS ATIVAS ===")
    
    start_time = time.time()
    summary = {
        'total_voyages': 0,
        'successful': 0,
        'no_changes': 0,
        'errors': 0,
        'total_changes': 0,
        'execution_time_seconds': 0,
        'voyages_processed': []
    }
    
    try:
        # Busca viagens ativas
        active_voyages = get_active_voyages_for_sync()
        summary['total_voyages'] = len(active_voyages)
        
        logger.info(f"Encontradas {len(active_voyages)} viagens ativas para sincronizar")
        
        if not active_voyages:
            logger.info("Nenhuma viagem ativa encontrada")
            return summary
        
        # Processa cada viagem
        for voyage in active_voyages:
            vessel = voyage['vessel']
            voyage_code = voyage['voyage']
            terminal = voyage['terminal']
            
            result = sync_single_voyage(vessel, voyage_code, terminal)
            summary['voyages_processed'].append(result)
            
            # Atualiza contadores
            if result['status'] == 'SUCCESS':
                summary['successful'] += 1
                summary['total_changes'] += result['changes_detected']
            elif result['status'] == 'NO_CHANGES':
                summary['no_changes'] += 1
            else:
                summary['errors'] += 1
            
            # Pequena pausa entre requisições para não sobrecarregar a API
            time.sleep(0.5)
        
        # Calcula tempo total
        summary['execution_time_seconds'] = round(time.time() - start_time, 2)
        
        # Log do resumo
        logger.info(f"=== SINCRONIZAÇÃO CONCLUÍDA ===")
        logger.info(f"Total de viagens: {summary['total_voyages']}")
        logger.info(f"Sucessos: {summary['successful']}")
        logger.info(f"Sem mudanças: {summary['no_changes']}")
        logger.info(f"Erros: {summary['errors']}")
        logger.info(f"Total de mudanças: {summary['total_changes']}")
        logger.info(f"Tempo total: {summary['execution_time_seconds']}s")
        
        return summary
        
    except Exception as e:
        logger.error(f"Erro geral na sincronização: {str(e)}")
        summary['error'] = str(e)
        return summary


def force_sync_voyage(vessel: str, voyage: str, terminal: str) -> Dict:
    """
    Força sincronização de uma viagem específica (para uso manual).
    
    Args:
        vessel (str): Nome do navio
        voyage (str): Código da viagem
        terminal (str): Terminal
    
    Returns:
        dict: Resultado da sincronização
    """
    logger.info(f"=== SINCRONIZAÇÃO FORÇADA: {vessel} - {voyage} - {terminal} ===")
    return sync_single_voyage(vessel, voyage, terminal)


if __name__ == "__main__":
    # Teste manual do serviço
    print("Testando serviço de sincronização...")
    result = sync_all_active_voyages()
    print(f"Resultado: {result}")
