#!/usr/bin/env python3
"""
Teste Rápido VPN vs API Ellox
Execute este script para diagnosticar problemas de conectividade
"""

import requests
import time

def quick_test():
    """Teste rápido e direto"""
    print("🔍 TESTE RÁPIDO API ELLOX")
    print("=" * 30)
    
    # CONFIGURE AQUI SUAS CREDENCIAIS
    email = "seu_email@exemplo.com"  # SUBSTITUA
    senha = "sua_senha"              # SUBSTITUA
    
    if email == "seu_email@exemplo.com":
        print("❌ Configure suas credenciais nas linhas 10-11!")
        return
    
    print(f"📧 Email: {email}")
    print("🔄 Testando conectividade...")
    
    try:
        # Teste de conectividade
        start = time.time()
        response = requests.post(
            "https://apidtz.comexia.digital/api/auth",
            json={"email": email, "senha": senha},
            headers={"Content-Type": "application/json"},
            timeout=15,
            verify=False
        )
        end = time.time()
        
        tempo = round((end - start) * 1000, 2)
        
        print(f"✅ Resposta em {tempo}ms")
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 SUCESSO! API funcionando com VPN")
            data = response.json()
            print(f"🔑 Token: {data.get('access_token', 'N/A')[:20]}...")
        else:
            print(f"❌ Falha - Status: {response.status_code}")
            print(f"📝 Resposta: {response.text[:100]}")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT - API não respondeu")
        print("💡 Possível causa: VPN bloqueando")
        
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 ERRO DE CONEXÃO: {e}")
        print("💡 Possível causa: VPN não permite acesso")
        
    except Exception as e:
        print(f"❌ ERRO: {e}")

if __name__ == "__main__":
    quick_test()
    print("\n" + "=" * 30)
    print("✅ Teste concluído!")
