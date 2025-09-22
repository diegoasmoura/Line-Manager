#!/usr/bin/env python3
"""
Teste de Conectividade VPN vs API Ellox
Diagnóstico completo para problemas de rede corporativa
"""

import requests
import time
import socket
import ssl
from datetime import datetime
import json

def test_basic_connectivity():
    """Testa conectividade básica de rede"""
    print("🌐 TESTE DE CONECTIVIDADE BÁSICA")
    print("=" * 50)
    
    # Teste 1: DNS Resolution
    print("🔄 Testando resolução DNS...")
    try:
        ip = socket.gethostbyname('apidtz.comexia.digital')
        print(f"✅ DNS resolvido: apidtz.comexia.digital → {ip}")
        dns_ok = True
    except socket.gaierror as e:
        print(f"❌ DNS falhou: {e}")
        dns_ok = False
    
    # Teste 2: Ping básico (simulado)
    print("🔄 Testando conectividade TCP...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('apidtz.comexia.digital', 443))
        sock.close()
        
        if result == 0:
            print("✅ Porta 443 (HTTPS) acessível")
            tcp_ok = True
        else:
            print(f"❌ Porta 443 inacessível (código: {result})")
            tcp_ok = False
    except Exception as e:
        print(f"❌ Teste TCP falhou: {e}")
        tcp_ok = False
    
    return dns_ok, tcp_ok

def test_ssl_handshake():
    """Testa handshake SSL/TLS"""
    print("\n🔐 TESTE DE SSL/TLS")
    print("=" * 50)
    
    try:
        # Criar contexto SSL
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Conectar via SSL
        with socket.create_connection(('apidtz.comexia.digital', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='apidtz.comexia.digital') as ssock:
                print("✅ Handshake SSL/TLS bem-sucedido")
                print(f"   Protocolo: {ssock.version()}")
                print(f"   Cipher: {ssock.cipher()}")
                ssl_ok = True
    except Exception as e:
        print(f"❌ Handshake SSL falhou: {e}")
        ssl_ok = False
    
    return ssl_ok

def test_http_requests():
    """Testa requisições HTTP com diferentes configurações"""
    print("\n🌐 TESTE DE REQUISIÇÕES HTTP")
    print("=" * 50)
    
    base_url = "https://apidtz.comexia.digital"
    
    # Configurações de teste
    configs = [
        {
            "name": "Configuração Padrão",
            "timeout": 30,
            "verify": True,
            "proxies": None
        },
        {
            "name": "Sem Verificação SSL",
            "timeout": 30,
            "verify": False,
            "proxies": None
        },
        {
            "name": "Timeout Reduzido",
            "timeout": 10,
            "verify": True,
            "proxies": None
        },
        {
            "name": "Timeout Muito Reduzido",
            "timeout": 5,
            "verify": True,
            "proxies": None
        }
    ]
    
    results = []
    
    for config in configs:
        print(f"\n🔄 {config['name']}...")
        try:
            # Teste de conectividade básica
            start_time = time.time()
            response = requests.get(
                f"{base_url}/api/auth",
                timeout=config['timeout'],
                verify=config['verify'],
                proxies=config['proxies']
            )
            end_time = time.time()
            
            response_time = round((end_time - start_time) * 1000, 2)
            
            print(f"✅ Conectou em {response_time}ms")
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(list(response.headers.items())[:3])}")
            
            results.append({
                "config": config['name'],
                "success": True,
                "time": response_time,
                "status": response.status_code
            })
            
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout após {config['timeout']}s")
            results.append({
                "config": config['name'],
                "success": False,
                "error": "Timeout"
            })
            
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 Erro de conexão: {e}")
            results.append({
                "config": config['name'],
                "success": False,
                "error": f"ConnectionError: {str(e)[:100]}"
            })
            
        except requests.exceptions.SSLError as e:
            print(f"🔐 Erro SSL: {e}")
            results.append({
                "config": config['name'],
                "success": False,
                "error": f"SSLError: {str(e)[:100]}"
            })
            
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            results.append({
                "config": config['name'],
                "success": False,
                "error": f"Unexpected: {str(e)[:100]}"
            })
    
    return results

def test_api_authentication():
    """Testa autenticação na API Ellox"""
    print("\n🔑 TESTE DE AUTENTICAÇÃO API")
    print("=" * 50)
    
    # Credenciais de teste (substitua pelas suas)
    test_credentials = {
        "email": "seu_email@exemplo.com",  # SUBSTITUA AQUI
        "senha": "sua_senha"              # SUBSTITUA AQUI
    }
    
    print("⚠️  IMPORTANTE: Configure suas credenciais no arquivo antes de executar!")
    print("   Edite as linhas 95-96 com seu email e senha da API Ellox")
    
    # Verificar se credenciais foram configuradas
    if test_credentials["email"] == "seu_email@exemplo.com":
        print("❌ Credenciais não configuradas - pulando teste de autenticação")
        return False
    
    try:
        url = "https://apidtz.comexia.digital/api/auth"
        headers = {"Content-Type": "application/json"}
        
        print("🔄 Testando autenticação...")
        start_time = time.time()
        
        response = requests.post(
            url,
            json=test_credentials,
            headers=headers,
            timeout=30,
            verify=False  # Desabilitar verificação SSL para teste
        )
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        print(f"✅ Resposta recebida em {response_time}ms")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ Autenticação bem-sucedida!")
                print(f"   Token recebido: {data.get('access_token', 'N/A')[:20]}...")
                return True
            except json.JSONDecodeError:
                print("⚠️  Resposta não é JSON válido")
                print(f"   Conteúdo: {response.text[:200]}")
                return False
        else:
            print(f"❌ Falha na autenticação (Status: {response.status_code})")
            print(f"   Resposta: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na autenticação: {e}")
        return False

def test_proxy_detection():
    """Detecta configurações de proxy"""
    print("\n🔍 DETECÇÃO DE PROXY")
    print("=" * 50)
    
    # Verificar variáveis de ambiente de proxy
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
    
    proxies_detected = False
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {value}")
            proxies_detected = True
    
    if not proxies_detected:
        print("ℹ️  Nenhuma variável de proxy detectada")
    
    # Testar se requests detecta proxy automaticamente
    try:
        session = requests.Session()
        proxies = session.proxies
        if proxies:
            print(f"✅ Proxies detectados pelo requests: {proxies}")
        else:
            print("ℹ️  Nenhum proxy detectado pelo requests")
    except Exception as e:
        print(f"⚠️  Erro ao detectar proxies: {e}")
    
    return proxies_detected

def test_network_route():
    """Testa rota de rede (simulado)"""
    print("\n🛣️  ANÁLISE DE ROTA")
    print("=" * 50)
    
    try:
        # Teste de conectividade com diferentes timeouts
        timeouts = [1, 3, 5, 10, 30]
        
        for timeout in timeouts:
            try:
                start_time = time.time()
                response = requests.get(
                    "https://apidtz.comexia.digital/api/auth",
                    timeout=timeout,
                    verify=False
                )
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)
                
                print(f"✅ Timeout {timeout}s: Conectou em {response_time}ms")
                break
                
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout {timeout}s: Falhou")
                continue
            except Exception as e:
                print(f"❌ Timeout {timeout}s: {str(e)[:50]}")
                break
                
    except Exception as e:
        print(f"❌ Erro no teste de rota: {e}")

def generate_report(results):
    """Gera relatório final"""
    print("\n📊 RELATÓRIO FINAL")
    print("=" * 60)
    
    print("🎯 DIAGNÓSTICO VPN vs API ELLOX")
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # Análise de resultados
    successful_configs = [r for r in results if r.get('success', False)]
    failed_configs = [r for r in results if not r.get('success', False)]
    
    print(f"✅ Configurações bem-sucedidas: {len(successful_configs)}")
    print(f"❌ Configurações com falha: {len(failed_configs)}")
    
    if successful_configs:
        print("\n🏆 CONFIGURAÇÕES QUE FUNCIONARAM:")
        for result in successful_configs:
            print(f"   • {result['config']}: {result['time']}ms")
    
    if failed_configs:
        print("\n💥 CONFIGURAÇÕES QUE FALHARAM:")
        for result in failed_configs:
            print(f"   • {result['config']}: {result.get('error', 'Erro desconhecido')}")
    
    # Recomendações
    print("\n💡 RECOMENDAÇÕES:")
    
    if len(successful_configs) > 0:
        print("✅ A API Ellox está acessível - problema pode ser específico da aplicação")
        print("🔧 Tente usar a configuração que funcionou no seu código")
    else:
        print("❌ A API Ellox não está acessível - problema de rede/VPN")
        print("🔧 Verifique:")
        print("   • Configurações de VPN")
        print("   • Firewall corporativo")
        print("   • Proxy settings")
        print("   • DNS corporativo")
    
    print("\n🛠️  PRÓXIMOS PASSOS:")
    print("1. Se algum teste passou, use essa configuração no seu código")
    print("2. Se todos falharam, verifique configurações de rede/VPN")
    print("3. Entre em contato com o TI da empresa sobre acesso à API")
    print("4. Considere usar proxy corporativo se necessário")

def main():
    """Função principal"""
    print("🔍 DIAGNÓSTICO DE CONECTIVIDADE VPN vs API ELLOX")
    print("=" * 60)
    print("Este script testa diferentes configurações de rede para identificar")
    print("problemas de conectividade com a API Ellox em ambientes corporativos.")
    print()
    
    # Importar os aqui para evitar erro se não estiver disponível
    import os
    
    # Executar todos os testes
    dns_ok, tcp_ok = test_basic_connectivity()
    ssl_ok = test_ssl_handshake()
    http_results = test_http_requests()
    auth_ok = test_api_authentication()
    proxy_detected = test_proxy_detection()
    test_network_route()
    
    # Gerar relatório
    generate_report(http_results)
    
    print("\n" + "=" * 60)
    print("✅ Teste concluído! Verifique o relatório acima.")
    print("📁 Salve este arquivo para referência futura.")

if __name__ == "__main__":
    main()
