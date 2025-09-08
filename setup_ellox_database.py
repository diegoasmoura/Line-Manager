#!/usr/bin/env python3
"""
Script de Inicialização do Banco de Dados Ellox
Este script configura e popula o banco com dados da API Ellox
"""

import sys
import argparse
from datetime import datetime
from ellox_data_extractor import ElloxDataExtractor

def main():
    """Função principal do script"""
    
    parser = argparse.ArgumentParser(description='Configurar e popular banco de dados Ellox')
    parser.add_argument('--ships-sample', type=int, default=100, 
                       help='Número de navios para amostra de voyages (padrão: 100)')
    parser.add_argument('--skip-voyages', action='store_true',
                       help='Pular extração de voyages (apenas terminais, navios e carriers)')
    parser.add_argument('--force', action='store_true',
                       help='Forçar recriação das tabelas')
    
    args = parser.parse_args()
    
    print("🚀 CONFIGURAÇÃO DO BANCO DE DADOS ELLOX")
    print("=" * 50)
    print(f"📊 Configurações:")
    print(f"  • Amostra de voyages: {args.ships_sample}")
    print(f"  • Pular voyages: {'Sim' if args.skip_voyages else 'Não'}")
    print(f"  • Forçar recriação: {'Sim' if args.force else 'Não'}")
    print()
    
    try:
        # Inicializar extrator
        print("🔄 Inicializando extrator...")
        extractor = ElloxDataExtractor()
        print("✅ Extrator inicializado com sucesso")
        
        start_time = datetime.now()
        
        # Criar tabelas
        if args.force:
            print("🗑️ Removendo tabelas existentes...")
            # Aqui você pode adicionar lógica para dropar tabelas se necessário
        
        print("🏗️ Criando/verificando tabelas...")
        extractor.create_tables()
        
        # Extrair carriers
        print("🏪 Extraindo carriers...")
        carriers = extractor.extract_carriers()
        print(f"✅ {len(carriers)} carriers inseridos")
        
        # Extrair terminais
        print("🏢 Extraindo terminais...")
        terminals = extractor.extract_terminals()
        print(f"✅ {len(terminals)} terminais inseridos")
        
        # Extrair navios
        print("🚢 Extraindo navios...")
        ships = extractor.extract_ships(terminals)
        print(f"✅ {len(ships)} navios inseridos")
        
        # Extrair voyages (se não foi pulado)
        voyages = []
        if not args.skip_voyages:
            print(f"⛵ Extraindo amostra de {args.ships_sample} voyages...")
            voyages = extractor.extract_voyages_sample(args.ships_sample)
            print(f"✅ {len(voyages)} voyages inseridos")
        else:
            print("⏭️ Extração de voyages pulada")
        
        # Resumo final
        end_time = datetime.now()
        duration = end_time - start_time
        
        print()
        print("🎉 CONFIGURAÇÃO CONCLUÍDA!")
        print("=" * 30)
        print(f"📊 Resumo:")
        print(f"  • Carriers: {len(carriers)}")
        print(f"  • Terminais: {len(terminals)}")
        print(f"  • Navios: {len(ships)}")
        print(f"  • Voyages: {len(voyages)}")
        print(f"  • Tempo total: {duration}")
        print()
        print("✅ Banco de dados pronto para uso!")
        print("🔗 Execute 'streamlit run app.py' e vá para a aba 'Tracking > Dados da API'")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
        return False
        
    except Exception as e:
        print(f"\n❌ Erro durante a configuração: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
