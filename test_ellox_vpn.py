#!/usr/bin/env python3
"""
Teste Simples de Conectividade API Ellox com VPN
Script focado para diagnosticar problemas de VPN corporativa
"""

import requests
import time
import json
from datetime import datetime

def test_ellox_api_simple():
    """Teste simples e direto da API Ellox"""
    print("🔍 TESTE SIMPLES API ELLOX")
    print("=" * 40)
    
    # URL da API
    api_url = "https://apidtz.comexia.digital/api/auth"
    
    # Credenciais (CONFIGURE AQUI)
    credentials = {
        "email": "seu_email@exemplo.com",  # SUBSTITUA
        "senha": "sua_senha"              # SUBSTITUA
    }
    
    print("⚠️  CONFIGURE SUAS CREDENCIAIS:")
    print("   Edite as linhas 15-16 com seu email e senha da API Ellox")
    print()
    
    # Verificar se credenciais foram configuradas
    if credentials["email"] == "seu_email@exemplo.com":
        print("❌ Credenciais não configuradas!")
        print("   Edite o arquivo e configure seu email e senha")
        return False
    
    # Teste 1: Conectividade básica
    print("🔄 Teste 1: Conectividade básica...")
    try:
        start_time = time.time()
        response = requests.get(api_url, timeout=10, verify=False)
        end_time = time.time()
        
        response_time = round((end_time - start_time) * 1000, 2)
        print(f"✅ Conectou em {response_time}ms - Status: {response.status_code}")
        
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT - A API não respondeu em 10 segundos")
        print("   Possível causa: VPN bloqueando ou API lenta")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 ERRO DE CONEXÃO - {e}")
        print("   Possível causa: VPN não permite acesso à API")
        return False
        
    except Exception as e:
        print(f"❌ ERRO INESPERADO - {e}")
        return False
    
    # Teste 2: Autenticação
    print("\n🔄 Teste 2: Autenticação...")
    try:
        headers = {"Content-Type": "application/json"}
        
        start_time = time.time()
        response = requests.post(
            api_url,
            json=credentials,
            headers=headers,
            timeout=15,
            verify=False
        )
        end_time = time.time()
        
        response_time = round((end_time - start_time) * 1000, 2)
        print(f"✅ Resposta em {response_time}ms - Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ AUTENTICAÇÃO BEM-SUCEDIDA!")
                print(f"   Token: {data.get('access_token', 'N/A')[:30]}...")
                return True
            except:
                print("⚠️  Resposta não é JSON válido")
                print(f"   Conteúdo: {response.text[:100]}")
        else:
            print(f"❌ FALHA NA AUTENTICAÇÃO - Status: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT na autenticação")
        return False
    except Exception as e:
        print(f"❌ ERRO na autenticação: {e}")
        return False
    
    return False

def test_different_timeouts():
    """Testa diferentes timeouts para identificar o problema"""
    print("\n🔄 TESTE DE DIFERENTES TIMEOUTS")
    print("=" * 40)
    
    api_url = "https://apidtz.comexia.digital/api/auth"
    timeouts = [5, 10, 20, 30, 60]
    
    for timeout in timeouts:
        print(f"🔄 Testando timeout de {timeout}s...")
        try:
            start_time = time.time()
            response = requests.get(api_url, timeout=timeout, verify=False)
            end_time = time.time()
            
            response_time = round((end_time - start_time) * 1000, 2)
            print(f"   ✅ Sucesso em {response_time}ms")
            break
            
        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout após {timeout}s")
            continue
        except Exception as e:
            print(f"   ❌ Erro: {str(e)[:50]}")
            break

def test_with_proxy():
    """Testa com configurações de proxy"""
    print("\n🔄 TESTE COM PROXY")
    print("=" * 40)
    
    # Configurações de proxy comuns
    proxy_configs = [
        None,  # Sem proxy
        {"http": "http://proxy:8080", "https": "https://proxy:8080"},  # Proxy HTTP
        {"http": "http://proxy:3128", "https": "https://proxy:3128"},  # Proxy alternativo
    ]
    
    api_url = "https://apidtz.comexia.digital/api/auth"
    
    for i, proxies in enumerate(proxy_configs):
        config_name = "Sem proxy" if proxies is None else f"Proxy {i}"
        print(f"🔄 Testando {config_name}...")
        
        try:
            response = requests.get(api_url, timeout=10, verify=False, proxies=proxies)
            print(f"   ✅ {config_name}: Funcionou! Status: {response.status_code}")
            break
        except Exception as e:
            print(f"   ❌ {config_name}: {str(e)[:50]}")

def main():
    """Função principal"""
    print("🔍 DIAGNÓSTICO VPN vs API ELLOX")
    print("=" * 50)
    print("Data/Hora:", datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    print()
    
    # Executar testes
    success = test_ellox_api_simple()
    
    if not success:
        print("\n🔧 EXECUTANDO TESTES ADICIONAIS...")
        test_different_timeouts()
        test_with_proxy()
    
    print("\n" + "=" * 50)
    print("📊 RESULTADO DO DIAGNÓSTICO:")
    
    if success:
        print("✅ A API Ellox está funcionando!")
        print("   O problema pode estar na configuração da aplicação principal")
        print("   Verifique as credenciais no arquivo de configuração")
    else:
        print("❌ A API Ellox não está acessível")
        print("   Possíveis causas:")
        print("   • VPN bloqueando acesso à API")
        print("   • Firewall corporativo")
        print("   • Proxy necessário")
        print("   • DNS corporativo")
        print()
        print("💡 SOLUÇÕES:")
        print("1. Verifique se a VPN permite acesso à API")
        print("2. Entre em contato com o TI da empresa")
        print("3. Tente desligar a VPN temporariamente")
        print("4. Configure proxy se necessário")
    
    print("\n✅ Teste concluído!")

if __name__ == "__main__":
    main()
