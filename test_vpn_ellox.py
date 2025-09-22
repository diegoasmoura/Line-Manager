#!/usr/bin/env python3
"""
Teste Específico: VPN vs API Ellox
Diagnóstico focado no problema de conectividade com VPN corporativa
"""

import requests
import time
import socket
from datetime import datetime

def test_dns_resolution():
    """Testa se consegue resolver o DNS da API"""
    print("🌐 TESTE DE DNS")
    print("-" * 20)
    
    try:
        ip = socket.gethostbyname('apidtz.comexia.digital')
        print(f"✅ DNS OK: apidtz.comexia.digital → {ip}")
        return True
    except socket.gaierror as e:
        print(f"❌ DNS FALHOU: {e}")
        print("💡 Possível causa: VPN bloqueando resolução DNS")
        return False

def test_port_connectivity():
    """Testa se consegue conectar na porta 443"""
    print("\n🔌 TESTE DE PORTA 443")
    print("-" * 20)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('apidtz.comexia.digital', 443))
        sock.close()
        
        if result == 0:
            print("✅ Porta 443 acessível")
            return True
        else:
            print(f"❌ Porta 443 inacessível (código: {result})")
            print("💡 Possível causa: Firewall/VPN bloqueando")
            return False
    except Exception as e:
        print(f"❌ Erro no teste de porta: {e}")
        return False

def test_https_request():
    """Testa requisição HTTPS básica"""
    print("\n🌐 TESTE DE REQUISIÇÃO HTTPS")
    print("-" * 20)
    
    try:
        start = time.time()
        response = requests.get(
            "https://apidtz.comexia.digital/api/auth",
            timeout=15,
            verify=False  # Desabilitar verificação SSL para teste
        )
        end = time.time()
        
        tempo = round((end - start) * 1000, 2)
        print(f"✅ Conectou em {tempo}ms - Status: {response.status_code}")
        return True
        
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT - API não respondeu em 15s")
        print("💡 Possível causa: VPN muito lenta ou bloqueando")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 ERRO DE CONEXÃO: {e}")
        print("💡 Possível causa: VPN não permite acesso à API")
        return False
        
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {e}")
        return False

def test_api_authentication():
    """Testa autenticação na API"""
    print("\n🔑 TESTE DE AUTENTICAÇÃO")
    print("-" * 20)
    
    # CONFIGURE SUAS CREDENCIAIS AQUI
    credentials = {
        "email": "seu_email@exemplo.com",  # SUBSTITUA
        "senha": "sua_senha"              # SUBSTITUA
    }
    
    if credentials["email"] == "seu_email@exemplo.com":
        print("⚠️  CONFIGURE SUAS CREDENCIAIS NAS LINHAS 60-61!")
        print("   Edite o arquivo e coloque seu email e senha da API Ellox")
        return False
    
    try:
        start = time.time()
        response = requests.post(
            "https://apidtz.comexia.digital/api/auth",
            json=credentials,
            headers={"Content-Type": "application/json"},
            timeout=20,
            verify=False
        )
        end = time.time()
        
        tempo = round((end - start) * 1000, 2)
        print(f"✅ Resposta em {tempo}ms - Status: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 AUTENTICAÇÃO BEM-SUCEDIDA!")
            try:
                data = response.json()
                print(f"🔑 Token recebido: {data.get('access_token', 'N/A')[:30]}...")
                return True
            except:
                print("⚠️  Resposta não é JSON válido")
                print(f"📝 Conteúdo: {response.text[:100]}")
        else:
            print(f"❌ FALHA NA AUTENTICAÇÃO - Status: {response.status_code}")
            print(f"📝 Resposta: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT na autenticação")
        return False
    except Exception as e:
        print(f"❌ Erro na autenticação: {e}")
        return False
    
    return False

def test_different_timeouts():
    """Testa diferentes timeouts para identificar o problema"""
    print("\n⏰ TESTE DE DIFERENTES TIMEOUTS")
    print("-" * 20)
    
    timeouts = [5, 10, 20, 30]
    
    for timeout in timeouts:
        print(f"🔄 Testando timeout de {timeout}s...")
        try:
            start = time.time()
            response = requests.get(
                "https://apidtz.comexia.digital/api/auth",
                timeout=timeout,
                verify=False
            )
            end = time.time()
            
            tempo = round((end - start) * 1000, 2)
            print(f"   ✅ Sucesso em {tempo}ms")
            return True
        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout após {timeout}s")
            continue
        except Exception as e:
            print(f"   ❌ Erro: {str(e)[:50]}")
            break
    
    return False

def main():
    """Função principal"""
    print("🔍 DIAGNÓSTICO VPN vs API ELLOX")
    print("=" * 50)
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # Executar testes sequenciais
    dns_ok = test_dns_resolution()
    port_ok = test_port_connectivity()
    https_ok = test_https_request()
    auth_ok = test_api_authentication()
    
    # Se falhou, testar timeouts diferentes
    if not auth_ok:
        test_different_timeouts()
    
    # Relatório final
    print("\n" + "=" * 50)
    print("📊 RELATÓRIO FINAL")
    print("=" * 50)
    
    print(f"🌐 DNS Resolution: {'✅ OK' if dns_ok else '❌ FALHOU'}")
    print(f"🔌 Porta 443: {'✅ OK' if port_ok else '❌ FALHOU'}")
    print(f"🌐 HTTPS Request: {'✅ OK' if https_ok else '❌ FALHOU'}")
    print(f"🔑 Autenticação: {'✅ OK' if auth_ok else '❌ FALHOU'}")
    
    print("\n💡 DIAGNÓSTICO:")
    
    if not dns_ok:
        print("❌ PROBLEMA: DNS não resolve")
        print("   Solução: Verificar configurações de DNS da VPN")
        
    elif not port_ok:
        print("❌ PROBLEMA: Porta 443 bloqueada")
        print("   Solução: Verificar firewall/VPN permite HTTPS")
        
    elif not https_ok:
        print("❌ PROBLEMA: Requisição HTTPS falha")
        print("   Solução: Verificar proxy/VPN permite API Ellox")
        
    elif not auth_ok:
        print("❌ PROBLEMA: Autenticação falha")
        print("   Solução: Verificar credenciais ou API indisponível")
        
    else:
        print("✅ TUDO FUNCIONANDO!")
        print("   A API Ellox está acessível com VPN")
        print("   O problema pode estar na aplicação principal")
    
    print("\n🛠️  PRÓXIMOS PASSOS:")
    if auth_ok:
        print("1. ✅ API funcionando - verifique configuração da aplicação")
        print("2. 🔧 Teste a aplicação principal")
    else:
        print("1. 🔧 Verifique configurações de VPN")
        print("2. 📞 Entre em contato com TI da empresa")
        print("3. 🔄 Tente desligar VPN temporariamente")
        print("4. 🌐 Configure proxy se necessário")
    
    print("\n✅ Teste concluído!")

if __name__ == "__main__":
    main()
