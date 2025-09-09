"""
Exemplo de uso da API Ellox com autenticação
Arquivo para testes independentes da API
"""

import requests
import json
from datetime import datetime

class ElloxAPITester:
    """Classe para testar a API Ellox com autenticação"""
    
    def __init__(self, base_url="https://apidtz.comexia.digital", email="diego_moura@cargill.com", password="Cargill@25"):
        """
        Inicializa o cliente da API
        
        Args:
            base_url: URL base da API
            email: Email para autenticação
            password: Senha para autenticação
        """
        self.base_url = base_url
        self.email = email
        self.password = password
        self.api_key = None
        self.authenticated = False
        
    def authenticate(self):
        """Autentica na API e obtém o token"""
        print("🔐 **AUTENTICANDO NA API ELLOX**")
        print("-" * 35)
        
        auth_url = f"{self.base_url}/api/auth"
        
        payload = {
            "email": self.email,
            "senha": self.password  # Usar "senha" em vez de "password"
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            print(f"📡 Enviando requisição para: {auth_url}")
            print(f"📧 Email: {self.email}")
            print(f"🔑 Senha: {'*' * len(self.password)}")
            print()
            
            response = requests.post(auth_url, data=json.dumps(payload), headers=headers, timeout=30)
            
            print(f"📊 Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.api_key = data.get("access_token") or data.get("token") or data.get("api_key")
                
                if self.api_key:
                    self.authenticated = True
                    print("✅ **AUTENTICAÇÃO BEM-SUCEDIDA!**")
                    print(f"🔑 Token obtido: {self.api_key[:20]}...")
                    return True
                else:
                    print("❌ **ERRO: Token não encontrado na resposta**")
                    print(f"📋 Resposta: {data}")
                    return False
            else:
                print(f"❌ **ERRO NA AUTENTICAÇÃO: HTTP {response.status_code}**")
                print(f"📋 Resposta: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("⏰ **ERRO: Timeout na requisição**")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ **ERRO NA REQUISIÇÃO: {str(e)}**")
            return False
        except Exception as e:
            print(f"❌ **ERRO INESPERADO: {str(e)}**")
            return False
    
    def test_connection(self):
        """Testa a conexão com a API"""
        if not self.authenticated:
            print("❌ Não autenticado. Execute authenticate() primeiro.")
            return False
        
        print("🔍 **TESTANDO CONEXÃO**")
        print("-" * 25)
        
        try:
            start_time = datetime.now()
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30
            )
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ **CONEXÃO OK!** Tempo: {response_time:.2f}s")
                print(f"📊 Terminais encontrados: {len(data) if isinstance(data, list) else 'N/A'}")
                return True
            else:
                print(f"❌ **ERRO: HTTP {response.status_code}**")
                print(f"📋 Resposta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ **ERRO: {str(e)}**")
            return False
    
    def test_monitoring(self, cnpj_client, vessel_name, terminal_cnpj, voyage):
        """Testa o monitoramento de navios"""
        if not self.authenticated:
            print("❌ Não autenticado. Execute authenticate() primeiro.")
            return False
        
        print("🚢 **TESTANDO MONITORAMENTO**")
        print("-" * 30)
        
        monitoring_url = f"{self.base_url}/api/monitor/navio"
        
        payload = {
            "cnpj": cnpj_client,
            "lista": [
                {
                    "cnpj_terminal": terminal_cnpj,
                    "nome_navio": vessel_name,
                    "viagem_navio": voyage
                }
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"📡 Enviando para: {monitoring_url}")
        print(f"📋 Dados: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        print()
        
        try:
            response = requests.post(monitoring_url, json=payload, headers=headers, timeout=30)
            
            print(f"📊 Status HTTP: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                print("✅ **MONITORAMENTO SOLICITADO COM SUCESSO!**")
                print(f"📋 Resposta: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return True
            else:
                print(f"❌ **ERRO: HTTP {response.status_code}**")
                print(f"📋 Resposta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ **ERRO: {str(e)}**")
            return False
    
    def list_terminals(self):
        """Lista os terminais disponíveis"""
        if not self.authenticated:
            print("❌ Não autenticado. Execute authenticate() primeiro.")
            return []
        
        print("🏢 **LISTANDO TERMINAIS**")
        print("-" * 25)
        
        try:
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30
            )
            
            if response.status_code == 200:
                terminals = response.json()
                print(f"📊 Total de terminais: {len(terminals)}")
                print()
                
                for i, terminal in enumerate(terminals[:10], 1):  # Primeiros 10
                    name = terminal.get('name', 'N/A')
                    cnpj = terminal.get('cnpj', 'N/A')
                    print(f"{i:2d}. 🏢 **{name}**: `{cnpj}`")
                
                if len(terminals) > 10:
                    print(f"... e mais {len(terminals) - 10} terminais")
                
                return terminals
            else:
                print(f"❌ **ERRO: HTTP {response.status_code}**")
                return []
                
        except Exception as e:
            print(f"❌ **ERRO: {str(e)}**")
            return []

def main():
    """Função principal para testar a API"""
    print("🧪 TESTE DA API ELLOX")
    print("=" * 25)
    print()
    
    # Criar instância do cliente
    api = ElloxAPITester()
    
    # 1. Autenticar
    if not api.authenticate():
        print("❌ Falha na autenticação. Encerrando.")
        return
    
    print()
    
    # 2. Testar conexão
    if not api.test_connection():
        print("❌ Falha no teste de conexão. Encerrando.")
        return
    
    print()
    
    # 3. Listar terminais
    terminals = api.list_terminals()
    
    print()
    
    # 4. Testar monitoramento
    print("🚀 **TESTE DE MONITORAMENTO**")
    print("-" * 30)
    
    # Dados de teste
    cnpj_client = "60.498.706/0001-57"  # CNPJ que funciona
    vessel_name = "MSC SHAY"
    terminal_cnpj = "04.887.625/0001-78"  # BTP
    voyage = "QI532R"
    
    print(f"📋 **DADOS DO TESTE:**")
    print(f"🏢 CNPJ Cliente: {cnpj_client}")
    print(f"🚢 Navio: {vessel_name}")
    print(f"🏢 Terminal: {terminal_cnpj}")
    print(f"🚢 Voyage: {voyage}")
    print()
    
    success = api.test_monitoring(cnpj_client, vessel_name, terminal_cnpj, voyage)
    
    print()
    if success:
        print("🎉 **TESTE COMPLETO - SUCESSO!**")
    else:
        print("❌ **TESTE COMPLETO - FALHOU**")

if __name__ == "__main__":
    main()
