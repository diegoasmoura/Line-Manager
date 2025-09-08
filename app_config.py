"""
Configuração principal da aplicação Farol
Centraliza todas as configurações e constantes
"""

import os
from typing import Dict, List

# Configurações da API Ellox
ELLOX_API_CONFIG = {
    "base_url": "https://api.comexia.digital",
    "timeout": 30,
    "max_retries": 3,
    "documentation_url": "https://developers.comexia.digital/"
}

# Configurações de carriers suportados
SUPPORTED_CARRIERS = [
    "HAPAG-LLOYD",
    "MAERSK", 
    "MSC",
    "CMA CGM",
    "COSCO",
    "EVERGREEN",
    "OOCL",
    "PIL"
]

# Mapeamento de funções de extração por carrier
CARRIER_EXTRACTION_MAPPING = {
    "HAPAG-LLOYD": "extract_hapag_lloyd_data",
    "MAERSK": "extract_maersk_data",
    "MSC": "extract_msc_data", 
    "CMA CGM": "extract_cma_cgm_data",
    "COSCO": "extract_cosco_data",
    "EVERGREEN": "extract_evergreen_data",
    "OOCL": "extract_oocl_data",
    "PIL": "extract_pil_data"
}

# Configurações de interface
UI_CONFIG = {
    "page_title": "Farol - Sistema de Gestão de Bookings",
    "page_icon": "⚓",
    "layout": "wide",
    "sidebar_state": "expanded"
}

# Campos obrigatórios para validação
REQUIRED_FIELDS = [
    "booking_reference",
    "vessel_name", 
    "carrier",
    "voyage"
]

# Campos opcionais mas recomendados
OPTIONAL_FIELDS = [
    "quantity",
    "pol",
    "pod", 
    "etd",
    "eta",
    "transhipment_port",
    "port_terminal_city",
    "pdf_print_date"
]

# Configurações de formatação de datas
DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y", 
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d-%b-%Y",
    "%d-%b-%Y %H:%M",
    "%d %b %Y",
    "%d%b%y",
    "%d%b%Y",
    "%d %b %y %H:%M"
]

# Configurações de logging
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "farol_app.log"
}

# Mensagens padrão da interface
UI_MESSAGES = {
    "api_not_configured": "💡 Configure a chave da API Ellox na barra lateral para obter informações de tracking em tempo real",
    "api_configured": "✅ API Ellox configurada - Dados de tracking serão consultados automaticamente", 
    "processing_pdf": "🔍 Processando PDF...",
    "consulting_api": "🔍 Consultando informações de tracking...",
    "success_extraction": "✅ Dados extraídos com sucesso!",
    "success_api": "✅ Informações de tracking obtidas com sucesso!",
    "error_api": "❌ Erro ao consultar API",
    "error_extraction": "❌ Erro na extração de dados",
    "delay_warning": "⚠️ **Atraso reportado:**"
}

# Configurações de validação de dados
VALIDATION_RULES = {
    "booking_reference": {
        "min_length": 6,
        "max_length": 20,
        "pattern": r"^[A-Z0-9\-]+$"
    },
    "voyage": {
        "min_length": 2,
        "max_length": 10,
        "pattern": r"^[A-Z0-9\-]+$"
    },
    "quantity": {
        "min_value": 1,
        "max_value": 1000
    }
}

# Configurações de exportação
EXPORT_CONFIG = {
    "csv_encoding": "utf-8",
    "excel_engine": "openpyxl",
    "date_format": "%Y-%m-%d",
    "datetime_format": "%Y-%m-%d %H:%M:%S"
}

def get_app_config() -> Dict:
    """Retorna configuração completa da aplicação"""
    return {
        "ellox_api": ELLOX_API_CONFIG,
        "carriers": SUPPORTED_CARRIERS,
        "ui": UI_CONFIG,
        "fields": {
            "required": REQUIRED_FIELDS,
            "optional": OPTIONAL_FIELDS
        },
        "dates": DATE_FORMATS,
        "logging": LOGGING_CONFIG,
        "messages": UI_MESSAGES,
        "validation": VALIDATION_RULES,
        "export": EXPORT_CONFIG
    }

def get_carrier_config(carrier: str) -> Dict:
    """Retorna configuração específica de um carrier"""
    return {
        "name": carrier,
        "extraction_function": CARRIER_EXTRACTION_MAPPING.get(carrier),
        "supported": carrier in SUPPORTED_CARRIERS
    }

def validate_api_key(api_key: str) -> bool:
    """Valida formato da chave da API"""
    if not api_key:
        return False
    
    # Validação básica de formato (ajustar conforme padrão real)
    if len(api_key) < 20:
        return False
    
    return True

def get_environment_config() -> Dict:
    """Retorna configurações baseadas em variáveis de ambiente"""
    return {
        "debug": os.getenv("FAROL_DEBUG", "false").lower() == "true",
        "database_url": os.getenv("DATABASE_URL"),
        "api_key": os.getenv("ELLOX_API_KEY"),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

