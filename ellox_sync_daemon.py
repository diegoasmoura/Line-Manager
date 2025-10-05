"""
Daemon de Sincronização Automática Ellox API
Script independente que roda 24/7 para sincronizar dados de viagens
"""

import time
import signal
import sys
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from ellox_sync_service import sync_all_active_voyages
from ellox_sync_functions import get_sync_config, update_sync_config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ellox_sync_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Variáveis globais
scheduler = None
running = True


def signal_handler(signum, frame):
    """Handler para sinais de interrupção (Ctrl+C, SIGTERM)"""
    global running
    logger.info(f"Recebido sinal {signum}. Parando daemon...")
    running = False
    if scheduler:
        scheduler.shutdown()
    sys.exit(0)


def job_listener(event):
    """Listener para eventos do scheduler"""
    if event.exception:
        logger.error(f"Erro na execução do job: {event.exception}")
    else:
        logger.info(f"Job executado com sucesso: {event.job_id}")


def sync_job():
    """Job principal de sincronização"""
    try:
        logger.info("=== EXECUTANDO JOB DE SINCRONIZAÇÃO ===")
        
        # Verifica se a sincronização está habilitada
        config = get_sync_config()
        if not config['enabled']:
            logger.info("Sincronização desabilitada. Pulando execução.")
            return
        
        # Executa sincronização
        result = sync_all_active_voyages()
        
        # Atualiza timestamp da última execução
        next_execution = datetime.now() + timedelta(minutes=config['interval_minutes'])
        update_sync_config(
            enabled=config['enabled'],
            interval_minutes=config['interval_minutes'],
            updated_by="DAEMON"
        )
        
        logger.info(f"Job concluído. Próxima execução: {next_execution}")
        
    except Exception as e:
        logger.error(f"Erro no job de sincronização: {str(e)}")


def retry_job(vessel, voyage, terminal, attempt=1):
    """Job de retry para viagens que falharam"""
    try:
        logger.info(f"Executando retry {attempt} para {vessel}-{voyage}-{terminal}")
        
        from ellox_sync_service import sync_single_voyage
        result = sync_single_voyage(vessel, voyage, terminal)
        
        if result['status'] in ['SUCCESS', 'NO_CHANGES']:
            logger.info(f"Retry {attempt} bem-sucedido para {vessel}-{voyage}")
        else:
            logger.warning(f"Retry {attempt} falhou para {vessel}-{voyage}: {result['status']}")
            
    except Exception as e:
        logger.error(f"Erro no retry {attempt} para {vessel}-{voyage}: {str(e)}")


def schedule_retries(failed_voyages, max_retries=3):
    """Agenda retries para viagens que falharam"""
    config = get_sync_config()
    retry_intervals = [5, 10, 15]  # minutos
    
    for i, voyage in enumerate(failed_voyages):
        if i < max_retries:
            retry_time = datetime.now() + timedelta(minutes=retry_intervals[i])
            scheduler.add_job(
                retry_job,
                'date',
                run_date=retry_time,
                args=[voyage['vessel'], voyage['voyage'], voyage['terminal'], i+1],
                id=f"retry_{voyage['vessel']}_{voyage['voyage']}_{i+1}",
                replace_existing=True
            )
            logger.info(f"Retry {i+1} agendado para {voyage['vessel']}-{voyage['voyage']} em {retry_time}")


def start_daemon():
    """Inicia o daemon de sincronização"""
    global scheduler, running
    
    logger.info("=== INICIANDO DAEMON DE SINCRONIZAÇÃO ELLOX ===")
    
    # Configurar handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Criar scheduler
        scheduler = BlockingScheduler()
        
        # Adicionar listener para eventos
        scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # Buscar configuração inicial
        config = get_sync_config()
        interval_minutes = config.get('interval_minutes', 60)
        
        logger.info(f"Configuração carregada: enabled={config['enabled']}, interval={interval_minutes}min")
        
        if config['enabled']:
            # Agendar job principal
            scheduler.add_job(
                sync_job,
                IntervalTrigger(minutes=interval_minutes),
                id='main_sync_job',
                name='Sincronização Principal Ellox',
                replace_existing=True
            )
            
            # Executar imediatamente se nunca foi executado
            if not config.get('last_execution'):
                logger.info("Executando sincronização inicial...")
                sync_job()
            
            logger.info(f"Daemon iniciado. Intervalo: {interval_minutes} minutos")
            logger.info("Pressione Ctrl+C para parar")
            
            # Loop principal
            while running:
                try:
                    scheduler.start()
                except KeyboardInterrupt:
                    break
        else:
            logger.info("Sincronização desabilitada. Daemon em modo de monitoramento.")
            logger.info("Pressione Ctrl+C para parar")
            
            # Loop de monitoramento (verifica configuração a cada minuto)
            while running:
                time.sleep(60)
                config = get_sync_config()
                if config['enabled']:
                    logger.info("Sincronização habilitada. Reiniciando daemon...")
                    break
    
    except Exception as e:
        logger.error(f"Erro fatal no daemon: {str(e)}")
        sys.exit(1)
    
    finally:
        if scheduler:
            scheduler.shutdown()
        logger.info("Daemon finalizado.")


def check_daemon_status():
    """Verifica status do daemon (para uso externo)"""
    try:
        config = get_sync_config()
        return {
            'enabled': config['enabled'],
            'interval_minutes': config['interval_minutes'],
            'last_execution': config['last_execution'],
            'next_execution': config['next_execution'],
            'daemon_running': running
        }
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        return None


def main():
    """Função principal"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'status':
            status = check_daemon_status()
            if status:
                print(f"Status do Daemon:")
                print(f"  Habilitado: {status['enabled']}")
                print(f"  Intervalo: {status['interval_minutes']} minutos")
                print(f"  Última execução: {status['last_execution']}")
                print(f"  Próxima execução: {status['next_execution']}")
                print(f"  Daemon rodando: {status['daemon_running']}")
            else:
                print("Erro ao verificar status")
        
        elif command == 'sync-now':
            print("Executando sincronização manual...")
            result = sync_all_active_voyages()
            print(f"Resultado: {result}")
        
        elif command == 'test':
            print("Testando conexão com banco e API...")
            try:
                config = get_sync_config()
                print(f"✓ Configuração carregada: {config}")
                
                from ellox_sync_functions import get_active_voyages_for_sync
                voyages = get_active_voyages_for_sync()
                print(f"✓ Viagens ativas encontradas: {len(voyages)}")
                
                print("✓ Teste concluído com sucesso")
            except Exception as e:
                print(f"✗ Erro no teste: {str(e)}")
        
        else:
            print("Comandos disponíveis:")
            print("  python ellox_sync_daemon.py          - Iniciar daemon")
            print("  python ellox_sync_daemon.py status   - Verificar status")
            print("  python ellox_sync_daemon.py sync-now - Executar sincronização manual")
            print("  python ellox_sync_daemon.py test     - Testar conexões")
    else:
        # Iniciar daemon
        start_daemon()


if __name__ == "__main__":
    main()
