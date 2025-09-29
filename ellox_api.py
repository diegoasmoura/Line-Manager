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

class ElloxAPI:
    """Cliente para integração com a API Ellox da Comexia"""
    
    def __init__(self, email: str = None, password: str = None, api_key: str = None, base_url: str = "https://apidtz.comexia.digital", token_expires_at: Optional[datetime] = None):
        """
        Inicializa o cliente da API Ellox
        
        Args:
            email: Email para autenticação (opcional se api_key fornecida)
            password: Senha para autenticação (opcional se api_key fornecida)
            api_key: Chave de API da Comexia (opcional se email/password fornecidos)
            base_url: URL base da API
        """
        self.base_url = base_url
        self.email = email
        self.password = password
        self.api_key = api_key
        self.authenticated = False
        self.token_expires_at = token_expires_at
        
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
    
    def _authenticate(self) -> str:
        """
        Autentica usando email e senha para obter token de acesso
        
        Returns:
            Token de acesso da API
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
            
            response = requests.post(
                f"{self.base_url}/api/auth",
                data=auth_payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token") or data.get("token")
                # Muitos endpoints retornam também 'expiracao' (segundos)
                expires_in = data.get("expiracao") or data.get("expires_in")
                if token:
                    self.api_key = token
                    self.authenticated = True
                    # Define expiração se disponível
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
                    return self.api_key
            
            return None
            
        except Exception as e:
            print(f"Erro na autenticação: {str(e)}")
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Testa a conexão com a API
        
        Returns:
            Resultado do teste de conexão
        """
        try:
            if not self.authenticated:
                return {
                    "success": False,
                    "error": "Não autenticado",
                    "status": "disconnected"
                }
            
            # Fazer uma chamada simples para testar conectividade
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "status": "connected",
                    "response_time": response.elapsed.total_seconds()
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "status": "error"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout",
                "status": "timeout"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Erro de conexão",
                "status": "connection_error"
            }
        except Exception as e:
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
        Faz uma requisição à API com tratamento de erros
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros da requisição
            
        Returns:
            Dicionário com resultado da requisição
        """
        try:
            # Garante autenticação válida antes da chamada
            if not endpoint.startswith("/api/auth"):
                self._ensure_auth()

            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            # Se o token expirou e retornou 401, tentar reautenticar e refazer uma vez
            if response.status_code == 401 and self.email and self.password:
                self._authenticate()
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    params=params,
                    timeout=30
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
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na requisição"
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
        try:
            # Tenta buscar informações da empresa via API
            # Usando endpoint de terminais que pode retornar info sobre empresas
            response = requests.get(
                f"{self.base_url}/api/terminals",
                headers=self.headers,
                timeout=30
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
                timeout=30
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
                timeout=15
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
                timeout=30
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
        try:
            params = {"port_name": port_name.strip()}
            
            response = requests.get(
                f"{self.base_url}/v1/ports/info",
                headers=self.headers,
                params=params,
                timeout=30
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
        email = st.session_state.get("api_email", ELLOX_API_CONFIG.get("email"))
        password = st.session_state.get("api_password", ELLOX_API_CONFIG.get("password"))
        base_url = st.session_state.get("api_base_url", ELLOX_API_CONFIG.get("base_url"))
        # Reutiliza token se disponível e válido
        api_token = st.session_state.get("api_token")
        token_expires_raw = st.session_state.get("api_token_expires_at")
        token_expires_at = None
        try:
            if token_expires_raw:
                token_expires_at = datetime.fromisoformat(token_expires_raw)
        except Exception:
            token_expires_at = None
        return ElloxAPI(email=email, password=password, api_key=api_token, base_url=base_url, token_expires_at=token_expires_at)
    except:
        # Fallback para credenciais do app_config se streamlit não estiver disponível
        return ElloxAPI(
            email=ELLOX_API_CONFIG.get("email"), 
            password=ELLOX_API_CONFIG.get("password"), 
            base_url=ELLOX_API_CONFIG.get("base_url")
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

