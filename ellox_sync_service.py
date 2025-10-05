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
from ellox_api import get_voyage_monitoring_data
from database import get_database_connection
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
            # Converte para dicionário
            return dict(result._mapping)
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
        'B_ETA', 'B_ETD', 'B_ATA', 'B_ATD', 'B_DATA_CHEGADA_DESTINO_ATA',
        'B_DATA_SAIDA_DESTINO_ATD', 'B_STATUS', 'B_VESSEL_NAME', 'B_VOYAGE_CODE',
        'B_TERMINAL', 'B_CARRIER', 'B_ORIGIN', 'B_DESTINATION', 'B_CARGO_TYPE',
        'B_QUANTITY', 'B_UNIT', 'B_DEADLINE', 'B_COMMENTS'
    ]
    
    for field in fields_to_compare:
        current_value = current_data.get(field)
        new_value = new_data.get(field)
        
        # Normaliza valores para comparação
        if current_value is None and new_value is None:
            continue
        if current_value is None or new_value is None:
            changes.append(field)
            continue
        
        # Converte para string para comparação
        current_str = str(current_value).strip()
        new_str = str(new_value).strip()
        
        if current_str != new_str:
            changes.append(field)
    
    return len(changes), changes


def save_monitoring_update(voyage_data: Dict, data_source: str = 'API') -> bool:
    """
    Salva dados de monitoramento atualizados no banco.
    
    Args:
        voyage_data (dict): Dados da viagem para salvar
        data_source (str): Fonte dos dados ('API' ou 'MANUAL')
    
    Returns:
        bool: True se salvou com sucesso
    """
    conn = get_database_connection()
    try:
        # Prepara dados para inserção
        insert_data = {
            'NAVIO': voyage_data.get('B_VESSEL_NAME'),
            'VIAGEM': voyage_data.get('B_VOYAGE_CODE'),
            'TERMINAL': voyage_data.get('B_TERMINAL'),
            'B_ETA': voyage_data.get('B_ETA'),
            'B_ETD': voyage_data.get('B_ETD'),
            'B_ATA': voyage_data.get('B_ATA'),
            'B_ATD': voyage_data.get('B_ATD'),
            'B_DATA_CHEGADA_DESTINO_ATA': voyage_data.get('B_DATA_CHEGADA_DESTINO_ATA'),
            'B_DATA_SAIDA_DESTINO_ATD': voyage_data.get('B_DATA_SAIDA_DESTINO_ATD'),
            'B_STATUS': voyage_data.get('B_STATUS'),
            'B_CARRIER': voyage_data.get('B_CARRIER'),
            'B_ORIGIN': voyage_data.get('B_ORIGIN'),
            'B_DESTINATION': voyage_data.get('B_DESTINATION'),
            'B_CARGO_TYPE': voyage_data.get('B_CARGO_TYPE'),
            'B_QUANTITY': voyage_data.get('B_QUANTITY'),
            'B_UNIT': voyage_data.get('B_UNIT'),
            'B_DEADLINE': voyage_data.get('B_DEADLINE'),
            'B_COMMENTS': voyage_data.get('B_COMMENTS'),
            'DATA_SOURCE': data_source,
            'CREATED_AT': datetime.now(),
            'UPDATED_AT': datetime.now(),
            'CREATED_BY': 'SYSTEM_SYNC'
        }
        
        # Remove valores None
        insert_data = {k: v for k, v in insert_data.items() if v is not None}
        
        # Monta query de inserção
        columns = list(insert_data.keys())
        values = [f":{col}" for col in columns]
        
        query = text(f"""
            INSERT INTO LogTransp.F_ELLOX_TERMINAL_MONITORINGS 
            ({', '.join(columns)})
            VALUES ({', '.join(values)})
        """)
        
        conn.execute(query, insert_data)
        conn.commit()
        
        logger.info(f"Dados salvos para {voyage_data.get('B_VESSEL_NAME')} - {voyage_data.get('B_VOYAGE_CODE')}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar dados: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


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
        
        # 2. Consulta API Ellox
        try:
            api_data = get_voyage_monitoring_data(vessel, voyage, terminal)
        except Exception as e:
            result['status'] = 'API_ERROR'
            result['error_message'] = f"Erro na API Ellox: {str(e)}"
            logger.error(f"Erro na API para {vessel}-{voyage}: {str(e)}")
            return result
        
        if not api_data:
            result['status'] = 'NO_DATA'
            result['error_message'] = "Nenhum dado retornado pela API"
            logger.warning(f"Nenhum dado da API para {vessel}-{voyage}")
            return result
        
        # 3. Detecta mudanças
        changes_count, fields_changed = detect_changes(current_data, api_data)
        result['changes_detected'] = changes_count
        result['fields_changed'] = fields_changed
        
        if changes_count == 0:
            result['status'] = 'NO_CHANGES'
            logger.info(f"Nenhuma mudança para {vessel}-{voyage}")
        else:
            # 4. Salva dados atualizados
            if save_monitoring_update(api_data, 'API'):
                result['status'] = 'SUCCESS'
                logger.info(f"Sincronização bem-sucedida para {vessel}-{voyage}: {changes_count} mudanças")
            else:
                result['status'] = 'SAVE_ERROR'
                result['error_message'] = "Erro ao salvar dados no banco"
                logger.error(f"Erro ao salvar dados para {vessel}-{voyage}")
        
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
