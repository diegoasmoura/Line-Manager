#!/usr/bin/env python3
"""
Teste da API Ellox com endpoint de voyages correto
=================================================
"""

import requests
import time
from ellox_api import get_default_api_client
from urllib.parse import quote

def test_voyages_endpoint():
    """Testa o endpoint de voyages da API Ellox"""
    
    print("🔍 TESTANDO API ELLOX - ENDPOINT DE VOYAGES")
    print("=" * 50)
    
    try:
        client = get_default_api_client()
        
        if not client.authenticated:
            print("❌ Cliente não autenticado")
            return
        
        print(f"✅ Cliente autenticado")
        print(f"🌐 Base URL: {client.base_url}")
        print()
        
        # Casos de teste
        test_cases = [
            {
                "name": "COSCO SHIPPING DANUBE",
                "terminal_cnpj": "02.762.121/0001-04",  # Santos Brasil
                "terminal_name": "Santos Brasil",
                "expected_voyage": "044E"
            },
            {
                "name": "MSC ALBANY",
                "terminal_cnpj": "04.887.625/0001-78",  # BTP
                "terminal_name": "BTP",
                "expected_voyage": "MM223A"
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"🚢 TESTE {i}: {case['name']}")
            print("-" * 30)
            
            try:
                # Primeiro verificar se o navio existe no terminal
                ships_url = f"{client.base_url}/api/ships?terminal={case['terminal_cnpj']}"
                print(f"1. Verificando navio no terminal {case['terminal_name']}...")
                
                ships_response = requests.get(ships_url, headers=client.headers, timeout=30)
                
                if ships_response.status_code == 200:
                    ships = ships_response.json()
                    ship_found = None
                    
                    for ship in ships:
                        if isinstance(ship, str) and case['name'].upper() in ship.upper():
                            ship_found = ship
                            break
                    
                    if ship_found:
                        print(f"   ✅ Navio encontrado: {ship_found}")
                        
                        # Testar voyages
                        encoded_ship = quote(ship_found)
                        voyages_url = f"{client.base_url}/api/voyages?ship={encoded_ship}&terminal={case['terminal_cnpj']}"
                        
                        print(f"2. Buscando voyages...")
                        print(f"   URL: {voyages_url}")
                        
                        # Tentar com timeout maior e retry
                        for attempt in range(3):
                            try:
                                print(f"   Tentativa {attempt + 1}/3...")
                                voyages_response = requests.get(
                                    voyages_url, 
                                    headers=client.headers, 
                                    timeout=45
                                )
                                
                                if voyages_response.status_code == 200:
                                    voyages = voyages_response.json()
                                    print(f"   ✅ {len(voyages)} voyages encontradas!")
                                    print(f"   Voyages: {voyages[:10]}...")  # Primeiras 10
                                    
                                    # Verificar voyage específica
                                    if case['expected_voyage'] in voyages:
                                        print(f"   🎯 Voyage {case['expected_voyage']} CONFIRMADA!")
                                    else:
                                        print(f"   ⚠️ Voyage {case['expected_voyage']} não encontrada")
                                        print(f"   Voyages disponíveis: {voyages}")
                                    
                                    break
                                    
                                elif voyages_response.status_code == 404:
                                    print(f"   ❌ Endpoint não encontrado (404)")
                                    break
                                else:
                                    print(f"   ⚠️ Status {voyages_response.status_code}: {voyages_response.text[:100]}")
                                    
                            except requests.exceptions.Timeout:
                                print(f"   ⏱️ Timeout na tentativa {attempt + 1}")
                                if attempt < 2:
                                    time.sleep(2)
                                else:
                                    print(f"   ❌ Timeout após 3 tentativas")
                            except Exception as e:
                                print(f"   💥 Erro: {e}")
                                break
                    else:
                        print(f"   ❌ Navio não encontrado no terminal")
                        
                else:
                    print(f"   ❌ Erro ao buscar navios: {ships_response.status_code}")
                    
            except Exception as e:
                print(f"💥 Erro no teste: {e}")
            
            print()
        
        print("🎯 TESTANDO IMPLEMENTAÇÃO COMPLETA...")
        print("-" * 40)
        
        # Testar a função completa
        result = client.search_voyage_tracking(
            vessel_name="COSCO SHIPPING DANUBE",
            carrier="COSCO", 
            voyage="044E",
            port_terminal="Santos Brasil"
        )
        
        print(f"Resultado: {result.get('success')}")
        if result.get('success'):
            data = result.get('data', {})
            print(f"✅ SUCESSO!")
            print(f"🚢 Navio: {data.get('vessel_name')}")
            print(f"🚢 Voyage: {data.get('voyage')}")
            print(f"🏢 Terminal: {data.get('terminal')}")
            print(f"✅ Voyage confirmada: {data.get('voyage_confirmed')}")
            print(f"🚢 Voyages disponíveis: {data.get('available_voyages', [])}")
        else:
            print(f"❌ Erro: {result.get('error')}")
            if result.get('data'):
                data = result.get('data', {})
                print(f"🚢 Voyages disponíveis: {data.get('available_voyages', [])}")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_voyages_endpoint()
