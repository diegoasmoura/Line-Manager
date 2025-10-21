"""
Módulo para integração com a API Ellox da Comexia
Fornece funcionalidades de tracking e consulta de informações de viagem

Documentação: https://developers.comexia.digital/
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import streamlit as st
import re
import os
import sys
from app_config import ELLOX_API_CONFIG, PROXY_CONFIG

def detect_environment():
    """
    Detecta automaticamente o ambiente de execução com múltiplas verificações
    Returns: 'development', 'production', ou 'unknown'
    """
    import socket
    import platform
    
    print("[DETECT] Iniciando detecção de ambiente...")
    
    # 1. Verifica variável de ambiente explícita (prioridade máxima)
    env_var = os.environ.get('FAROL_ENVIRONMENT', '').lower()
    if env_var in ['development', 'dev', 'local']:
        print("[DETECT] Ambiente definido explicitamente como DESENVOLVIMENTO")
        return 'development'
    elif env_var in ['production', 'prod', 'corporate', 'empresa']:
        print("[DETECT] Ambiente definido explicitamente como PRODUÇÃO")
        return 'production'
    
    # 2. Verifica se existe pasta certificados/ (indicador forte de ambiente corporativo)
    script_dir = os.path.dirname(__file__)
    cert_dir = os.path.join(script_dir, 'certificados')
    cert_file = os.path.join(cert_dir, 'ca_bundle.pem')
    
    if os.path.isdir(cert_dir) and os.path.isfile(cert_file):
        print(f"[DETECT] Pasta certificados/ encontrada - indicador de ambiente corporativo")
        # Verifica se o certificado é válido (não vazio)
        try:
            if os.path.getsize(cert_file) > 0:
                print(f"[DETECT] Certificado válido encontrado: {cert_file}")
                return 'production'
            else:
                print(f"[DETECT] Certificado vazio - ignorando")
        except:
            print(f"[DETECT] Erro ao verificar certificado - ignorando")
    
    # 3. Verifica se está em rede corporativa (proxy acessível)
    try:
        socket.gethostbyname('web.prod.proxy.cargill.com')
        print("[DETECT] Proxy corporativo acessível - ambiente de produção")
        return 'production'
    except socket.gaierror:
        print("[DETECT] Proxy corporativo não acessível")
    
    # 4. Verifica se está em rede Cargill (outros indicadores)
    try:
        hostname = platform.node().lower()
        if any(indicator in hostname for indicator in ['cargill', 'corp', 'prod', 'empresa']):
            print(f"[DETECT] Hostname indica ambiente corporativo: {hostname}")
            return 'production'
    except:
        print("[DETECT] Erro ao verificar hostname")
    
    # 5. Verifica se há configuração de proxy ativa
    proxy_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']
    active_proxies = [var for var in proxy_vars if var in os.environ]
    if active_proxies:
        print(f"[DETECT] Variáveis de proxy ativas: {active_proxies}")
        return 'production'
    
    # 6. Verifica se está em rede corporativa (outros domínios)
    try:
        # Verifica se consegue resolver domínios corporativos
        corporate_domains = ['cargill.com', 'corp.cargill.com']
        for domain in corporate_domains:
            try:
                socket.gethostbyname(domain)
                print(f"[DETECT] Domínio corporativo acessível: {domain}")
                return 'production'
            except:
                pass
    except:
        pass
    
    # 7. Padrão: desenvolvimento
    print("[DETECT] Nenhum indicador de produção encontrado - ambiente de desenvolvimento")
    return 'development'

def _setup_proxy_and_certs():
    """
    Configura proxy e certificados baseado no código da empresa
    Implementa detecção inteligente de ambiente e fallback resiliente
    """
    environment = detect_environment()
    print(f"[SETUP] Ambiente detectado: {environment.upper()}")
    script_dir = os.path.dirname(__file__)
    cert_path = os.path.join(script_dir, 'certificados', 'ca_bundle.pem')
    
    if environment == 'production':
        print("[SETUP] Configurando ambiente de PRODUÇÃO...")
        
        # Configuração do certificado (exatamente como no código da empresa)
        if os.path.isfile(cert_path):
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            print(f"[SETUP] Certificado configurado: {cert_path}")
        else:
            print(f"[SETUP] AVISO: Certificado não encontrado em: {cert_path}")
            print("[SETUP] Tentando sem certificado...")
    
    else:
        print("[SETUP] Configurando ambiente de DESENVOLVIMENTO...")
        
        # Remove certificado se existir
        if 'REQUESTS_CA_BUNDLE' in os.environ:
            del os.environ['REQUESTS_CA_BUNDLE']
            print("[SETUP] Removido REQUESTS_CA_BUNDLE")
        
        print("[SETUP] Ambiente de desenvolvimento configurado - conexão direta")
# Executa a configuração ao carregar o módulo
_setup_proxy_and_certs()

class ElloxAPI:
    """Cliente para integração com a API Ellox da Comexia"""
    
    def __init__(self, email: str = None, password: str = None, api_key: str = None, base_url: str = "https://apidtz.comexia.digital", token_expires_at: Optional[datetime] = None, proxy_config: Optional[Dict[str, str]] = None):
        """
        Inicializa o cliente da API Ellox
        
        Args:
            email: Email para autenticação (opcional se api_key fornecida)
            password: Senha para autenticação (opcional se api_key fornecida)
            api_key: Chave de API da Comexia (opcional se email/password fornecidos)
            base_url: URL base da API
            proxy_config: Dicionário com configurações de proxy (host, port, username, password)
        """
        self.base_url = base_url
        self.email = email
        self.password = password
        self.api_key = api_key
        self.authenticated = False
        self.token_expires_at = token_expires_at
        self.proxy_config = proxy_config
        print(f"[ElloxAPI.__init__] Proxy config recebido: {self.proxy_config}")
        
        # Se temos api_key e não está expirada, utiliza; senão tenta autenticar
        if self.api_key and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            pass
        elif self.email and self.password:
            self._authenticate()

        if self.api_key:
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            self.authenticated = True
        else:
            self.headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

    def _get_effective_proxies(self) -> Dict[str, Optional[str]]:
        """
        Determines the effective proxy settings to be used for a requests call.
        Prioritizes explicit proxy_config from the instance, then checks os.environ.
        Returns {'http': None, 'https': None} if no proxy should be used.
        """
        # 1. Prioritize proxy_config from instance (explicitly set in app)
        if self.proxy_config and \
           self.proxy_config.get('host') and \
           self.proxy_config.get('port') and \
           self.proxy_config.get('username') and \
           self.proxy_config.get('password'):
            
            username = self.proxy_config['username']
            password = self.proxy_config['password']
            host = self.proxy_config['host']
            port = self.proxy_config['port']
            proxy_url = f"http://{username}:{password}@{host}:{port}"
            print(f"[PROXY_DEBUG] Usando proxy da instância: {host}:{port}")
            return {"http": proxy_url, "https": proxy_url}
        
        # 2. Fallback to os.environ (system-wide or set by _setup_proxy_and_certs if it did)
        http_proxy_env = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
        https_proxy_env = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')

        if http_proxy_env or https_proxy_env:
            print(f"[PROXY_DEBUG] Usando proxy do ambiente: http={http_proxy_env}, https={https_proxy_env}")
            return {"http": http_proxy_env, "https": https_proxy_env}
        
        # 3. No proxy configured, explicitly disable
        print("[PROXY_DEBUG] Nenhuma configuração de proxy encontrada. Conexão direta.")
        return {'http': None, 'https': None}
    def _authenticate(self) -> str:
        """
        Autentica usando email e senha para obter token de acesso com fallback resiliente
        
        Returns:
            Token de acesso da API
        """
        print("[AUTH] Iniciando autenticação...")
        
        # Tenta primeiro com configuração atual
        token = self._authenticate_with_current_config()
        if token:
            print("[AUTH] Autenticação bem-sucedida com configuração atual")
            return token
        
        # Se falhou, tenta com fallback
        print("[AUTH] Falha com configuração atual, tentando fallback...")
        return self._authenticate_with_fallback()
    
    def _authenticate_with_current_config(self) -> str:
        """
        Autentica usando configuração atual (proxy + certificado se configurado)
        """
        effective_proxies = self._get_effective_proxies()
        print(f"[AUTH_CURRENT] Tentando autenticar com proxies efetivos: {effective_proxies}")
        
        original_proxies_env = {}
        if effective_proxies.get('http') is None and effective_proxies.get('https') is None:
            # Se a intenção é conexão direta, limpar variáveis de ambiente de proxy temporariamente
            proxy_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    original_proxies_env[var] = os.environ[var]
                    del os.environ[var]
            print("[AUTH_CURRENT] Variáveis de ambiente de proxy limpas temporariamente para conexão direta.")

        try:
            import json
            
            auth_payload = json.dumps({
                "email": self.email,
                "senha": self.password
            })
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/api/auth",
                data=auth_payload,
                headers=headers,
                timeout=30,
                proxies=effective_proxies
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token") or data.get("token")
                if token:
                    self._set_auth_token(token, data)
                    return token
            
            print(f"[AUTH_CURRENT] Autenticação falhou com status {response.status_code}: {response.text}")
            return None
            
        except requests.exceptions.ProxyError as e:
            print(f"[AUTH_CURRENT] Erro de proxy na autenticação: {str(e)}")
            return None
        except Exception as e:
            print(f"[AUTH_CURRENT] Erro na autenticação com configuração atual: {str(e)}")
            return None
        finally:
            # Restaurar variáveis de ambiente de proxy
            for var, value in original_proxies_env.items():
                os.environ[var] = value
            if original_proxies_env: print("[AUTH_CURRENT] Variáveis de ambiente de proxy restauradas.")
    
    def _authenticate_with_fallback(self) -> str:
        """
        Autentica sem proxy e sem certificado (fallback)
        """
        try:
            import json
            
            auth_payload = json.dumps({
                "email": self.email,
                "senha": self.password
            })
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Salva configuração atual
            original_proxies = {}
            original_cert = None
            
            proxy_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    original_proxies[var] = os.environ[var]
                    del os.environ[var]
            
            if 'REQUESTS_CA_BUNDLE' in os.environ:
                original_cert = os.environ['REQUESTS_CA_BUNDLE']
                del os.environ['REQUESTS_CA_BUNDLE']

            try:
                response = requests.post(
                    f"{self.base_url}/api/auth",
                    data=auth_payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("access_token") or data.get("token")
                    if token:
                        self._set_auth_token(token, data)
                        return token
                
                return None
            finally:
                # Restaura configuração original
                for var, value in original_proxies.items():
                    os.environ[var] = value
                
                if original_cert:
                    os.environ['REQUESTS_CA_BUNDLE'] = original_cert
                
        except Exception as e:
            print(f"[AUTH] Erro na autenticação de fallback: {str(e)}")
            return None
    
    def _set_auth_token(self, token: str, data: dict):
        """
        Configura o token de autenticação e headers
        """
        self.api_key = token
        self.authenticated = True
        
        # Define expiração se disponível
        expires_in = data.get("expiracao") or data.get("expires_in")
        try:
            if expires_in:
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        except Exception:
            self.token_expires_at = None
        
        # Atualiza headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Persiste em session_state para reutilização
        try:
            st.session_state.api_token = self.api_key
            st.session_state.api_token_expires_at = self.token_expires_at.isoformat() if self.token_expires_at else None
        except Exception:
            pass
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Testa a conexão com a API
        
        Returns:
            Resultado do teste de conexão
        """
        effective_proxies = self._get_effective_proxies()
        print(f"[TEST_CONN] Testando conexão com API Ellox. Base URL: {self.base_url}, Proxies efetivos: {effective_proxies}")
        try:
            if not self.authenticated:
                print("[TEST_CONN] Não autenticado antes de testar conexão.")
                return {
                    "success": False,
                    "error": "Não autenticado",
                    "status": "disconnected"
                }
            
            # Fazer uma chamada simples para testar conectividade
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers=self.headers,
                timeout=10,
                proxies=effective_proxies,
            )
            
            if response.status_code == 200:
                print(f"[TEST_CONN] Conexão bem-sucedida. Status: {response.status_code}")
                return {
                    "success": True,
                    "status": "connected",
                    "response_time": response.elapsed.total_seconds()
                }
            else:
                print(f"[TEST_CONN] Conexão falhou. HTTP Status: {response.status_code}, Response: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "status": "error"
                }
                
        except requests.exceptions.Timeout:
            print("[TEST_CONN] Timeout na requisição.")
            return {
                "success": False,
                "error": "Timeout",
                "status": "timeout"
            }
        except requests.exceptions.ProxyError as e:
            print(f"[TEST_CONN] Erro de proxy: {str(e)}")
            return {
                "success": False,
                "error": f"Erro de proxy: {str(e)}",
                "status": "proxy_error"
            }
        except requests.exceptions.ConnectionError as e:
            print(f"[TEST_CONN] Erro de conexão: {str(e)}")
            return {
                "success": False,
                "error": f"Erro de conexão: {str(e)}",
                "status": "connection_error"
            }
        except Exception as e:
            print(f"[TEST_CONN] Erro inesperado: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

    def _ensure_auth(self) -> None:
        """Garante que há autenticação válida; renova se expirado."""
        if not self.email or not self.password:
            return
        needs_auth = (not self.api_key) or (self.token_expires_at and datetime.utcnow() >= self.token_expires_at)
        if needs_auth:
            self._authenticate()
    
    def normalize_carrier_name(self, carrier: str) -> str:
        """
        Normaliza o nome do carrier para padronização com a API
        
        Args:
            carrier: Nome do carrier extraído do PDF
            
        Returns:
            Nome normalizado do carrier
        """
        if not carrier:
            return ""
            
        carrier_upper = carrier.upper().strip()
        
        # Mapeamento de carriers para nomenclatura padrão da API
        carrier_mapping = {
            "HAPAG-LLOYD": "HAPAG-LLOYD",
            "HAPAG": "HAPAG-LLOYD",
            "HLAG": "HAPAG-LLOYD",
            "MAERSK": "MAERSK",
            "A.P. MOLLER": "MAERSK",
            "APM": "MAERSK",
            "MSC": "MSC",
            "MEDITERRANEAN SHIPPING": "MSC",
            "CMA CGM": "CMA CGM",
            "CMA": "CMA CGM",
            "COSCO": "COSCO",
            "CHINA COSCO": "COSCO",
            "EVERGREEN": "EVERGREEN",
            "EMC": "EVERGREEN",
            "OOCL": "OOCL",
            "ORIENT OVERSEAS": "OOCL",
            "PIL": "PIL",
            "PACIFIC INTERNATIONAL LINES": "PIL"
        }
        
        return carrier_mapping.get(carrier_upper, carrier_upper)
    
    def normalize_vessel_name(self, vessel_name: str) -> str:
        """
        Normaliza o nome do navio removendo prefixos comuns
        
        Args:
            vessel_name: Nome do navio extraído do PDF
            
        Returns:
            Nome normalizado do navio
        """
        if not vessel_name:
            return ""
            
        # Remove prefixos comuns
        vessel = re.sub(r'^(M/V|MV|MS)\s+', '', vessel_name, flags=re.IGNORECASE)
        
        # Normaliza espaços
        vessel = re.sub(r'\s+', ' ', vessel).strip()
        
        return vessel.upper()
    
    def _make_api_request(self, endpoint: str, params: dict = None) -> Dict[str, Any]:
        """
        Faz uma requisição à API com fallback resiliente
        Tenta primeiro com configuração atual, depois com fallback
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros da requisição
            
        Returns:
            Dicionário com resultado da requisição
        """
        print(f"[API] Fazendo requisição para: {endpoint}")
        
        # Tenta primeiro com configuração atual
        result = self._make_api_request_with_current_config(endpoint, params)
        if result.get('success'):
            print(f"[API] Sucesso com configuração atual - método: {result.get('method', 'N/A')}")
            return result
        
        # Se falhou, tenta com fallback
        print(f"[API] Falha com configuração atual, tentando fallback...")
        return self._make_api_request_with_fallback(endpoint, params)
    
    def _make_api_request_with_current_config(self, endpoint: str, params: dict = None) -> Dict[str, Any]:
        """
        Faz requisição com configuração atual (proxy + certificado se configurado)
        """
        effective_proxies = self._get_effective_proxies()
        
        original_proxies_env = {}
        if effective_proxies.get('http') is None and effective_proxies.get('https') is None:
            # Se a intenção é conexão direta, limpar variáveis de ambiente de proxy temporariamente
            proxy_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    original_proxies_env[var] = os.environ[var]
                    del os.environ[var]
            print("[API_CURRENT] Variáveis de ambiente de proxy limpas temporariamente para conexão direta.")

        try:
            # Garante autenticação válida antes da chamada
            if not endpoint.startswith("/api/auth"):
                self._ensure_auth()

            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30,
                proxies=effective_proxies,
            )
            
            # Se o token expirou e retornou 401, tentar reautenticar e refazer uma vez
            if response.status_code == 401 and self.email and self.password:
                print("[API] Token expirado, reautenticando...")
                self._authenticate()
                # Re-fetch effective proxies after re-authentication, in case proxy config changed
                effective_proxies_reauth = self._get_effective_proxies()
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    params=params,
                    timeout=30,
                    proxies=effective_proxies_reauth,
                    trust_env=(effective_proxies_reauth.get('http') is not None or effective_proxies_reauth.get('https') is not None)
                )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                    "method": "current_config"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "status_code": response.status_code,
                    "method": "current_config"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na requisição com configuração atual",
                "method": "current_config"
            }
        except requests.exceptions.ProxyError as e:
            return {
                "success": False,
                "error": f"Erro de proxy: {str(e)}",
                "method": "current_config"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": f"Erro de conexão: {str(e)}",
                "method": "current_config"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}",
                "method": "current_config"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}",
                "method": "current_config"
            }
        finally:
            # Restaurar variáveis de ambiente de proxy
            for var, value in original_proxies_env.items():
                os.environ[var] = value
            if original_proxies_env: print("[API_CURRENT] Variáveis de ambiente de proxy restauradas.")
    
    def _make_api_request_with_fallback(self, endpoint: str, params: dict = None) -> Dict[str, Any]:
        """
        Faz requisição com fallback (sem proxy, sem certificado)
        """
        try:
            print("[API] Tentando fallback - conexão direta...")
            
            # Garante autenticação válida antes da chamada
            if not endpoint.startswith("/api/auth"):
                self._ensure_auth()

            # Salva configuração atual
            original_proxies = {}
            original_cert = None
            
            proxy_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']
            for var in proxy_vars:
                if var in os.environ:
                    original_proxies[var] = os.environ[var]
                    del os.environ[var]
            
            if 'REQUESTS_CA_BUNDLE' in os.environ:
                original_cert = os.environ['REQUESTS_CA_BUNDLE']
                del os.environ['REQUESTS_CA_BUNDLE']

            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    params=params,
                    timeout=30,
                    proxies={}
                )
                
                # Se o token expirou e retornou 401, tentar reautenticar e refazer uma vez
                if response.status_code == 401 and self.email and self.password:
                    print("[API] Token expirado no fallback, reautenticando...")
                    self._authenticate()
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers,
                        params=params,
                        timeout=30,
                        proxies={}
                    )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "data": response.json(),
                        "status_code": response.status_code,
                        "method": "fallback"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code,
                        "method": "fallback"
                    }
            finally:
                # Restaura configuração original
                for var, value in original_proxies.items():
                    os.environ[var] = value
                
                if original_cert:
                    os.environ['REQUESTS_CA_BUNDLE'] = original_cert
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na requisição de fallback",
                "method": "fallback"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": f"Erro de conexão no fallback: {str(e)}",
                "method": "fallback"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado no fallback: {str(e)}",
                "method": "fallback"
            }
    
    def search_voyage_tracking(self, vessel_name: str, carrier: str, voyage: str, 
                             port_terminal: str = None) -> Dict[str, Any]:
        """
        Busca informações de tracking de uma viagem específica usando a API Ellox
        
        Args:
            vessel_name: Nome do navio
            carrier: Nome do carrier/armador
            voyage: Código da viagem
            port_terminal: Terminal portuário (opcional)
            
        Returns:
            Dicionário com informações de tracking da viagem
        """
        try:
            from urllib.parse import quote
            
            # Normalizar dados de entrada
            normalized_vessel = self.normalize_vessel_name(vessel_name)
            
            # Primeiro, encontrar o terminal do navio
            terminals_response = self._make_api_request("/api/terminals")
            if not terminals_response.get("success"):
                return {
                    "success": False,
                    "error": "Erro ao consultar terminais da API"
                }
            
            terminals = terminals_response.get("data", [])
            vessel_found = False
            terminal_info = None
            voyages_found = []
            
            # Procurar o navio em cada terminal
            for terminal in terminals:
                terminal_cnpj = terminal.get("cnpj")
                if not terminal_cnpj:
                    continue
                
                # Se terminal específico foi fornecido, dar prioridade
                is_preferred_terminal = not port_terminal or terminal.get("name", "").upper() == port_terminal.upper()
                
                # Verificar se o navio está neste terminal
                ships_response = self._make_api_request(f"/api/ships?terminal={terminal_cnpj}")
                if ships_response.get("success"):
                    ships = ships_response.get("data", [])
                    
                    for ship in ships:
                        if isinstance(ship, str) and normalized_vessel.upper() in ship.upper():
                            vessel_found = True
                            terminal_info = terminal
                            
                            # Buscar voyages para este navio neste terminal
                            encoded_ship = quote(ship)
                            voyages_response = self._make_api_request(
                                f"/api/voyages?ship={encoded_ship}&terminal={terminal_cnpj}"
                            )
                            
                            if voyages_response.get("success"):
                                voyages = voyages_response.get("data", [])
                                voyages_found.extend(voyages)
                                
                                # Verificar se a voyage específica existe
                                if voyage.upper() in [v.upper() for v in voyages]:
                                    return {
                                        "success": True,
                                        "data": {
                                            "vessel_name": vessel_name,
                                            "carrier": carrier,
                                            "voyage": voyage,
                                            "terminal": terminal_info.get("name"),
                                            "terminal_cnpj": terminal_info.get("cnpj"),
                                            "status": "Viagem encontrada",
                                            "available_voyages": voyages,
                                            "voyage_confirmed": True,
                                            "found_via_api": True
                                        },
                                        "status_code": 200
                                    }
                            
                            # Se encontrou no terminal preferido, para
                            if is_preferred_terminal:
                                break
                    
                    # Se encontrou no terminal preferido, para a busca
                    if vessel_found and is_preferred_terminal:
                        break
            
            # Se encontrou o navio mas não a voyage específica
            if vessel_found:
                return {
                    "success": False,
                    "error": f"Navio '{vessel_name}' encontrado, mas voyage '{voyage}' não disponível",
                    "data": {
                        "vessel_name": vessel_name,
                        "carrier": carrier,
                        "voyage": voyage,
                        "terminal": terminal_info.get("name") if terminal_info else "N/A",
                        "terminal_cnpj": terminal_info.get("cnpj") if terminal_info else "N/A",
                        "available_voyages": voyages_found,
                        "voyage_confirmed": False,
                        "found_via_api": True
                    },
                    "status_code": 404
                }
            else:
                return {
                    "success": False,
                    "error": f"Navio '{vessel_name}' não encontrado nos terminais disponíveis",
                    "suggestion": f"Verifique se '{vessel_name}' está correto ou consulte diretamente o site da Ellox",
                    "website_url": "https://elloxdigital.com/",
                    "status_code": 404
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na consulta à API - A API pode estar sobrecarregada"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}"
            }
    
    def check_company_exists(self, cnpj: str) -> Dict[str, Any]:
        """
        Verifica se uma empresa (CNPJ) existe no sistema
        
        Args:
            cnpj: CNPJ da empresa para verificar
            
        Returns:
            Dicionário com resultado da verificação
        """
        effective_proxies = self._get_effective_proxies()
        try:
            # Tenta buscar informações da empresa via API
            # Usando endpoint de terminais que pode retornar info sobre empresas
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers=self.headers,
                timeout=30,
                proxies=effective_proxies,
            )
            
            if response.status_code == 200:
                terminals = response.json()
                
                # Verifica se o CNPJ existe entre os terminais/empresas
                cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
                
                for terminal in terminals:
                    terminal_cnpj = terminal.get('cnpj', '')
                    terminal_cnpj_clean = terminal_cnpj.replace(".", "").replace("/", "").replace("-", "")
                    
                    if cnpj_clean == terminal_cnpj_clean:
                        return {
                            "success": True,
                            "exists": True,
                            "company_info": terminal,
                            "message": f"Empresa encontrada: {terminal.get('nome', 'N/A')}"
                        }
                
                return {
                    "success": True,
                    "exists": False,
                    "message": f"CNPJ {cnpj} não encontrado no sistema",
                    "suggestion": "Verifique se o CNPJ está correto ou se a empresa está cadastrada na plataforma Ellox"
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro ao verificar empresa: HTTP {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro na verificação da empresa: {str(e)}"
            }

    def request_vessel_monitoring(self, cnpj_client: str, monitoring_requests: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Solicita monitoramento de navios no sistema
        
        Args:
            cnpj_client: CNPJ do cliente
            monitoring_requests: Lista de solicitações de monitoramento
                Cada item deve conter: cnpj_terminal, nome_navio, viagem_navio
                
        Returns:
            Dicionário com resultado da solicitação
        """
        effective_proxies = self._get_effective_proxies()
        try:
            import json
            
            payload = {
                "cnpj": cnpj_client,
                "lista": monitoring_requests
            }
            
            response = requests.post(
                f"{self.base_url}/api/monitor/navio",
                headers={**self.headers, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30,
                proxies=effective_proxies,
            )
            
            if response.status_code == 201:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "Monitoramento solicitado com sucesso",
                    "status_code": response.status_code
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "error": "Dados inválidos ou parâmetros em falta",
                    "details": response.text,
                    "status_code": response.status_code
                }
            elif response.status_code == 500:
                return {
                    "success": False,
                    "error": "Erro interno do servidor",
                    "details": response.text,
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text,
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na solicitação de monitoramento"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}"
            }
    
    def view_vessel_monitoring(self, cnpj_client: str, cnpj_terminal: str, 
                              nome_navio: str, viagem_navio: str) -> Dict[str, Any]:
        """
        Visualiza monitoramento de um navio específico
        
        Args:
            cnpj_client: CNPJ do cliente
            cnpj_terminal: CNPJ do terminal de embarque
            nome_navio: Nome do navio
            viagem_navio: Identificador da viagem
            
        Returns:
            Dicionário com informações do monitoramento
        """
        effective_proxies = self._get_effective_proxies()
        try:
            import json
            
            payload = {
                "cnpj": cnpj_client,
                "cnpj_terminal": cnpj_terminal,
                "nome_navio": nome_navio,
                "viagem_navio": viagem_navio
            }
            
            response = requests.post(
                f"{self.base_url}/api/terminalmonitorings",
                headers={**self.headers, "Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30,
                proxies=effective_proxies,
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "Monitoramento encontrado",
                    "status_code": response.status_code
                }
            elif response.status_code == 201:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "Monitoramento criado/atualizado",
                    "status_code": response.status_code
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "error": "Dados inválidos ou parâmetros em falta",
                    "details": response.text,
                    "status_code": response.status_code
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "Monitoramento não encontrado",
                    "details": response.text,
                    "status_code": response.status_code
                }
            elif response.status_code == 500:
                return {
                    "success": False,
                    "error": "Erro interno do servidor",
                    "details": response.text,
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}",
                    "details": response.text,
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na consulta de monitoramento"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Erro na requisição: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro inesperado: {str(e)}"
            }
    
    def get_vessel_schedule(self, vessel_name: str, carrier: str) -> Dict[str, Any]:
        """
        Obtém cronograma completo de um navio
        
        Args:
            vessel_name: Nome do navio
            carrier: Nome do carrier
            
        Returns:
            Cronograma do navio com próximas escalas
        """
        effective_proxies = self._get_effective_proxies()
        try:
            normalized_carrier = self.normalize_carrier_name(carrier)
            normalized_vessel = self.normalize_vessel_name(vessel_name)
            
            params = {
                "vessel_name": normalized_vessel,
                "carrier": normalized_carrier
            }
            
            response = requests.get(
                f"{self.base_url}/v1/vessels/schedule",
                headers=self.headers,
                params=params,
                timeout=30,
                proxies=effective_proxies,
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro na API: {response.status_code}",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro na consulta: {str(e)}"
            }
    
    def search_port_information(self, port_name: str) -> Dict[str, Any]:
        """
        Busca informações detalhadas de um porto
        
        Args:
            port_name: Nome do porto
            
        Returns:
            Informações do porto (terminais, operadores, etc.)
        """
        effective_proxies = self._get_effective_proxies()
        try:
            params = {"port_name": port_name.strip()}
            
            response = requests.get(
                f"{self.base_url}/v1/ports/info",
                headers=self.headers,
                params=params,
                timeout=30,
                proxies=effective_proxies,
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Porto não encontrado: {response.status_code}",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro na consulta: {str(e)}"
            }

def get_default_api_client() -> ElloxAPI:
    """
    Retorna cliente da API com credenciais padrão configuradas
    
    Returns:
        Cliente da API Ellox autenticado
    """
    from app_config import ELLOX_API_CONFIG
    # Tentar usar credenciais do session state primeiro
    try:
        import streamlit as st
        from app_config import ELLOX_API_CONFIG

        email = st.session_state.get("api_email")
        password = st.session_state.get("api_password")

        if not email or not password:
            email = ELLOX_API_CONFIG.get("email")
            password = ELLOX_API_CONFIG.get("password")

        base_url = st.session_state.get("api_base_url", ELLOX_API_CONFIG.get("base_url"))

        # Verificar se proxy está habilitado
        use_proxy = st.session_state.get("use_proxy", False)

        if use_proxy:
            # Usar configurações de proxy do session state
            proxy_config = {
                "host": st.session_state.get("proxy_host"),
                "port": st.session_state.get("proxy_port"),
                "username": st.session_state.get("proxy_username"),
                "password": st.session_state.get("proxy_password"),
            }
        else:
            # Sem proxy - conexão direta
            proxy_config = {
                "host": None,
                "port": None,
                "username": None,
                "password": None,
            }

        # Reutiliza token se disponível e válido
        api_token = st.session_state.get("api_token")
        token_expires_raw = st.session_state.get("api_token_expires_at")
        token_expires_at = None
        try:
            if token_expires_raw:
                token_expires_at = datetime.fromisoformat(token_expires_raw)
        except Exception:
            token_expires_at = None
        return ElloxAPI(email=email, password=password, api_key=api_token, base_url=base_url, token_expires_at=token_expires_at, proxy_config=proxy_config)
    except:
        # Fallback para credenciais do app_config se streamlit não estiver disponível
        # Não força proxy - deixa detecção automática funcionar
        return ElloxAPI(
            email=ELLOX_API_CONFIG.get("email"), 
            password=ELLOX_API_CONFIG.get("password"), 
            base_url=ELLOX_API_CONFIG.get("base_url"),
            proxy_config=None  # Permite detecção automática de ambiente
        )

def enrich_booking_data(booking_data: Dict[str, Any], client: ElloxAPI = None) -> Dict[str, Any]:
    """
    Enriquece dados de booking com informações da API Ellox
    
    Args:
        booking_data: Dados extraídos do PDF
        client: Cliente da API (opcional, usa credenciais padrão se não fornecido)
        
    Returns:
        Dados enriquecidos com informações de tracking
    """
    if not client:
        client = get_default_api_client()
    
    if not client.authenticated:
        return {**booking_data, "api_enrichment": {"error": "Falha na autenticação da API"}}
    
    # Extrair campos necessários
    vessel_name = booking_data.get("vessel_name", "")
    carrier = booking_data.get("carrier", "")
    voyage = booking_data.get("voyage", "")
    port_terminal = booking_data.get("port_terminal_city", "")
    
    enriched_data = booking_data.copy()
    
    # Consultar tracking da viagem
    if vessel_name and carrier and voyage:
        tracking_result = client.search_voyage_tracking(
            vessel_name=vessel_name,
            carrier=carrier,
            voyage=voyage,
            port_terminal=port_terminal
        )
        
        enriched_data["api_tracking"] = tracking_result
        
        # Se encontrou dados de tracking, extrair informações úteis
        if tracking_result.get("success") and tracking_result.get("data"):
            api_data = tracking_result["data"]
            
            # Adicionar informações enriquecidas (ajustar conforme estrutura real da API)
            enriched_data["api_enrichment"] = {
                "vessel_imo": api_data.get("vessel_imo"),
                "vessel_mmsi": api_data.get("vessel_mmsi"),
                "current_position": api_data.get("current_position"),
                "next_port": api_data.get("next_port"),
                "estimated_arrival": api_data.get("estimated_arrival"),
                "delays": api_data.get("delays"),
                "route_details": api_data.get("route_details"),
                "last_updated": datetime.now().isoformat()
            }
    
    return enriched_data

def format_tracking_display(tracking_data: Dict[str, Any]) -> str:
    """
    Formata dados de tracking para exibição amigável
    
    Args:
        tracking_data: Dados de tracking da API
        
    Returns:
        String formatada para exibição
    """
    if not tracking_data.get("success"):
        return f"❌ Erro na consulta: {tracking_data.get('error', 'Erro desconhecido')}"
    
    data = tracking_data.get("data", {})
    enrichment = tracking_data.get("api_enrichment", {})
    
    if not data:
        return "ℹ️ Nenhuma informação de tracking encontrada"
    
    formatted = "🚢 **Informações de Tracking:**\n\n"
    
    if enrichment.get("vessel_imo"):
        formatted += f"• **IMO:** {enrichment['vessel_imo']}\n"
    
    if enrichment.get("current_position"):
        pos = enrichment["current_position"]
        formatted += f"• **Posição Atual:** {pos.get('latitude', 'N/A')}, {pos.get('longitude', 'N/A')}\n"
    
    if enrichment.get("next_port"):
        formatted += f"• **Próximo Porto:** {enrichment['next_port']}\n"
    
    if enrichment.get("estimated_arrival"):
        formatted += f"• **ETA Estimado:** {enrichment['estimated_arrival']}\n"
    
    if enrichment.get("delays"):
        delays = enrichment["delays"]
        if delays:
            formatted += f"• **Atrasos:** {delays}\n"
    
    if enrichment.get("last_updated"):
        formatted += f"\n*Última atualização: {enrichment['last_updated']}*"
    
    return formatted

# Configurações padrão
DEFAULT_CARRIER_MAPPING = {
    "HAPAG-LLOYD": ["HAPAG", "LLOYD", "HAPAG-LLOYD", "HLAG"],
    "MAERSK": ["MAERSK", "A.P. MOLLER", "APM"],
    "MSC": ["MSC", "MEDITERRANEAN SHIPPING"],
    "CMA CGM": ["CMA", "CGM", "CMA CGM"],
    "COSCO": ["COSCO", "CHINA COSCO", "CHINA OCEAN SHIPPING"],
    "EVERGREEN": ["EVERGREEN", "EMC"],
    "OOCL": ["OOCL", "ORIENT OVERSEAS"],
    "PIL": ["PIL", "PACIFIC INTERNATIONAL LINES"]
}


def get_voyage_monitoring_data(vessel: str, voyage: str, terminal: str) -> Dict[str, Any]:
    """
    Função de conveniência para obter dados de monitoramento de uma viagem específica.
    Usada pelo sistema de sincronização automática.
    
    Args:
        vessel (str): Nome do navio
        voyage (str): Código da viagem
        terminal (str): Terminal
        
    Returns:
        dict: Dados de monitoramento da viagem ou erro
    """
    try:
        # Criar instância da API
        api = ElloxAPI()
        
        # Obter CNPJ do cliente (assumindo que existe uma função para isso)
        # Por enquanto, vamos usar um CNPJ padrão ou buscar do banco
        cnpj_client = "12345678000199"  # CNPJ padrão - deve ser configurado
        
        # Obter CNPJ do terminal (assumindo que existe uma função para isso)
        cnpj_terminal = "98765432000188"  # CNPJ padrão - deve ser configurado
        
        # Chamar a função de visualização de monitoramento
        result = api.view_vessel_monitoring(
            cnpj_client=cnpj_client,
            cnpj_terminal=cnpj_terminal,
            nome_navio=vessel,
            viagem_navio=voyage
        )
        
        if result.get("success"):
            return {
                "success": True,
                "data": result.get("data", {}),
                "vessel": vessel,
                "voyage": voyage,
                "terminal": terminal,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Erro desconhecido"),
                "vessel": vessel,
                "voyage": voyage,
                "terminal": terminal,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro na consulta da API: {str(e)}",
            "vessel": vessel,
            "voyage": voyage,
            "terminal": terminal,
            "timestamp": datetime.now().isoformat()
        }

