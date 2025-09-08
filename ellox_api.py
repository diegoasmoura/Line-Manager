"""
Módulo para integração com a API Ellox da Comexia
Fornece funcionalidades de tracking e consulta de informações de viagem

Documentação: https://developers.comexia.digital/
"""

import requests
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
import streamlit as st
import re

class ElloxAPI:
    """Cliente para integração com a API Ellox da Comexia"""
    
    def __init__(self, email: str = None, password: str = None, api_key: str = None, base_url: str = "https://apidtz.comexia.digital"):
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
        
        # Se não tiver api_key, tentar autenticar com email/senha
        if not self.api_key and self.email and self.password:
            self.api_key = self._authenticate()
        
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
                if token:
                    self.authenticated = True
                    return token
            
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
    
    def search_voyage_tracking(self, vessel_name: str, carrier: str, voyage: str, 
                             port_terminal: str = None) -> Dict[str, Any]:
        """
        Busca informações de tracking de uma viagem específica
        
        Args:
            vessel_name: Nome do navio
            carrier: Nome do carrier/armador
            voyage: Código da viagem
            port_terminal: Terminal portuário (opcional)
            
        Returns:
            Dicionário com informações de tracking da viagem
        """
        try:
            # Normalizar dados de entrada
            normalized_carrier = self.normalize_carrier_name(carrier)
            normalized_vessel = self.normalize_vessel_name(vessel_name)
            
            # Parâmetros de busca
            params = {
                "vessel_name": normalized_vessel,
                "carrier": normalized_carrier,
                "voyage": voyage.upper().strip()
            }
            
            if port_terminal:
                params["terminal"] = port_terminal
            
            # Chamada para endpoint de tracking (ajustar conforme documentação real)
            response = requests.get(
                f"{self.base_url}/v1/tracking/voyage",
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
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "Viagem não encontrada na base de dados",
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro na API: {response.status_code} - {response.text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Timeout na consulta à API"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Erro de conexão: {str(e)}"
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
    # Tentar usar credenciais do session state primeiro
    try:
        import streamlit as st
        email = st.session_state.get("api_email", "diego_moura@cargill.com")
        password = st.session_state.get("api_password", "Cargill@25")
        base_url = st.session_state.get("api_base_url", "https://apidtz.comexia.digital")
    except:
        # Fallback para credenciais padrão se streamlit não estiver disponível
        email = "diego_moura@cargill.com"
        password = "Cargill@25"
        base_url = "https://apidtz.comexia.digital"
    
    return ElloxAPI(email=email, password=password, base_url=base_url)

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

