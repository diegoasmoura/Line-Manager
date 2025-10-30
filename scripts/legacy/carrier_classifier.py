#!/usr/bin/env python3
"""
Classificador de Carriers para Navios
====================================

Este script melhora a classificação de carriers para navios que estão marcados como "OUTROS"
no banco de dados, usando padrões conhecidos de nomenclatura de navios.
"""

import logging
from database import get_database_connection
from sqlalchemy import text
import pandas as pd

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CarrierClassifier:
    """Classificador inteligente de carriers baseado em padrões de nomes de navios"""
    
    def __init__(self):
        """Inicializar padrões de classificação"""
        self.patterns = {
            'MSC': [
                'MSC ', 'MSC_', 'MEDITERRANEAN SHIPPING',
                'MSC ANNA', 'MSC MARIA', 'MSC SANDRA', 'MSC OSCAR',
                'MSC ELENA', 'MSC LUCIA', 'MSC PALOMA'
            ],
            'MAERSK': [
                'MAERSK', 'MÆRSK', 'MAERSK LINE',
                'EMMA MAERSK', 'EVELYN MAERSK', 'ESTELLE MAERSK'
            ],
            'CMA CGM': [
                'CMA CGM', 'CMA', 'CGM ',
                'ANTOINE DE SAINT EXUPERY', 'BENJAMIN FRANKLIN',
                'JULES VERNE', 'MARCO POLO', 'VASCO DE GAMA',
                'SWANSEA'  # Baseado no exemplo do usuário
            ],
            'COSCO': [
                'COSCO', 'CHINA SHIPPING', 'CSCL',
                'COSCO SHIPPING', 'COSCO PACIFIC', 'COSCO PRIDE'
            ],
            'EVERGREEN': [
                'EVERGREEN', 'EVER ', 'EMC',
                'EVER GIVEN', 'EVER GOLDEN', 'EVER GLOBE'
            ],
            'HAPAG-LLOYD': [
                'HAPAG', 'HAPAG-LLOYD', 'HL ',
                'HAMBURG SUD', 'BERLIN EXPRESS', 'HAMBURG EXPRESS'
            ],
            'OOCL': [
                'OOCL', 'ORIENT OVERSEAS',
                'KOTA ', 'OOCL HONG KONG', 'OOCL SHANGHAI'
            ]
        }
    
    def classify_vessel(self, vessel_name: str) -> str:
        """
        Classificar um navio baseado em seu nome
        
        Args:
            vessel_name: Nome do navio
            
        Returns:
            Carrier classificado ou 'OUTROS' se não identificado
        """
        vessel_upper = vessel_name.upper().strip()
        
        for carrier, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.upper() in vessel_upper:
                    logger.info(f"Navio '{vessel_name}' classificado como '{carrier}' (padrão: '{pattern}')")
                    return carrier
        
        return 'OUTROS'
    
    def get_outros_vessels(self):
        """Buscar navios classificados como 'OUTROS' no banco"""
        try:
            conn = get_database_connection()
            query = """
                SELECT DISTINCT NOME 
                FROM LogTransp.F_ELLOX_SHIPS 
                WHERE UPPER(CARRIER) = 'OUTROS' 
                ORDER BY NOME
            """
            
            result = conn.execute(text(query))
            vessels = [row[0] for row in result.fetchall()]
            
            logger.info(f"Encontrados {len(vessels)} navios classificados como 'OUTROS'")
            return vessels
            
        except Exception as e:
            logger.error(f"Erro ao buscar navios 'OUTROS': {e}")
            return []
    
    def update_vessel_carrier(self, vessel_name: str, new_carrier: str):
        """Atualizar carrier de um navio no banco"""
        try:
            conn = get_database_connection()
            query = """
                UPDATE LogTransp.F_ELLOX_SHIPS 
                SET CARRIER = :new_carrier 
                WHERE UPPER(NOME) = UPPER(:vessel_name)
            """
            
            result = conn.execute(
                text(query), 
                {"new_carrier": new_carrier, "vessel_name": vessel_name}
            )
            conn.commit()
            
            if result.rowcount > 0:
                logger.info(f"✅ Navio '{vessel_name}' atualizado para carrier '{new_carrier}' ({result.rowcount} registros)")
                return True
            else:
                logger.warning(f"⚠️ Nenhum registro atualizado para navio '{vessel_name}'")
                return False
                    
        except Exception as e:
            logger.error(f"Erro ao atualizar navio '{vessel_name}': {e}")
            return False
    
    def run_classification(self, dry_run: bool = True):
        """
        Executar classificação completa
        
        Args:
            dry_run: Se True, apenas simula as mudanças sem aplicar
        """
        logger.info(f"🚀 Iniciando classificação de carriers (dry_run={dry_run})")
        
        # Buscar navios 'OUTROS'
        outros_vessels = self.get_outros_vessels()
        
        if not outros_vessels:
            logger.info("Nenhum navio 'OUTROS' encontrado")
            return
        
        # Classificar cada navio
        reclassifications = {}
        
        for vessel in outros_vessels:
            new_carrier = self.classify_vessel(vessel)
            if new_carrier != 'OUTROS':
                reclassifications[vessel] = new_carrier
        
        logger.info(f"📊 Resultado da classificação:")
        logger.info(f"   • Total navios analisados: {len(outros_vessels)}")
        logger.info(f"   • Navios reclassificados: {len(reclassifications)}")
        logger.info(f"   • Permancem como 'OUTROS': {len(outros_vessels) - len(reclassifications)}")
        
        if reclassifications:
            logger.info("📋 Reclassificações propostas:")
            for vessel, carrier in reclassifications.items():
                logger.info(f"   • {vessel} → {carrier}")
        
        # Aplicar mudanças se não for dry_run
        if not dry_run and reclassifications:
            logger.info("💾 Aplicando mudanças no banco...")
            success_count = 0
            
            for vessel, carrier in reclassifications.items():
                if self.update_vessel_carrier(vessel, carrier):
                    success_count += 1
            
            logger.info(f"✅ {success_count}/{len(reclassifications)} navios atualizados com sucesso")
        elif dry_run:
            logger.info("🔍 Modo dry_run ativo - nenhuma mudança aplicada")
    
    def get_classification_stats(self):
        """Obter estatísticas de classificação atual"""
        try:
            conn = get_database_connection()
            query = """
                SELECT CARRIER, COUNT(*) as count
                FROM LogTransp.F_ELLOX_SHIPS 
                GROUP BY CARRIER 
                ORDER BY count DESC
            """
            
            result = conn.execute(text(query))
            stats = {row[0]: row[1] for row in result.fetchall()}
            
            logger.info("📊 Estatísticas atuais de carriers:")
            for carrier, count in stats.items():
                logger.info(f"   • {carrier}: {count} navios")
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {}


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Classificador de Carriers para Navios')
    parser.add_argument('--apply', action='store_true', 
                       help='Aplicar mudanças no banco (padrão: dry_run)')
    parser.add_argument('--stats', action='store_true',
                       help='Mostrar apenas estatísticas atuais')
    
    args = parser.parse_args()
    
    classifier = CarrierClassifier()
    
    if args.stats:
        classifier.get_classification_stats()
    else:
        dry_run = not args.apply
        classifier.run_classification(dry_run=dry_run)


if __name__ == "__main__":
    main()
