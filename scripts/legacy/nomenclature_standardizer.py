"""
Módulo para padronização de nomenclaturas entre PDFs e API Ellox
Garante consistência nos nomes de carriers, navios e portos
"""

import re
from typing import Dict, List, Optional

class NomenclatureStandardizer:
    """Classe para padronização de nomenclaturas"""
    
    def __init__(self):
        """Inicializa o padronizador com os mapeamentos"""
        
        # Mapeamento de carriers para nomenclatura padrão
        self.carrier_mapping = {
            # HAPAG-LLOYD
            "HAPAG-LLOYD": "HAPAG-LLOYD",
            "HAPAG": "HAPAG-LLOYD",
            "LLOYD": "HAPAG-LLOYD",
            "HLAG": "HAPAG-LLOYD",
            "HAPAG LLOYD": "HAPAG-LLOYD",
            
            # MAERSK
            "MAERSK": "MAERSK",
            "A.P. MOLLER": "MAERSK",
            "APM": "MAERSK",
            "AP MOLLER": "MAERSK",
            "MAERSK LINE": "MAERSK",
            
            # MSC
            "MSC": "MSC",
            "MEDITERRANEAN SHIPPING": "MSC",
            "MEDITERRANEAN SHIPPING COMPANY": "MSC",
            "MSC MEDITERRANEAN SHIPPING": "MSC",
            
            # CMA CGM
            "CMA CGM": "CMA CGM",
            "CMA": "CMA CGM",
            "CGM": "CMA CGM",
            "CMA-CGM": "CMA CGM",
            
            # COSCO
            "COSCO": "COSCO",
            "CHINA COSCO": "COSCO",
            "CHINA OCEAN SHIPPING": "COSCO",
            "COSCO SHIPPING": "COSCO",
            "CHINA COSCO SHIPPING": "COSCO",
            
            # EVERGREEN
            "EVERGREEN": "EVERGREEN",
            "EMC": "EVERGREEN",
            "EVERGREEN MARINE": "EVERGREEN",
            "EVERGREEN LINE": "EVERGREEN",
            
            # OOCL
            "OOCL": "OOCL",
            "ORIENT OVERSEAS": "OOCL",
            "ORIENT OVERSEAS CONTAINER LINE": "OOCL",
            "ORIENT OVERSEAS CONTAINER LINES": "OOCL",
            
            # PIL
            "PIL": "PIL",
            "PACIFIC INTERNATIONAL LINES": "PIL",
            "PACIFIC INTERNATIONAL LINE": "PIL",
        }
        
        # Mapeamento de portos para nomenclatura padrão
        self.port_mapping = {
            # Brasil
            "SANTOS": "Santos",
            "PORTO DE SANTOS": "Santos", 
            "SANTOS BRASIL": "Santos",
            "SANTOS PORT": "Santos",
            "SAO PAULO": "Santos",
            "PARANAGUA": "Paranaguá",
            "PORTO DE PARANAGUA": "Paranaguá",
            "RIO DE JANEIRO": "Rio de Janeiro",
            "VITORIA": "Vitória",
            "SALVADOR": "Salvador",
            "FORTALEZA": "Fortaleza",
            "SUAPE": "Suape",
            "PECEM": "Pecém",
            
            # Ásia
            "SINGAPORE": "Singapore",
            "SINGAPURA": "Singapore",
            "HO CHI MINH": "Ho Chi Minh City",
            "HO CHI MINH CITY": "Ho Chi Minh City",
            "SAIGON": "Ho Chi Minh City",
            "CAT LAI": "Ho Chi Minh City",
            "HONG KONG": "Hong Kong",
            "SHANGHAI": "Shanghai",
            "NINGBO": "Ningbo",
            "SHENZHEN": "Shenzhen",
            "QINGDAO": "Qingdao",
            "TIANJIN": "Tianjin",
            "BUSAN": "Busan",
            "YOKOHAMA": "Yokohama",
            "TOKYO": "Tokyo",
            "KOBE": "Kobe",
            
            # Europa
            "HAMBURG": "Hamburg",
            "ROTTERDAM": "Rotterdam",
            "ANTWERP": "Antwerp",
            "FELIXSTOWE": "Felixstowe",
            "LE HAVRE": "Le Havre",
            "VALENCIA": "Valencia",
            "ALGECIRAS": "Algeciras",
            
            # América do Norte
            "LOS ANGELES": "Los Angeles",
            "LONG BEACH": "Long Beach",
            "NEW YORK": "New York",
            "SAVANNAH": "Savannah",
            "CHARLESTON": "Charleston",
            "NORFOLK": "Norfolk",
            "VANCOUVER": "Vancouver",
            "MONTREAL": "Montreal",
        }
        
        # Padrões para limpeza de nomes de navios
        self.vessel_prefixes = [
            r"^M/V\s+",
            r"^MV\s+", 
            r"^MS\s+",
            r"^M\.V\.\s+",
            r"^VESSEL\s+",
            r"^SHIP\s+"
        ]
    
    def standardize_carrier(self, carrier: str) -> str:
        """
        Padroniza nome do carrier
        
        Args:
            carrier: Nome do carrier extraído do PDF
            
        Returns:
            Nome padronizado do carrier
        """
        if not carrier:
            return ""
        
        # Normalizar para maiúsculas e remover espaços extras
        carrier_clean = re.sub(r'\s+', ' ', carrier.upper().strip())
        
        # Buscar no mapeamento
        return self.carrier_mapping.get(carrier_clean, carrier_clean)
    
    def standardize_vessel(self, vessel_name: str) -> str:
        """
        Padroniza nome do navio
        
        Args:
            vessel_name: Nome do navio extraído do PDF
            
        Returns:
            Nome padronizado do navio
        """
        if not vessel_name:
            return ""
        
        vessel_clean = vessel_name.strip()
        
        # Remover prefixos comuns
        for prefix in self.vessel_prefixes:
            vessel_clean = re.sub(prefix, '', vessel_clean, flags=re.IGNORECASE)
        
        # Normalizar espaços
        vessel_clean = re.sub(r'\s+', ' ', vessel_clean).strip()
        
        # Converter para maiúsculas para consistência com API
        return vessel_clean.upper()
    
    def standardize_port(self, port_name: str) -> str:
        """
        Padroniza nome do porto
        
        Args:
            port_name: Nome do porto extraído do PDF
            
        Returns:
            Nome padronizado do porto
        """
        if not port_name:
            return ""
        
        # Remover conteúdo entre parênteses e após vírgulas
        port_clean = re.sub(r'\s*\([^)]*\)', '', port_name)
        port_clean = re.sub(r',.*', '', port_clean)
        
        # Normalizar espaços e maiúsculas
        port_clean = re.sub(r'\s+', ' ', port_clean.upper().strip())
        
        # Buscar no mapeamento
        return self.port_mapping.get(port_clean, port_clean.title())
    
    def standardize_voyage(self, voyage: str) -> str:
        """
        Padroniza código da viagem
        
        Args:
            voyage: Código da viagem extraído do PDF
            
        Returns:
            Código padronizado da viagem
        """
        if not voyage:
            return ""
        
        # Remover espaços e converter para maiúsculas
        voyage_clean = re.sub(r'\s+', '', voyage.upper().strip())
        
        return voyage_clean
    
    def standardize_booking_data(self, booking_data: Dict) -> Dict:
        """
        Padroniza todos os campos de um booking
        
        Args:
            booking_data: Dados do booking extraídos do PDF
            
        Returns:
            Dados padronizados
        """
        standardized = booking_data.copy()
        
        # Padronizar campos principais
        if "carrier" in standardized:
            standardized["carrier"] = self.standardize_carrier(standardized["carrier"])
        
        if "vessel_name" in standardized:
            standardized["vessel_name"] = self.standardize_vessel(standardized["vessel_name"])
        
        if "voyage" in standardized:
            standardized["voyage"] = self.standardize_voyage(standardized["voyage"])
        
        # Padronizar portos
        port_fields = ["pol", "pod", "transhipment_port", "port_terminal_city"]
        for field in port_fields:
            if field in standardized and standardized[field]:
                standardized[field] = self.standardize_port(standardized[field])
        
        return standardized
    
    def get_carrier_variations(self, standard_carrier: str) -> List[str]:
        """
        Retorna todas as variações conhecidas de um carrier padrão
        
        Args:
            standard_carrier: Nome padrão do carrier
            
        Returns:
            Lista de variações conhecidas
        """
        variations = []
        for variation, standard in self.carrier_mapping.items():
            if standard == standard_carrier:
                variations.append(variation)
        
        return variations
    
    def get_port_variations(self, standard_port: str) -> List[str]:
        """
        Retorna todas as variações conhecidas de um porto padrão
        
        Args:
            standard_port: Nome padrão do porto
            
        Returns:
            Lista de variações conhecidas
        """
        variations = []
        for variation, standard in self.port_mapping.items():
            if standard == standard_port:
                variations.append(variation)
        
        return variations

# Instância global do padronizador
standardizer = NomenclatureStandardizer()

# Funções de conveniência para uso direto
def standardize_carrier(carrier: str) -> str:
    """Padroniza nome do carrier"""
    return standardizer.standardize_carrier(carrier)

def standardize_vessel(vessel_name: str) -> str:
    """Padroniza nome do navio"""
    return standardizer.standardize_vessel(vessel_name)

def standardize_port(port_name: str) -> str:
    """Padroniza nome do porto"""
    return standardizer.standardize_port(port_name)

def standardize_voyage(voyage: str) -> str:
    """Padroniza código da viagem"""
    return standardizer.standardize_voyage(voyage)

def standardize_booking_data(booking_data: Dict) -> Dict:
    """Padroniza todos os campos de um booking"""
    return standardizer.standardize_booking_data(booking_data)

