##pdf_booking_processor.py
# 
# ✅ FUNCIONALIDADE: Processamento de PDFs de Booking
# Extrai dados de PDFs de Booking recebidos por e-mail e processa para inserção na F_CON_RETURN_CARRIERS
# 
# Funcionalidades implementadas:
# - Extração de texto de PDFs usando PyPDF2
# - Identificação automática de armador/carrier baseado no conteúdo
# - Extração de dados específicos usando regex patterns
# - Validação e normalização de dados extraídos
# - Interface de validação para o usuário
# - Inserção na tabela F_CON_RETURN_CARRIERS com status "Received from Carrier"
# 
import streamlit as st
import pandas as pd
import re
from datetime import datetime
from database import get_database_connection, insert_return_carrier_from_ui, upsert_terminal_monitorings_from_dataframe
from sqlalchemy import text
import uuid
import os
import glob

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    st.error("⚠️ pdfplumber não está instalado. Execute: pip install pdfplumber")

# Padrões de extração por armador/carrier
CARRIER_PATTERNS = {
    "MAERSK": {
        "booking_reference": [
            r"Booking No\.?:\s*(\d+)",  # Padrão específico Maersk
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9]{8,12})",
            r"(\d{9})",  # Padrão genérico para números de 9 dígitos (como 243601857)
        ],
        "vessel_name": [
            r"MVS\s+([^(]+?)(?:\s*\([^)]*\))?\s+(\d+[A-Z]?)",  # Padrão MVS Maersk
            r"Vessel[\s:]+([A-Z\s]+)",
            r"Ship[\s:]+([A-Z\s]+)",
        ],
        "voyage": [
            r"MVS\s+[^(]+?\s+(\d+[A-Z]?)",  # Extrai voyage do padrão MVS
            r"Voyage[\s:]+([A-Z0-9]+)",
        ],
        "quantity": [
            r"(\d+)\s+40\s+DRY",  # Padrão específico Maersk
            r"(\d+)\s+(?:20|40|45)\s+([A-Z/ ]+?)\b",  # Padrão genérico
            r"Quantity[\s:]+(\d+)",
        ],
        "pol": [
            r"From:\s*([^,\n]+,[^,\n]+,[^,\n]+)",  # Padrão específico Maersk
            r"Port\s+of\s+Loading[\s:]+([A-Z\s,]+)",
            r"POL[\s:]+([A-Z\s,]+)",
        ],
        "pod": [
            r"(?:To|TO)\s*:\s*([^,\n]+(?:,[^,\n]+)?(?:,[^,\n]+)?)",  # Padrão específico Maersk
            r"Port\s+of\s+Discharge[\s:]+([A-Z\s,]+)",
            r"POD[\s:]+([A-Z\s,]+)",
        ],
        "etd": [
            r"(\d{4}-\d{2}-\d{2})\s+\d{4}-\d{2}-\d{2}",  # Primeira data do padrão MVS
            r"ETD[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "eta": [
            r"\d{4}-\d{2}-\d{2}\s+(\d{4}-\d{2}-\d{2})",  # Segunda data do padrão MVS
            r"ETA[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "cargo_type": [
            r"(?:Customer Cargo|Commodity Description)\s*:\s*(.+?)(?:\n|Service Contract|Price Owner|$)",
        ],
        "gross_weight": [
            r"Gross Weight.*?([\d\.]+)\s*KGS",
        ],
        "print_date": [
            # Padrão específico Maersk: data na linha após o título
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UT",  # Formato: 2024-08-19 18:31 UT
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UT",  # Com segundos
            # Padrões genéricos para outros formatos
            r"Print Date:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UTC",  # Formato específico: 2024-09-06 18:23 UTC
            r"Print Date:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UTC",  # Com segundos
            r"Print Date:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2})",  # Formato alternativo
        ],
    },
    "HAPAG-LLOYD": {
        "booking_reference": [
            # Nossa Referência (prioridade máxima para Hapag)
            r"Nossa\s+Referência\s*[:：]\s*([0-9]{6,12})",
            # BL/SWB completos (português / variantes) - fallback
            r"No\.?\s*de\s*BL/SWB\s*[:：]?\s*([A-Z0-9\-]{10,30})",
            r"No\.?\s*de\s*(?:BL|SWB)\s*[:：]?\s*([A-Z0-9\-]{10,30})",
            # Prefixos longos típicos Hapag
            r"(HLC[A-Z0-9]{10,20})",
            r"(HL\-[0-9]{6,20})",
            # Booking refs comuns
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9\-]{8,20})",
            r"BKG\s+(?:REF|NO)[\s:]+([A-Z0-9\-]{8,20})",
            # Padrão típico Hapag (mais flexível para não cortar)
            r"([A-Z]{4}\d{7,12})",
        ],
        "vessel_name": [
            r"Vessel[\s:]+([A-Z\s]+)",
            r"Ship[\s:]+([A-Z\s]+)",
            r"M/V\s+([A-Z\s]+)",
        ],
        "voyage": [
            r"Voyage[\s:]+([A-Z0-9]+)",
            r"Voy[\s:]+([A-Z0-9]+)",
        ],
        "quantity": [
            r"(\d+)\s*x\s*\d+['\s]*(?:containers?|cntr|ctr)",
            r"Quantity[\s:]+(\d+)",
            r"(\d+)\s*(?:containers?|cntr|ctr)",
        ],
        "pol": [
            r"Port\s+of\s+Loading[\s:]+([A-Z\s,]+)",
            r"POL[\s:]+([A-Z\s,]+)",
            r"Loading\s+Port[\s:]+([A-Z\s,]+)",
        ],
        "pod": [
            r"Port\s+of\s+Discharge[\s:]+([A-Z\s,]+)",
            r"POD[\s:]+([A-Z\s,]+)",
            r"Discharge\s+Port[\s:]+([A-Z\s,]+)",
        ],
        "etd": [
            r"ETD[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Departure[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "eta": [
            r"ETA[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Arrival[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "print_date": [
            r"Print\s*Date[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)",
            r"Run\s*Date[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)",
            r"Generated\s+on[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)",
            r"Date[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
    },
    "MSC": {
        "booking_reference": [
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9]{8,12})",
            r"([A-Z]{3}\d{7})",  # Padrão típico MSC
        ],
        "vessel_name": [
            r"Vessel[\s:]+([A-Z\s]+)",
            r"Ship[\s:]+([A-Z\s]+)",
        ],
        "voyage": [
            r"Voyage[\s:]+([A-Z0-9]+)",
        ],
        "quantity": [
            r"(\d+)\s*x\s*\d+['\s]*(?:containers?|cntr|ctr)",
            r"Quantity[\s:]+(\d+)",
        ],
        "pol": [
            r"Port\s+of\s+Loading[\s:]+([A-Z\s,]+)",
            r"POL[\s:]+([A-Z\s,]+)",
        ],
        "pod": [
            r"Port\s+of\s+Discharge[\s:]+([A-Z\s,]+)",
            r"POD[\s:]+([A-Z\s,]+)",
        ],
        "etd": [
            r"ETD[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "eta": [
            r"ETA[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
    },
    "CMA CGM": {
        "booking_reference": [
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9\-]{6,20})",
            r"e[ -]?Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9\-]{6,20})",
            r"BOOKING\s+CONFIRMATION\s*N[°o]?\s*[:\-]?\s*([A-Z0-9\-]{6,20})",
            r"Reference\s+No\.?\s*[:\-]?\s*([A-Z0-9\-]{6,20})",
        ],
        "vessel_name": [
            r"Vessel\s*/\s*Voyage\s*[:\-]?\s*([^\n/]+?)\s*/\s*[A-Z0-9\-]+",
            r"Vessel\s*[:\-]?\s*([A-Z0-9\s\-]+)",
        ],
        "voyage": [
            r"Vessel\s*/\s*Voyage\s*[:\-]?\s*[^\n/]+?\s*/\s*([A-Z0-9\-]+)",
            r"Voyage\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "quantity": [
            r"(\d+)\s*[xX]\s*(?:20|40|45)[\s']*(?:HC|DV|DRY|GP|REEFER|RF|RH)?",
            r"Equipment\s*[:\-]?\s*(\d+)\s*[xX]",
            r"Quantity\s*[:\-]?\s*(\d+)",
        ],
        "pol": [
            r"Port\s+of\s+Loading\s*[:\-]?\s*([A-Z\s,\-]+)",
            r"Load\s+Port\s*[:\-]?\s*([A-Z\s,\-]+)",
            r"Place\s+of\s+Receipt\s*[:\-]?\s*([A-Z\s,\-]+)",
        ],
        "pod": [
            r"Port\s+of\s+Discharge\s*[:\-]?\s*([A-Z\s,\-]+)",
            r"Discharge\s+Port\s*[:\-]?\s*([A-Z\s,\-]+)",
            r"Final\s+Destination\s*[:\-]?\s*([A-Z\s,\-]+)",
        ],
        "etd": [
            r"ETD\s*[:\-]?\s*(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})",
        ],
        "eta": [
            r"ETA\s*[:\-]?\s*(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})",
        ],
        "print_date": [
            r"Printed\s+on\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)",
            r"Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)",
            r"Emission\s+Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
        ],
    },
    "GENERIC": {  # Padrões genéricos para outros armadores
        "booking_reference": [
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9]{6,15})",
            r"BKG\s+(?:REF|NO)[\s:]+([A-Z0-9]{6,15})",
            r"Reference[\s:]+([A-Z0-9]{6,15})",
        ],
        "vessel_name": [
            r"Vessel[\s:]+([A-Z\s]+)",
            r"Ship[\s:]+([A-Z\s]+)",
            r"M/V\s+([A-Z\s]+)",
        ],
        "voyage": [
            r"Voyage[\s:]+([A-Z0-9]+)",
            r"Voy[\s:]+([A-Z0-9]+)",
        ],
        "quantity": [
            r"(\d+)\s*x\s*\d+['\s]*(?:containers?|cntr|ctr)",
            r"Quantity[\s:]+(\d+)",
            r"(\d+)\s*(?:containers?|cntr|ctr)",
        ],
        "pol": [
            r"Port\s+of\s+Loading[\s:]+([A-Z\s,]+)",
            r"POL[\s:]+([A-Z\s,]+)",
            r"Loading\s+Port[\s:]+([A-Z\s,]+)",
        ],
        "pod": [
            r"Port\s+of\s+Discharge[\s:]+([A-Z\s,]+)",
            r"POD[\s:]+([A-Z\s,]+)",
            r"Discharge\s+Port[\s:]+([A-Z\s,]+)",
        ],
        "etd": [
            r"ETD[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Departure[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "eta": [
            r"ETA[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            r"Arrival[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        ],
        "print_date": [
            # Padrão específico Maersk: data na linha após o título
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UT",  # Formato: 2024-08-19 18:31 UT
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UT",  # Com segundos
            # Padrões genéricos para outros formatos
            r"Print Date:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UTC",  # Formato específico: 2024-09-06 18:23 UTC
            r"Print Date:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UTC",  # Com segundos
            r"Print Date:\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2})",  # Formato alternativo
            r"Printed[\s:]+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2})",  # Variação "Printed"
            r"Date[\s:]+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",  # Padrão mais genérico
        ],
    }
}

def extract_text_from_pdf(pdf_file):
    """
    Extrai texto de um arquivo PDF.
    
    Args:
        pdf_file: Arquivo PDF (bytes ou file-like object)
    
    Returns:
        str: Texto extraído do PDF
    """
    if not PDF_AVAILABLE:
        return ""

    try:
        text = ""
        # Caso 1: bytes
        if isinstance(pdf_file, bytes):
            from io import BytesIO
            bio = BytesIO(pdf_file)
            bio.seek(0)
            with pdfplumber.open(bio) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()

        # Caso 2: file-like object (tem read/seek)
        if hasattr(pdf_file, "read"):
            try:
                pdf_file.seek(0)
            except Exception:
                pass
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()

        # Caso 3: caminho de arquivo (str ou path-like)
        with pdfplumber.open(str(pdf_file)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()

    except Exception:
        # Em modo não-Streamlit, evitar st.error para não poluir logs
        return ""

def identify_carrier(text):
    """
    Identifica o armador/carrier baseado no conteúdo do PDF.
    
    Args:
        text (str): Texto extraído do PDF
    
    Returns:
        str: Nome do carrier identificado ou "GENERIC"
    """
    text_upper = text.upper()
    
    # Padrões de identificação de carriers (ordem importa)
    carrier_indicators = {
        # OOCL antes de COSCO, pois muitos PDFs trazem "FROM: COSCO ... as agent for OOCL"
        "OOCL": ["OOCL", "BY OOCL APP", "MY OOCL CENTER", "BOOKING ACKNOWLEDGEMENT"],
        # PIL deve ser detectado explicitamente
        "PIL": ["PIL", "PACIFIC INTERNATIONAL LINES", "PIL AGENCIA"],
        "HAPAG-LLOYD": ["HAPAG", "LLOYD", "HAPAG-LLOYD", "HAPG", "HLAG"],
        "MAERSK": ["MAERSK", "A.P. MOLLER", "APM"],
        "MSC": ["MSC", "MEDITERRANEAN SHIPPING"],
        "CMA CGM": ["CMA", "CGM", "CMA CGM"],
        "COSCO": ["COSCO", "CHINA COSCO"],
        "EVERGREEN": ["EVERGREEN", "EMC"],
    }
    
    for carrier, indicators in carrier_indicators.items():
        for indicator in indicators:
            if indicator in text_upper:
                return carrier
    
    return "GENERIC"

def extract_data_with_patterns(text, patterns):
    """
    Extrai dados usando os padrões regex definidos.
    
    Args:
        text (str): Texto do PDF
        patterns (dict): Dicionário com padrões regex
    
    Returns:
        dict: Dados extraídos
    """
    extracted_data = {}
    
    for field, regex_list in patterns.items():
        for regex_pattern in regex_list:
            try:
                match = re.search(regex_pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    extracted_data[field] = match.group(1).strip()
                    break  # Para no primeiro match encontrado
            except Exception:
                continue  # Continua para o próximo padrão
    
    return extracted_data

def extract_maersk_data_old(text_content):
    """Extrai dados específicos para PDFs da Maersk usando padrões MVS"""
    data = {}
    
    # Usar padrões específicos da Maersk
    patterns = CARRIER_PATTERNS["MAERSK"]
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                if field == "vessel_name":
                    # Para Maersk, extrair vessel e voyage do padrão MVS
                    vessel_match = re.search(r"MVS\s+([^(]+?)(?:\s*\([^)]*\))?\s+(\d+[A-Z]?)", text_content)
                    if vessel_match:
                        # Limpar quebras de linha e espaços extras do vessel name
                        vessel_name = vessel_match.group(1).strip()
                        # Remove quebras de linha primeiro
                        vessel_name = re.sub(r'\n+', ' ', vessel_name)   # Substitui quebras por espaços
                        # Normaliza espaços múltiplos em um só
                        vessel_name = re.sub(r'\s+', ' ', vessel_name)
                        
                        # Lógica específica para juntar partes de nomes que foram separadas
                        # Casos comuns: "MAERSK L ABREA" -> "MAERSK LABREA"
                        #               "MAERSK L O T A" -> "MAERSK LOTA"
                        
                        # Primeiro, junta sequências de letras individuais (ex: "L O T A" -> "LOTA")
                        vessel_name = re.sub(r'\b([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z])\b', r'\1\2\3\4\5', vessel_name)
                        vessel_name = re.sub(r'\b([A-Z])\s+([A-Z])\s+([A-Z])\s+([A-Z])\b', r'\1\2\3\4', vessel_name)
                        vessel_name = re.sub(r'\b([A-Z])\s+([A-Z])\s+([A-Z])\b', r'\1\2\3', vessel_name)
                        vessel_name = re.sub(r'\b([A-Z])\s+([A-Z])\b', r'\1\2', vessel_name)
                        
                        # Depois, junta uma letra isolada com uma palavra seguinte
                        # Ex: "MAERSK L ABREA" -> "MAERSK LABREA"
                        vessel_name = re.sub(r'\b([A-Z])\s+([A-Z]{2,})\b', r'\1\2', vessel_name)
                        
                        data["vessel_name"] = vessel_name.strip()
                        data["voyage"] = vessel_match.group(2).strip()
                    else:
                        data["vessel_name"] = match.group(1).strip()
                elif field == "quantity":
                    # Para Maersk, extrair quantidade específica
                    qty_match = re.search(r"(\d+)\s+40\s+DRY", text_content)
                    if qty_match:
                        data["quantity"] = qty_match.group(1).strip()
                    else:
                        data["quantity"] = match.group(1).strip()
                else:
                    data[field] = match.group(1).strip()
                break
    
    # Extrair ETD e ETA do padrão MVS (antes de processar POL/POD)
    mvs_pattern = r"(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})"
    mvs_match = re.search(mvs_pattern, text_content)
    if mvs_match:
        data["etd"] = mvs_match.group(1)
        data["eta"] = mvs_match.group(2).strip()
    
    # Extrair POL e POD usando padrões mais específicos da Maersk
    # POL (From:) - Função similar ao POD
    def extract_maersk_pol(text_content):
        """Extrai POL da Maersk capturando o texto completo após 'From:'"""
        # Regex que captura tudo até o próximo campo conhecido (deve parar antes de "To:")
        from_pattern = r"(?:From|FROM)\s*:\s*(.+?)(?=To:|Booking No|$)"
        from_match = re.search(from_pattern, text_content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        if from_match:
            port_text = from_match.group(1).strip()
            
            # Remove quebras de linha e normaliza espaços
            port_clean = re.sub(r'\n+', ' ', port_text)
            port_clean = re.sub(r'\s+', ' ', port_clean)
            port_clean = port_clean.strip()
            
            # Remove campos que não são parte do porto
            port_clean = re.sub(r'Contact Name.*$', '', port_clean, flags=re.IGNORECASE)
            port_clean = re.sub(r'Booked by Ref.*$', '', port_clean, flags=re.IGNORECASE)
            port_clean = port_clean.strip()
            
            # Aplica a mesma lógica de limpeza do POD
            # Casos específicos conhecidos para POL
            port_clean = re.sub(r'\bSao\s+P\s+aulo\b', 'Sao Paulo', port_clean, flags=re.IGNORECASE)
            port_clean = re.sub(r'\bB\s+r\s+azi\s+l\b', 'Brazil', port_clean, flags=re.IGNORECASE)
            
            # Junta letras isoladas que foram separadas incorretamente
            port_clean = re.sub(r'\b([A-Z])\s+([A-Z])\b', r'\1\2', port_clean)
            port_clean = re.sub(r'\b([A-Z])\s+([a-z]+)\s+([a-z]+)\b', r'\1\2\3', port_clean)
            
            # Junta palavras quebradas comuns
            port_clean = re.sub(r'\b([A-Z][a-z]+)\s+([a-z]+)\b', r'\1\2', port_clean)
            
            # Junta letras individuais com palavras seguintes
            port_clean = re.sub(r'\b([A-Z])\s+([a-z]{2,})\b', r'\1\2', port_clean)
            
            return port_clean
        
        return None
    
    # Extrai POL usando a função melhorada
    pol_text = extract_maersk_pol(text_content)
    if pol_text:
        data["pol"] = pol_text
    
    # POD (To:) - Função melhorada para lidar com quebras de linha
    def extract_maersk_pod(text_content):
        """Extrai POD da Maersk capturando o texto completo após 'To:'"""
        # Regex que funciona: captura tudo até o próximo campo conhecido
        to_pattern = r"(?:To|TO)\s*:\s*(.+?)(?=Contact Name|Booked by Ref|Customer Cargo|Booking No)"
        to_match = re.search(to_pattern, text_content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        if to_match:
            port_text = to_match.group(1).strip()
            
            # Remove quebras de linha e normaliza espaços
            port_clean = re.sub(r'\n+', ' ', port_text)
            port_clean = re.sub(r'\s+', ' ', port_clean)
            port_clean = port_clean.strip()
            
            # Lógica inteligente para juntar palavras quebradas preservando nomes de cidades
            
            # Casos específicos conhecidos
            port_clean = re.sub(r'\bI\s+sk\s+enderun\b', 'Iskenderun', port_clean, flags=re.IGNORECASE)
            port_clean = re.sub(r'\bHo\s+Chi\s+Minh\s+Ci\s+T\s+Y\b', 'Ho Chi Minh City', port_clean, flags=re.IGNORECASE)
            
            # Junta letras isoladas que foram separadas incorretamente
            # Ex: "T Y" -> "TY", "T urk ey" -> "Turkey"
            port_clean = re.sub(r'\b([A-Z])\s+([A-Z])\b', r'\1\2', port_clean)
            port_clean = re.sub(r'\b([A-Z])\s+([a-z]+)\s+([a-z]+)\b', r'\1\2\3', port_clean)
            
            # Junta palavras quebradas comuns em PDFs
            # Ex: "Ci ty" -> "City", "Tur key" -> "Turkey"
            port_clean = re.sub(r'\b([A-Z][a-z]+)\s+([a-z]+)\b', r'\1\2', port_clean)
            
            # Junta letras individuais com palavras seguintes
            # Ex: "I sk" -> "Isk", mas preserva espaços entre palavras completas
            port_clean = re.sub(r'\b([A-Z])\s+([a-z]{2,})\b', r'\1\2', port_clean)
            
            return port_clean
        
        # Fallback: método anterior se a regex não funcionar
        to_match = re.search(r"(?:To|TO)\s*:", text_content, re.IGNORECASE | re.MULTILINE)
        if not to_match:
            print("DEBUG: 'To:' não encontrado")
            return None
        
        print(f"DEBUG: 'To:' encontrado na posição {to_match.end()}")
        
        # Obtém a posição do "To:"
        to_pos = to_match.end()
        
        # Extrai o texto após "To:" até encontrar o próximo campo
        remaining_text = text_content[to_pos:]
        print(f"DEBUG: Texto restante após 'To:': '{remaining_text[:100]}...'")
        
        # Procura pelo próximo campo (Contact Name, Booked by Ref, Customer Cargo, etc.)
        next_field_match = re.search(r'(?:Contact Name|Booked by Ref|Customer Cargo|Booking No|Service Contract|Price Owner)', remaining_text, re.IGNORECASE)
        
        if next_field_match:
            # Extrai apenas o texto do porto
            port_text = remaining_text[:next_field_match.start()].strip()
            print(f"DEBUG: Porto extraído (com próximo campo): '{port_text}'")
        else:
            # Se não encontrar próximo campo, pega as próximas linhas
            lines = remaining_text.split('\n')
            port_lines = []
            for line in lines[:10]:  # Limita a 10 linhas para evitar capturar muito
                line = line.strip()
                if line and not any(keyword in line for keyword in ['Contact Name', 'Booked by Ref', 'Customer Cargo', 'Booking No']):
                    port_lines.append(line)
                if len(port_lines) >= 5:  # Limita a 5 linhas para o porto
                    break
            port_text = ' '.join(port_lines)
            print(f"DEBUG: Porto extraído (sem próximo campo): '{port_text}'")
        
        # Limpa o texto do porto
        if port_text:
            print(f"DEBUG: Porto antes da limpeza: '{port_text}'")
            
            # Remove quebras de linha e normaliza espaços
            port_clean = re.sub(r'\n+', ' ', port_text)  # Remove quebras de linha primeiro
            port_clean = re.sub(r'\s+', ' ', port_clean)  # Normaliza espaços múltiplos
            # Remove campos que não são parte do porto
            port_clean = re.sub(r'Contact Name.*$', '', port_clean, flags=re.IGNORECASE)
            port_clean = re.sub(r'Booked by Ref.*$', '', port_clean, flags=re.IGNORECASE)
            port_clean = re.sub(r'Customer Cargo.*$', '', port_clean, flags=re.IGNORECASE)
            port_clean = port_clean.strip()
            
            print(f"DEBUG: Porto após limpeza básica: '{port_clean}'")
            
            # Lógica simplificada para juntar palavras quebradas
            # Caso específico: "I sk enderun,T urk ey" -> "Iskenderun,Turkey"
            
            # Abordagem direta: substitui padrões específicos
            port_clean = re.sub(r'\bI\s+sk\b', 'Isk', port_clean)
            print(f"DEBUG: Após substituir I+sk: '{port_clean}'")
            
            port_clean = re.sub(r'\benderun,T\s+urk\s+ey\b', 'enderun,Turkey', port_clean)
            print(f"DEBUG: Após substituir enderun,T+urk+ey: '{port_clean}'")
            
            # Caso geral: junta palavras que começam com maiúscula seguida de minúscula
            port_clean = re.sub(r'\b([A-Z])\s+([a-z]{2,})\b', r'\1\2', port_clean)
            print(f"DEBUG: Após regex geral: '{port_clean}'")
            
            # Junta palavras que terminam com minúscula seguidas de minúscula
            port_clean = re.sub(r'\b([a-z]+)\s+([a-z]{2,})\b', r'\1\2', port_clean)
            print(f"DEBUG: Após regex minúscula+minúscula: '{port_clean}'")
            
            print(f"DEBUG: Porto final: '{port_clean}'")
            return port_clean
        
        print("DEBUG: Nenhum texto de porto encontrado")
        return None
    
    # Extrai POD usando a função melhorada
    pod_text = extract_maersk_pod(text_content)
    if pod_text:
        data["pod"] = pod_text
    
    # Extrair dados adicionais específicos da Maersk
    # Cargo Type
    cargo_match = re.search(r"(?:Customer Cargo|Commodity Description)\s*:\s*(.+?)(?:\n|Service Contract|Price Owner|$)", text_content, re.IGNORECASE | re.MULTILINE)
    if cargo_match:
        cargo_text = cargo_match.group(1).strip()
        # Limpar quebras de linha
        cargo_clean = re.sub(r'\s+', ' ', cargo_text)
        data["cargo_type"] = cargo_clean.strip()
    
    # Gross Weight
    weight_match = re.search(r"Gross Weight.*?([\d\.]+)\s*KGS", text_content, re.IGNORECASE)
    if weight_match:
        data["gross_weight"] = weight_match.group(1).strip()
    
    # Document Type Detection
    doc_type_keywords = [
        ("BOOKING AMENDMENT", "BOOKING AMENDMENT"),
        ("BOOKING CONFIRMATION", "BOOKING CONFIRMATION"),
        ("BOOKING CANCELLATION", "BOOKING CANCELLATION"),
        ("ARCHIVE COPY", "ARCHIVE COPY")
    ]
    for keyword, label in doc_type_keywords:
        if keyword in text_content.upper():
            data["document_type"] = label
            break
    
    # Limpar campos de porto para formato "Cidade,Estado,País"
    if "pol" in data:
        data["pol"] = clean_port_field(data["pol"])
    
    if "pod" in data:
        data["pod"] = clean_port_field(data["pod"])
    
    return data

def extract_maersk_data(text_content):
    """Extrai dados específicos para PDFs da Maersk usando as regex do código de exemplo e pdfplumber"""
    data = {}
    
    # Regex baseadas no código de exemplo que funciona
    patterns = {
        "booking_reference": r"Booking No\.?\s*:\s*(\d+)",
        "from": r"From:\s*([^,\n]+,[^,\n]+,[^,\n]+)",
        "to": r"(?:To|TO)\s*:\s*([^,\n]+(?:,[^,\n]+)?(?:,[^,\n]+)?)",
        "cargo_type": r"(?:Customer Cargo|Commodity Description)\s*:\s*(.+?)(?:\n|Service Contract|Price Owner|$)",
        "quantity": r"(\d+)\s+40\s+DRY",
        "gross_weight": r"Gross Weight.*?([\d\.]+)\s*KGS",
    }
    
    # Extrair dados básicos usando as regex do código de exemplo
    for field, pattern in patterns.items():
        try:
            match = re.search(pattern, text_content, re.DOTALL | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
        except Exception:
            data[field] = None
    
    # Mapear campos para nomes esperados
    if "booking_reference" in data:
        data["booking_reference"] = data["booking_reference"]
    if "from" in data:
        data["pol"] = data.pop("from")  # Remove "from" e adiciona "pol"
    if "to" in data:
        data["pod"] = data.pop("to")    # Remove "to" e adiciona "pod"

    # Extrair Port Terminal City (Maersk)
    def extract_maersk_port_terminal(text: str):
        # Caso 1: padrão linear "From <TERMINAL> To ..." onde o terminal pode quebrar em 2 linhas
        m = re.search(r"From\s+([A-Z][A-Z\s\-\.'&/]+?)(?:\n([A-Z][A-Z\s\-\.'&/]+))?\s+To\b", text, re.IGNORECASE)
        if m:
            part1 = (m.group(1) or "").strip()
            part2 = (m.group(2) or "").strip()
            joined = (part1 + (" " + part2 if part2 else "")).strip()
            # Evitar capturar cidades com mistura de minúsculas como destino
            if re.fullmatch(r"[A-Z][A-Z\s\-\.'&/]+", joined):
                return re.sub(r"\s+", " ", joined)

        # Caso 2: tabela "From To Mode Vessel Voy No. ETD ETA" seguida por linhas
        lines = text.split("\n")
        header_idx = None
        for i, ln in enumerate(lines):
            if re.search(r"From\s+To\s+Mode\s+Vessel\s+Voy\s+No\.?\s+ETD\s+ETA", ln, re.IGNORECASE):
                header_idx = i
                break
        if header_idx is not None:
            # Pegar o prefixo em MAIÚSCULAS do início da primeira linha após o cabeçalho
            after = lines[header_idx+1:header_idx+12]
            if after:
                first = after[0].strip()
                # Heurística 0: pegar o ÚLTIMO trecho em maiúsculas que termina com TERMINAL dentro da primeira linha
                caps_terms = re.findall(r"([A-Z][A-Z\s\-\.'&/]*?TERMINAL)\b", first)
                if caps_terms:
                    base = re.sub(r"\s+", " ", caps_terms[-1]).strip()
                    parts = [base]
                    if len(after) > 1 and after[1].strip() == "PORTUARIO":
                        parts.append("PORTUARIO")
                    return " ".join(parts)
                # Heurística 1: capturar do início até a palavra TERMINAL (inclusive)
                m_term = re.match(r"^\s*([A-Z][A-Z\s\-\.'&/]*?TERMINAL)\b", first)
                if m_term:
                    parts = [re.sub(r"\s+", " ", m_term.group(1)).strip()]
                    # Se a próxima linha for exatamente PORTUARIO (maiusc), concatena
                    if len(after) > 1 and after[1].strip() == "PORTUARIO":
                        parts.append("PORTUARIO")
                    return " ".join(parts)
                # Heurística 2: aceitar nomes em Title Case no início da linha até um marcador (PSA, MVS, ETD/ETA, datas)
                m_title = re.match(r"^\s*([A-Za-z][A-Za-z\s\-\.'&/]+?)(?=\s+(?:PSA\b|MVS\b|Vessel\b|Voy\b|ETD\b|ETA\b|\d{4}-\d{2}-\d{2})|\s*$)", first)
                if m_title:
                    base = re.sub(r"\s+", " ", m_title.group(1)).strip()
                    parts = [base]
                    # Se a próxima linha for uma palavra/linha curta que completa o nome (ex.: "Brasileira"), concatena
                    if len(after) > 1:
                        next_line = after[1].strip()
                        if re.fullmatch(r"[A-Za-z][A-Za-z\s\-\.'&/]+", next_line) and len(next_line.split()) <= 3 and not re.search(r"\d", next_line):
                            parts.append(next_line)
                    return " ".join(parts).strip()
                m_pref = re.match(r"^\s*([A-Z][A-Z\s\-\.'&/]*[A-Z])\b", first)
                parts = []
                if m_pref:
                    parts.append(re.sub(r"\s+", " ", m_pref.group(1)).strip())
                    # Se a próxima linha for toda MAIÚSCULA, concatena (ex.: "PORTUARIO")
                    if len(after) > 1 and re.fullmatch(r"[A-Z][A-Z\s\-\.'&/]+", after[1].strip()):
                        parts.append(re.sub(r"\s+", " ", after[1].strip()))
                # Se não encontrou no prefixo da primeira, tenta segunda linha como MAIÚSCULA inteira
                if not parts and len(after) > 0 and re.fullmatch(r"[A-Z][A-Z\s\-\.'&/]+", after[0].strip()):
                    parts.append(re.sub(r"\s+", " ", after[0].strip()))
                    if len(after) > 1 and re.fullmatch(r"[A-Z][A-Z\s\-\.'&/]+", after[1].strip()):
                        parts.append(re.sub(r"\s+", " ", after[1].strip()))
                if parts:
                    return " ".join(parts).strip()

        return None

    ptc = extract_maersk_port_terminal(text_content)
    if ptc:
        data["port_terminal_city"] = ptc
    
    # Extrair print date (data de emissão) — Maersk coloca na linha após o título
    try:
        print_date_patterns = [
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UT",
            r"(?:BOOKING\s+(?:CONFIRMATION|AMENDMENT)|ARCHIVE\s+COPY)\s*\n\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UT",
            # Padrão explícito em duas linhas: 'Print Date:' na linha anterior e a data na próxima
            r"Print\s*Date\s*:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})(?:\s*(?:UTC|UT))?",
            r"Print\s*Date\s*:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\s*(?:UTC|UT))?",
        ]
        for p in print_date_patterns:
            m = re.search(p, text_content, re.IGNORECASE | re.MULTILINE)
            if m:
                data["print_date"] = m.group(1).strip()
                break
    except Exception:
        pass
    
    # Extrair ETD, ETA, Vessel e Voy No. usando a função do código de exemplo
    def extract_etd_eta_vessel(text):
        lines = text.split('\n')
        etd_eta_lines = []
        
        for line in lines:
            if re.search(r'\d{4}-\d{2}-\d{2}', line):
                if 'MVS' in line:
                    etd_eta_lines.append(line.strip())
        
        if not etd_eta_lines:
            return None, None, None, None
        
        # Extrair informações da primeira linha MVS (primeiro ETD)
        first_line = etd_eta_lines[0]
        first_dates = re.findall(r'\d{4}-\d{2}-\d{2}', first_line)
        first_etd = first_dates[0] if first_dates else None  # Primeira data da primeira linha MVS
        
        # Padrões para Vessel e Voy
        vessel_patterns = [
            r'MVS\s+PENDING MOTHER VSL\s+FLEX\s+(\d{4}-\d{2}-\d{2})',
            r'MVS\s+([^(:]+?)(?:\s*\([^)]*\))?\s+(\d+[A-Z]?)',
        ]
        
        first_vessel = None
        first_voy = None
        
        # Tentar padrão FLEX primeiro
        match = re.search(vessel_patterns[0], first_line)
        if match:
            first_vessel = "PENDING MOTHER VSL"
            first_voy = "FLEX"
        else:
            # Tentar padrão padrão
            match = re.search(vessel_patterns[1], first_line)
            if match:
                first_vessel = match.group(1).strip()
                first_voy = match.group(2)
        
        # Extrair informações da última linha MVS (último ETA)
        last_line = etd_eta_lines[-1]
        last_dates = re.findall(r'\d{4}-\d{2}-\d{2}', last_line)
        last_eta = last_dates[-1] if last_dates else None  # Segunda data da última linha MVS
        
        return first_etd, last_eta, first_vessel, first_voy
    
    # Extrair ETD, ETA, Vessel e Voy
    first_etd, last_eta, first_vessel, first_voy = extract_etd_eta_vessel(text_content)
    if first_etd:
        # Converter formato YYYY-MM-DD para DD/MM/YYYY (padrão da ferramenta)
        try:
            from datetime import datetime
            etd_date = datetime.strptime(first_etd, '%Y-%m-%d')
            data["etd"] = etd_date.strftime('%d/%m/%Y')
        except:
            data["etd"] = first_etd  # Fallback para formato original
    
    if last_eta:
        # Converter formato YYYY-MM-DD para DD/MM/YYYY (padrão da ferramenta)
        try:
            from datetime import datetime
            eta_date = datetime.strptime(last_eta, '%Y-%m-%d')
            data["eta"] = eta_date.strftime('%d/%m/%Y')
        except:
            data["eta"] = last_eta  # Fallback para formato original
    
    if first_vessel:
        data["vessel_name"] = first_vessel
    if first_voy:
        data["voyage"] = first_voy
    
    # Document Type Detection
    doc_type_keywords = [
        ("BOOKING AMENDMENT", "BOOKING AMENDMENT"),
        ("BOOKING CONFIRMATION", "BOOKING CONFIRMATION"),
        ("BOOKING CANCELLATION", "BOOKING CANCELLATION"),
        ("ARCHIVE COPY", "ARCHIVE COPY")
    ]
    for keyword, label in doc_type_keywords:
        if keyword in text_content:
            data["document_type"] = label
            break
    
    # Limpar campos de porto para formato "Cidade,Estado,País"
    if "pol" in data:
        data["pol"] = clean_port_field(data["pol"])
    
    if "pod" in data:
        data["pod"] = clean_port_field(data["pod"])
    
    return data

def extract_hapag_lloyd_data(text_content):
    """Extrai dados específicos para PDFs da Hapag-Lloyd"""
    data = {}
    # Usar padrões específicos da Hapag-Lloyd
    patterns = CARRIER_PATTERNS["HAPAG-LLOYD"]
    # Extrair campos básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            m = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if m:
                data[field] = m.group(1).strip()
                break
    # Tentar capturar Vessel quando vier na linha seguinte ao rótulo
    if "vessel_name" not in data:
        m_vsl_nl = re.search(r"Vessel\s*(?:\n|:)\s*([A-Z][A-Z\s\-]+)", text_content, re.IGNORECASE)
        if m_vsl_nl:
            data["vessel_name"] = re.sub(r"\s+", " ", m_vsl_nl.group(1).strip())

    # Heurísticas para extrair legs (De/Para) e campos estruturados
    try:
        lines = [ln.strip() for ln in text_content.split("\n") if ln.strip()]

        def is_upper_city(s: str) -> bool:
            # Casos especiais: aceitar "HO CHI MINH CITY" mesmo que não seja todo maiúsculo
            if re.search(r"HO\s+CHI\s+MINH\s+CITY", s, re.IGNORECASE):
                return True
            
            if not re.fullmatch(r"[A-Z][A-Z\s\-]+", s):
                return False
            bad = ["VESSEL", "VOY", "IMO", "CALL", "FLAG", "INLAND", "WATERWAY", "DATE", "HAPAG", "LLOYD", "DP VOYAGE"]
            # Permitir "TERMINAL" se for parte do nome da cidade/porto
            if any(b in s.upper() for b in bad):
                return False
            # Deve ter pelo menos 3 caracteres e não ser só números/códigos
            return len(s.strip()) >= 3 and not re.fullmatch(r"[A-Z0-9\-]+", s)

        legs = []
        idx = 0
        n = len(lines)
        while idx < n:
            if re.search(r"^Vessel\b", lines[idx], flags=re.IGNORECASE):
                # Vessel name: procurar melhor candidato nas próximas linhas
                vessel_name = None
                stop_keywords = re.compile(r"^(?:DP\s*Voyage|Voy\.|IMO|Call\s*Sign|Flag)\b", re.IGNORECASE)
                bad_words = re.compile(r"\b(Carrier|Is\s+In)\b", re.IGNORECASE)
                jscan = idx + 1
                while jscan < min(idx + 10, n):
                    ln = lines[jscan].strip()
                    if not ln or stop_keywords.search(ln):
                        break
                    # Ignorar linhas que obviamente não são nome de navio
                    if bad_words.search(ln) or re.fullmatch(r"Is\s+In\s+Carrier", ln, re.IGNORECASE):
                        jscan += 1
                        continue
                    if re.search(r"[A-Za-z]", ln) and len(ln) > 2:
                        # Heurística: pelo menos 2 palavras ou string longa, mas não frases genéricas
                        if (len(ln.split()) >= 2 or re.search(r"[A-Za-z]{6,}", ln)) and not re.search(r"^(Is\s+In|Carrier)", ln, re.IGNORECASE):
                            vessel_name = re.sub(r"\s+", " ", ln).strip()
                            break
                    jscan += 1

                # Voyage (DP Voyage) nas próximas 1-6 linhas
                voyage_dp = None
                for j in range(idx+1, min(idx+7, n)):
                    m_v = re.search(r"DP\s*Voyage\s*:\s*([A-Z0-9]+)", lines[j], re.IGNORECASE)
                    if m_v:
                        voyage_dp = m_v.group(1).strip()
                        break

                # Encontrar destino e origem imediatamente antes de 'Vessel'
                dest_city = None
                origin_city = None
                j = idx - 1
                
                # Procurar especificamente por "HO CHI MINH CITY" primeiro
                for k in range(max(0, idx-10), idx):
                    if re.search(r"HO\s+CHI\s+MINH\s+CITY", lines[k], re.IGNORECASE):
                        dest_city = "HO CHI MINH CITY"
                        break
                
                # Se não encontrou HO CHI MINH CITY, usar lógica padrão
                if not dest_city:
                    while j >= 0 and not dest_city:
                        if is_upper_city(lines[j]):
                            dest_city = lines[j]
                        j -= 1
                
                while j >= 0 and not origin_city:
                    if is_upper_city(lines[j]):
                        origin_city = lines[j]
                    j -= 1

                # Terminal do origin: procurar entre origin_city e dest_city por linha com TERMINAL
                origin_terminal = None
                if origin_city and dest_city:
                    # localizar índices exatos
                    try:
                        i_origin = max(i for i, ln in enumerate(lines[:idx]) if ln == origin_city)
                        i_dest = max(i for i, ln in enumerate(lines[:idx]) if ln == dest_city)
                        seg = lines[i_origin+1:i_dest]
                        for ln in seg:
                            if re.search(r"TERMINAL", ln, re.IGNORECASE):
                                origin_terminal = ln
                                break
                    except Exception:
                        pass

                legs.append({
                    "vessel_name": vessel_name,
                    "voyage": voyage_dp,
                    "origin": origin_city,
                    "dest": dest_city,
                    "origin_terminal": origin_terminal,
                })
                idx += 1
            else:
                idx += 1

        # Preencher campos principais a partir dos legs
        if legs:
            first = legs[0]
            last = legs[-1]
            if first.get("vessel_name"):
                data["vessel_name"] = first["vessel_name"]
            if first.get("voyage") and not data.get("voyage"):
                data["voyage"] = first["voyage"]
            if first.get("origin") and not data.get("pol"):
                data["pol"] = first["origin"]
            if last.get("dest") and not data.get("pod"):
                data["pod"] = last["dest"]
            # Transhipment: primeiro destino intermediário, se houver múltiplos legs
            if len(legs) > 1 and not data.get("transhipment_port"):
                # Se há 3+ trechos, o primeiro destino é transhipment
                # Se há 2 trechos, verificar se o primeiro destino não é o POD final
                first_dest = legs[0].get("dest")
                final_dest = last.get("dest")
                if first_dest and first_dest != final_dest:
                    data["transhipment_port"] = first_dest
            # Terminal do POL
            if first.get("origin_terminal") and not data.get("port_terminal_city"):
                pt = first["origin_terminal"]
                pt = re.sub(r"\s*\([^)]*\)", "", pt).strip()
                data["port_terminal_city"] = pt
    except Exception:
        pass

    # Extrair Port Terminal City (terminal de exportação)
    if not data.get("port_terminal_city"):
        # Procurar especificamente "BRASIL TERMINAL PORTUARIO SA" primeiro
        brasil_terminal_match = re.search(r"(BRASIL\s+TERMINAL\s+PORTUARIO\s+SA)", text_content, re.IGNORECASE)
        if brasil_terminal_match:
            data["port_terminal_city"] = "BRASIL TERMINAL PORTUARIO SA"
        else:
            # Fallback para outros padrões de terminal
            terminal_patterns = [
                r"Terminal\s+de\s+entrega\s+de\s+exportação\s*\n\s*([A-Z][A-Z\s]*TERMINAL[A-Z\s]*)",
                r"Endereço\s+do\s+Terminal.*?\n\s*([A-Z][A-Z\s]*TERMINAL[A-Z\s]*)",
                r"([A-Z\s]{10,}TERMINAL\s+PORTUARIO[A-Z\s]*)",
            ]
            for pattern in terminal_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
                if match:
                    terminal = re.sub(r'\s+', ' ', match.group(1).strip())
                    # Limitar a primeira linha se houver quebra
                    terminal = terminal.split('\n')[0]
                    data["port_terminal_city"] = terminal
                    break

    # Extrair PDF Print Date (Date of Issue)
    if not data.get("pdf_print_date"):
        print_date_patterns = [
            r"Date\s+of\s+Issue\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2})",
            r"ate\s+of\s+Issue\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2})",  # Para casos com "D" cortado
            r"Date\s+of\s+Issue\s*:\s*(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2})",
        ]
        for pattern in print_date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                data["pdf_print_date"] = match.group(1).strip()
                break

    # Extrair ETD/ETA das datas de saída e chegada no contexto de viagem
    if not data.get("etd") or not data.get("eta"):
        # Procurar datas em linhas com "Vessel" (formato: CIDADE CIDADE Vessel DD-MMM-YYYY DD-MMM-YYYY)
        lines = text_content.split('\n')
        vessel_dates = []
        
        for line in lines:
            if 'Vessel' in line or 'Inland Waterway' in line:
                # Extrair todas as datas da linha que contém "Vessel" ou "Inland Waterway"
                dates_in_line = re.findall(r"(\d{2}-[A-Za-z]{3}-\d{4})", line)
                vessel_dates.extend(dates_in_line)
        
        if vessel_dates:
            # ETD: primeira data de saída (primeira data de todas as viagens)
            if not data.get("etd"):
                data["etd"] = vessel_dates[0]
            # ETA: última data de chegada (última data de todas as viagens)
            if not data.get("eta"):
                data["eta"] = vessel_dates[-1]
        
        # Fallback: procurar todas as datas DD-MMM-YYYY e filtrar por contexto
        if not data.get("etd") or not data.get("eta"):
            all_dates = re.findall(r"(\d{2}-[A-Za-z]{3}-\d{4})", text_content)
            # Filtrar datas que não são Date of Issue
            filtered_dates = []
            for date_str in all_dates:
                # Pular se for a data de emissão
                if data.get("pdf_print_date") and date_str in data["pdf_print_date"]:
                    continue
                # Pular datas de reserva (Data da Reserva)
                if re.search(f"Data\\s+da\\s+Reserva.*?{re.escape(date_str)}", text_content, re.IGNORECASE):
                    continue
                filtered_dates.append(date_str)
            
            if filtered_dates and len(filtered_dates) >= 2:
                if not data.get("etd"):
                    # ETD: terceira data (após Date of Issue e Data da Reserva)
                    data["etd"] = filtered_dates[2] if len(filtered_dates) > 2 else filtered_dates[0]
                if not data.get("eta"):
                    # ETA: última data
                    data["eta"] = filtered_dates[-1]

    # Lógica especial para POD: sempre procurar HO CHI MINH CITY primeiro (apenas se existir no texto)
    if re.search(r"HO\s+CHI\s+MINH\s+CITY", text_content, re.IGNORECASE):
        data["pod"] = "HO CHI MINH CITY"  # Sempre maiúsculo
        # Se HO CHI MINH é o POD, procurar transhipments (SHANGHAI, SINGAPORE, VUNG TAU)
        if not data.get("transhipment_port"):
            # Procurar SHANGHAI primeiro (tem prioridade como primeiro transhipment)
            if re.search(r"SANTOS.*?SHANGHAI.*?Vessel", text_content, re.IGNORECASE | re.DOTALL):
                data["transhipment_port"] = "SHANGHAI"
            elif re.search(r"SINGAPORE.*?Vessel", text_content, re.IGNORECASE | re.DOTALL):
                data["transhipment_port"] = "SINGAPORE"
            elif re.search(r"\bVUNG\s+TAU\b", text_content, re.IGNORECASE):
                data["transhipment_port"] = "VUNG TAU"
    
    # Lógica adicional para casos sem HO CHI MINH CITY: usar destino da última linha com "Vessel"
    elif not data.get("pod"):
        lines = text_content.split('\n')
        vessel_lines = [line for line in lines if 'Vessel' in line]
        if vessel_lines:
            # Extrair destino da última linha com "Vessel"
            last_vessel_line = vessel_lines[-1]
            # Procurar padrão: ORIGEM DESTINO Vessel (melhor regex para destinos compostos)
            match = re.search(r"^([A-Z\s]+?)\s+([A-Z\s]+?)\s+Vessel", last_vessel_line)
            if match:
                origin_candidate = match.group(1).strip()
                destination_candidate = match.group(2).strip()
                
                # Lógica para dividir corretamente origem e destino
                # Se o destino candidato é muito curto, pode ser parte de um nome composto
                words = (origin_candidate + " " + destination_candidate).split()
                if len(words) >= 3:
                    # Assumir que as últimas 2 palavras são o destino
                    destination = " ".join(words[-2:])
                    origin = " ".join(words[:-2])
                elif len(words) == 2:
                    # Caso simples: primeira palavra origem, segunda destino
                    origin = words[0]
                    destination = words[1]
                else:
                    destination = destination_candidate
                
                # Verificar se não é uma palavra genérica
                if destination and len(destination) >= 3 and destination not in ["VESSEL", "FLAG"]:
                    data["pod"] = destination
                    
                    # Se há múltiplas linhas com "Vessel", o primeiro destino é transhipment
                    if len(vessel_lines) > 1 and not data.get("transhipment_port"):
                        first_vessel_line = vessel_lines[0]
                        first_match = re.search(r"^([A-Z\s]+?)\s+([A-Z\s]+?)\s+Vessel", first_vessel_line)
                        if first_match:
                            first_origin_candidate = first_match.group(1).strip()
                            first_destination_candidate = first_match.group(2).strip()
                            
                            # Aplicar mesma lógica para o primeiro destino
                            first_words = (first_origin_candidate + " " + first_destination_candidate).split()
                            if len(first_words) >= 3:
                                first_dest = " ".join(first_words[-2:])
                            elif len(first_words) == 2:
                                first_dest = first_words[1]
                            else:
                                first_dest = first_destination_candidate
                            
                            if first_dest and len(first_dest) >= 3 and first_dest not in ["VESSEL", "FLAG"] and first_dest != destination:
                                data["transhipment_port"] = first_dest
    
    # Fallback para POL/POD se não foram capturados pelos legs
    if not data.get("pol") or not data.get("pod"):
        # Estratégia 1: Procurar cidades brasileiras (origem) e asiáticas (destino)
        if not data.get("pol"):
            pol_patterns = [
                r"\b(SANTOS|PARANAGUA|SUAPE|ITAJAI|NAVEGANTES|RIO\s+GRANDE)\b",
                r"\b([A-Z]{5,})\s+BRASIL\b"
            ]
            for pattern in pol_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    data["pol"] = match.group(1).strip()
                    break
        
        if not data.get("pod"):
            pod_patterns = [
                r"\b(HO\s+CHI\s+MINH\s+CITY|VUNG\s+TAU|SHANGHAI|SINGAPORE|HONG\s+KONG)\b",
                r"\b([A-Z]{5,})\s+(?:CHINA|SINGAPORE|VIETNAM)\b"
            ]
            for pattern in pod_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    data["pod"] = match.group(1).strip()
                    break
        
        # Transhipment port fallback: procurar SINGAPORE se for intermediário
        if not data.get("transhipment_port") and data.get("pod") != "SINGAPORE":
            if re.search(r"\bSINGAPORE\b", text_content, re.IGNORECASE):
                data["transhipment_port"] = "SINGAPORE"
        
        # Estratégia 2: Procurar padrão "De / Para" mais específico
        if not data.get("pol") or not data.get("pod"):
            # Procurar estrutura com múltiplas linhas após "De Para"
            de_para_section = re.search(r"De\s+Para.*?\n((?:.*?\n){1,10})", text_content, re.IGNORECASE | re.MULTILINE)
            if de_para_section:
                section_text = de_para_section.group(1)
                lines = [ln.strip() for ln in section_text.split('\n') if ln.strip()]
                
                # POL: primeira cidade encontrada (geralmente brasileira)
                if not data.get("pol") and lines:
                    for line in lines[:3]:  # Primeiras 3 linhas
                        city_match = re.search(r"^([A-Z]{4,})", line)
                        if city_match:
                            city = city_match.group(1)
                            if city in ['SANTOS', 'PARANAGUA', 'SUAPE', 'ITAJAI', 'NAVEGANTES']:
                                data["pol"] = city
                                break
                
                # POD: procurar o verdadeiro destino final (HO CHI MINH tem prioridade)
                if not data.get("pod") and lines:
                    # Primeiro procurar HO CHI MINH CITY especificamente
                    for line in lines:
                        if re.search(r"HO\s+CHI\s+MINH\s+CITY", line, re.IGNORECASE):
                            data["pod"] = "HO CHI MINH CITY"
                            break
                    
                    # Se não encontrou HO CHI MINH, usar a última cidade das últimas linhas
                    if not data.get("pod"):
                        for line in reversed(lines[-3:]):  # Últimas 3 linhas
                            city_match = re.search(r"^([A-Z]{4,})", line)
                            if city_match:
                                city = city_match.group(1)
                                if city in ['SHANGHAI', 'SINGAPORE', 'VUNG']:
                                    data["pod"] = city
                                    break

    # Corrigir vessel_name inválido (ex.: "Is In Carrier") substituindo pelo melhor candidato após 'Vessel'
    try:
        invalid_vessel = False
        vsl = (data.get("vessel_name") or "").strip()
        if vsl:
            # Detectar vessel_name inválido mais amplamente
            if re.search(r"\b(Carrier|Is\s+In)\b", vsl, re.IGNORECASE):
                invalid_vessel = True
            if vsl in ["Is In Carrier", "Carrier", "Is In"]:
                invalid_vessel = True
            if len(vsl) < 4:  # Nomes muito curtos são suspeitos
                invalid_vessel = True
        else:
            invalid_vessel = True  # Se não tem vessel_name, também é inválido
        if invalid_vessel:
            # procurar melhor candidato analisando até 10 linhas após cada 'Vessel'
            lines = [ln.strip() for ln in text_content.split("\n")]
            stop_keywords = re.compile(r"^(?:DP\s*Voyage|Voy\.|IMO|Call\s*Sign|Flag)\b", re.IGNORECASE)
            bad_words = re.compile(r"\b(Carrier|Is\s+In)\b", re.IGNORECASE)
            for i, ln in enumerate(lines):
                if re.search(r"^Vessel\b", ln, re.IGNORECASE):
                    for j in range(i+1, min(i+11, len(lines))):
                        cand = lines[j].strip()
                        if not cand or stop_keywords.search(cand):
                            break
                        if bad_words.search(cand) or re.fullmatch(r"Is\s+In\s+Carrier", cand, re.IGNORECASE):
                            continue
                        # Buscar nomes que parecem navios (múltiplas palavras maiúsculas ou nome longo)
                        if re.search(r"[A-Za-z]", cand) and len(cand) > 5:
                            # Deve ter pelo menos 2 palavras OU ser uma palavra longa (6+ chars)
                            words = cand.split()
                            if len(words) >= 2 or (len(words) == 1 and len(words[0]) >= 6):
                                # Verificar se não é uma frase genérica
                                if not re.search(r"^(Is\s+In|Carrier|HAPAG|LLOYD)", cand, re.IGNORECASE):
                                    data["vessel_name"] = re.sub(r"\s+", " ", cand).strip()
                                    raise StopIteration
            
            # Se ainda não encontrou, procurar nomes típicos de navios no texto geral
            if invalid_vessel:
                vessel_patterns = [
                    r"\b(SEASPAN\s+HARRIER)\b",
                    r"\b(WAN\s+HAI\s+A10)\b",
                    r"\b(SEASPAN\s+[A-Z]+)\b",
                    r"\b(WAN\s+HAI\s+[A-Z0-9]+)\b",
                    r"\b(MSC\s+[A-Z]+)\b",
                    r"\b(MAERSK\s+[A-Z]+)\b",
                    r"\b(COSCO\s+[A-Z]+)\b"
                ]
                for pattern in vessel_patterns:
                    match = re.search(pattern, text_content, re.IGNORECASE)
                    if match:
                        candidate = match.group(1).strip()
                        # Verificar se não é uma palavra genérica
                        if not re.search(r"\b(CARRIER|HAPAG|LLOYD|BRASIL|TERMINAL|INLAND|WATERWAY)\b", candidate, re.IGNORECASE):
                            data["vessel_name"] = candidate
                            break
    except StopIteration:
        pass
    except Exception:
        pass

    # Tipo de documento
    for kw, label in [
        ("BOOKING CONFIRMATION", "BOOKING CONFIRMATION"),
        ("BOOKING AMENDMENT", "BOOKING AMENDMENT"),
        ("BOOKING CANCELLATION", "BOOKING CANCELLATION"),
    ]:
        if kw in text_content.upper():
            data["document_type"] = label
            break
    # Limpeza de portos
    if "pol" in data:
        data["pol"] = clean_port_field(data["pol"]) or data["pol"]
    if "pod" in data:
        data["pod"] = clean_port_field(data["pod"]) or data["pod"]
    # Quantidade e tipo de contêiner (formatos como 4x45GP, 4 x 40 HC etc.)
    try:
        m_qty = re.search(r"(\d+)\s*[xX×]\s*(20|40|45)\s*[''']\s*([A-Za-z]{2,})", text_content)
        if m_qty:
            data["quantity"] = m_qty.group(1).strip()
            data["container_type"] = f"{m_qty.group(2)}{m_qty.group(3).upper()}"
        else:
            # fallback: captura somente a quantidade antes de x
            m_qty_only = re.search(r"\b(\d+)\s*[xX×]\s*(?:20|40|45)\b", text_content)
            if m_qty_only and "quantity" not in data:
                data["quantity"] = m_qty_only.group(1).strip()
    except Exception:
        pass
    # Preferir pdf_print_date se só houver print_date
    if "print_date" in data and "pdf_print_date" not in data:
        data["pdf_print_date"] = data["print_date"]
    return data

def extract_msc_data(text_content):
    """Extrai dados específicos para PDFs da MSC"""
    data = {}
    
    # Usar padrões específicos da MSC
    patterns = CARRIER_PATTERNS["MSC"]
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    # Heurísticas para rótulos em português típicos da MSC Brasil
    try:
        # NAVIO E VIAGEM: exemplo "NAVIO E VIAGEM MSC GISELLE NA535R , ou substituto"
        m_nv = re.search(r"NAVIO\s+E\s+VIAGEM\s+([^\n,]+)", text_content, re.IGNORECASE)
        if m_nv:
            raw = re.sub(r"\s*,\s*ou\s+substituto.*$", "", m_nv.group(1).strip(), flags=re.IGNORECASE)
            # Separar vessel e voyage assumindo que o último token é a viagem quando alfanumérico
            parts = raw.split()
            if len(parts) >= 2 and re.search(r"[A-Za-z]\d|\d[A-Za-z]", parts[-1]):
                data["vessel_name"] = " ".join(parts[:-1])
                data["voyage"] = parts[-1]
            else:
                data["vessel_name"] = raw

        # Helpers locais para limpar cidades (remove país e códigos)
        def city_only(value: str) -> str:
            if not value:
                return None
            s = str(value)
            # corta em vírgula (pais) ou parênteses (código)
            s = re.split(r"[,\(]", s)[0]
            s = re.sub(r"\s+", " ", s).strip()
            return s.title() if s else None

        # PORTO DE EMBARQUE -> pol
        m_pol = re.search(r"PORTO\s+DE\s+EMBARQUE\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_pol and not data.get("pol"):
            pol_city = city_only(m_pol.group(1))
            if pol_city:
                data["pol"] = pol_city

        # PORTO DE TRANSBORDO -> transhipment_port
        m_trans = re.search(r"PORTO\s+DE\s+TRANSBORDO\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_trans and not data.get("transhipment_port"):
            trans_city = city_only(m_trans.group(1))
            if trans_city:
                data["transhipment_port"] = trans_city

        # PORTO DE DESCARGA -> pod
        m_pod = re.search(r"PORTO\s+DE\s+DESCARGA\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_pod and not data.get("pod"):
            pod_city = city_only(m_pod.group(1))
            if pod_city:
                data["pod"] = pod_city

        # DESTINO FINAL -> final_destination (não sobrescreve POD)
        m_final = re.search(r"DESTINO\s+FINAL[^\n:]*:?\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_final:
            # Pode vir como frase: "Para entrega ... considerar porto de destino : ANTWERP"
            tail = m_final.group(1)
            m_cons = re.search(r"destino\s*:\s*([A-Z\s\-]+)", tail, re.IGNORECASE)
            if m_cons:
                data["final_destination"] = re.sub(r"\s+", " ", m_cons.group(1).strip()).upper()
            else:
                fd_city = city_only(tail)
                if fd_city:
                    data["final_destination"] = fd_city

        # Port Terminal City (MSC)
        if not data.get("port_terminal_city"):
            # Priorizar ocorrência explícita de BRASIL TERMINAL PORTUARIO S/A
            m_btp = re.search(r"(BRASIL\s+TERMINAL\s+PORTU[ÁA]RIO\s*(?:S\s*/?\s*A)?)", text_content, re.IGNORECASE)
            if m_btp:
                data["port_terminal_city"] = re.sub(r"\s+", " ", m_btp.group(1)).upper()

        if not data.get("port_terminal_city"):
            # 1) Linha que começa com "Terminal ..." e não é genérica (ex.: "Terminal de Embarque", "Terminal Handling Charge")
            m_term = re.search(r"^\s*Terminal\s+([^\n]+)", text_content, re.IGNORECASE | re.MULTILINE)
            if m_term:
                term = re.sub(r"\s+", " ", m_term.group(1)).strip()
                if not re.search(r"\b(de\s+Embarque|Handling\s+Charge)\b", term, re.IGNORECASE):
                    data["port_terminal_city"] = term.upper()

        if not data.get("port_terminal_city"):
            # 2) Bloco em maiúsculas contendo TERMINAL/PORTUARIO em até 3 linhas seguidas
            lines = [ln.strip() for ln in text_content.split("\n")]
            i = 0
            while i < len(lines):
                ln = lines[i]
                if re.search(r"\b(TERMINAL|PORTUARIO|PORTUÁRIO)\b", ln, re.IGNORECASE):
                    # Ignorar genéricos
                    if re.search(r"\b(de\s+Embarque|Handling\s+Charge)\b", ln, re.IGNORECASE):
                        i += 1
                        continue
                    block = [ln]
                    # incluir até 2 próximas linhas se forem maiúsculas/parte do nome
                    for j in range(1, 3):
                        if i + j < len(lines):
                            nxt = lines[i + j].strip()
                            if re.fullmatch(r"[A-ZÀ-ÿ0-9/\s\.'-]+", nxt):
                                block.append(nxt)
                            else:
                                break
                    term = " ".join(p.strip(" .,") for p in block)
                    term = re.sub(r"\s+", " ", term)
                    # Remover sufixo ", Cidade"
                    term = re.sub(r",\s*[A-Za-zÀ-ÿ\-\s]+$", "", term)
                    data["port_terminal_city"] = term.upper()
                    break
                i += 1
    except Exception:
        pass

    # Quantidade e tipo (MSC) — cobrir formatos comuns
    try:
        # 1) Equipment Type/Q'ty: 40HC-5
        if not data.get("quantity"):
            m_eq = re.search(r"Equipment\s+Type\s*/\s*Q[']?ty\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
            if m_eq:
                tail = m_eq.group(1)
                m_qty = re.search(r"-(\d{1,4})\b", tail)
                if m_qty:
                    data["quantity"] = m_qty.group(1)
                m_typ = re.search(r"\b(20|40|45)\s*['']?\s*(HC|HIGH\s*CUBE|GP|DV)\b", tail, re.IGNORECASE)
                if m_typ:
                    size = m_typ.group(1)
                    kind = m_typ.group(2)
                    kind_norm = "HC" if re.search(r"HIGH\s*CUBE|HC", kind, re.IGNORECASE) else "GP"
                    data["container_type"] = f"{size}{kind_norm}"

        # 2) Linha solta: 14 40' HIGH CUBE 350,000.00 Kgs
        if not data.get("quantity"):
            m_line = re.search(r"\b(\d{1,4})\s+(20|40|45)\s*['']?\s*(HIGH\s*CUBE|HC|GP|DV)\b", text_content, re.IGNORECASE)
            if m_line:
                data["quantity"] = m_line.group(1)
                size = m_line.group(2)
                kind = m_line.group(3)
                kind_norm = "HC" if re.search(r"HIGH\s*CUBE|HC", kind, re.IGNORECASE) else "GP"
                data["container_type"] = f"{size}{kind_norm}"

        # 3) Multiplicador: 14 x 40 HC
        if not data.get("quantity"):
            m_mul = re.search(r"\b(\d{1,4})\s*[xX×]\s*(20|40|45)\s*['']?\s*(HC|HIGH\s*CUBE|GP|DV)\b", text_content, re.IGNORECASE)
            if m_mul:
                data["quantity"] = m_mul.group(1)
                size = m_mul.group(2)
                kind = m_mul.group(3)
                kind_norm = "HC" if re.search(r"HIGH\s*CUBE|HC", kind, re.IGNORECASE) else "GP"
                data["container_type"] = f"{size}{kind_norm}"

        # 4) Fallback simples: número antes de 20/40/45
        if not data.get("quantity"):
            m_simple = re.search(r"\b(\d{1,4})\s+(?=20|40|45)\b", text_content)
            if m_simple:
                data["quantity"] = m_simple.group(1)
    except Exception:
        pass

    # ETA (MSC) via "DATA PREVISTA DE CHEGADA" em PT
    try:
        if not data.get("eta"):
            m_anchor = re.search(r"DATA\s+PREVISTA\s+DE\s+CHEGADA", text_content, re.IGNORECASE)
            if m_anchor:
                tail = text_content[m_anchor.end():]
                lines = [ln.strip() for ln in tail.split("\n") if ln.strip()][:10]
                # coletar todas as datas dd/mm/yyyy nas próximas linhas e escolher a última (mais provável ETA)
                dates = []
                times = []
                for ln in lines:
                    for d in re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", ln):
                        dates.append(d)
                    for t in re.findall(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[APap]M)\b", ln):
                        times.append(t)
                if dates:
                    data["eta"] = dates[-1]  # última data encontrada
    except Exception:
        pass

    # PDF Print Date (MSC) — header com data e hora em linhas separadas
    try:
        if not data.get("pdf_print_date"):
            # Padrão A: Booking Confirmation abaixo de data/hora
            m_hdr = re.search(r"Booking\s+Confirmation[\s\S]{0,40}?\n?\s*Page\s+\d+\s+of\s+\d+", text_content, re.IGNORECASE)
            if m_hdr:
                # procurar até 3 linhas acima por data/hora
                head = text_content[:m_hdr.start()].split("\n")
                for back in range(1, 6):
                    if len(head) - back >= 0:
                        ln = head[-back].strip()
                        m_d = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", ln)
                        m_t = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[APap]M)\b", ln)
                        if m_d and m_t:
                            data["pdf_print_date"] = f"{m_d.group(1)} {m_t.group(1)}"
                            break
                # Se não encontrou juntos, olhar duas linhas consecutivas acima (data em uma, hora na outra)
                if not data.get("pdf_print_date") and len(head) >= 2:
                    last2 = head[-3:]
                    d = None; t = None
                    for ln in last2:
                        if not d:
                            m_d = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", ln)
                            if m_d:
                                d = m_d.group(1)
                        if not t:
                            m_t = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[APap]M)\b", ln)
                            if m_t:
                                t = m_t.group(1)
                    if d and t:
                        data["pdf_print_date"] = f"{d} {t}"
            # Padrão B: Companhia + data na mesma linha, hora na linha seguinte (antes do Booking)
            if not data.get("pdf_print_date"):
                m_company = re.search(r"MEDITERRANEAN\s+SHIPPING\s+COMPANY\s*(\d{2}/\d{2}/\d{4})\s*\n\s*([0-9:]{3,8}\s*[APap]M)", text_content, re.IGNORECASE)
                if m_company:
                    data["pdf_print_date"] = f"{m_company.group(1)} {m_company.group(2)}"
    except Exception:
        pass

    # Requisito: ETD não deve ser preenchido para MSC
    if "etd" in data:
        try:
            del data["etd"]
        except Exception:
            data["etd"] = ""
    return data

def extract_cma_cgm_data(text_content):
    """Extrai dados específicos para PDFs da CMA CGM"""
    data = {}

    # Helpers baseados no seu CMA.py
    def extract_city_only(value: str):
        if not value:
            return None
        s = str(value)
        # Remove data prefixada (ex.: 19-Oct-25 Qingdao -> Qingdao)
        s = re.sub(r"^[0-9]{2}[-/][A-Za-z]{3}[-/][0-9]{2,4}\s+", "", s)
        s = re.sub(r"^[0-9]{2}/[0-9]{2}/[0-9]{4}\s+", "", s)
        s = re.split(r"\bET[AD]:", s, maxsplit=1)[0]
        # Remove caudas de cut-off/fechamento caso venham na mesma linha
        s = re.sub(r"\b(?:SI|eSI|CY)\s*Cut[- ]?Off.*$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\bCut[- ]?Off.*$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\bClosing\s+Date.*$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\bYard.*$", "", s, flags=re.IGNORECASE)
        if "|" in s:
            s = s.split("|")[0]
        s = re.sub(r"^(?:PORT OF|PORTO DE|PORTO|POD|POL|PLACE OF RECEIPT)\s*:?\s*", "", s, flags=re.IGNORECASE)
        s = s.replace(" / ", ", ").replace("/", ", ")
        s = re.sub(r"\s+", " ", s).strip(" ,")
        city = s.split(",")[0].strip()
        return city.title() if city else None

    def extract_date(value: str):
        if not value:
            return None
        m = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2} \w{3} \d{4})", value)
        return m.group(1) if m else None

    def extract_vessel_voyage_info(text: str):
        # 1) Prioriza "Vessel / Voyage" e permite que o valor esteja na próxima linha
        vessel = None
        voyage = None
        m_hdr = re.search(r"Vessel\s*/\s*Voyage\s*:?", text, re.IGNORECASE)
        if m_hdr:
            tail = text[m_hdr.end():]
            lines = tail.split("\n")
            candidate = None
            for ln in lines[:3]:
                t = (ln or "").strip()
                if not t:
                    continue
                # Pular rótulos "Receipt:", "Alternate Base", etc.
                if re.search(r"^(Receipt|Alternate\s+Base|Feeder\s+Vessel|Connecting\s+Vessel|Port\s+Of|Final\s+Place|ETD|ETA|Transhipment|Shipper)\b", t, re.IGNORECASE):
                    continue
                candidate = t
                # Se a próxima linha tiver '/', preferir (valor completo)
                if '/' not in candidate and len(lines) > 1 and '/' in lines[1]:
                    candidate = lines[1].strip()
                break
            if candidate:
                candidate = re.sub(r"\b(ETD|ETA|Connecting\s+Vessel|Receipt)\b.*$", "", candidate, flags=re.IGNORECASE).strip()
                parts = [p.strip() for p in candidate.split('/') if p.strip()]
                if parts:
                    vessel = parts[0]
                    if len(parts) > 1:
                        voyage = parts[1]
        # 2) Fallback: "Connecting Vessel / Voyage" na mesma linha
        if not vessel:
            m = re.search(r"Connecting\s+Vessel\s*/\s*Voyage\s*:?\s*([^\n]+)", text, re.IGNORECASE)
            if m and m.group(1).strip():
                tail = m.group(1).strip()
                parts = [p.strip() for p in tail.split('/') if p.strip()]
                vessel = parts[0] if parts else None
                voyage = parts[1] if len(parts) > 1 else None
        # 3) ETD em qualquer lugar do texto
        etd_m = re.search(r"ETD\s*:?\s*(\d{2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        etd = etd_m.group(1) if etd_m else None
        return vessel, voyage, etd

    def extract_container_info(text: str):
        # Captura formatos como: "8 x 40'HC", "8x40 HC", "8 × 40'HC"
        m = re.search(r"(\d+)\s*[xX×]\s*(20|40|45)\s*['']?\s*([A-Za-z]{2,})", text)
        if m:
            qty = m.group(1)
            size = m.group(2)
            ctype = m.group(3)
            return qty, f"{size}{ctype.upper()}"
        # Fallback: "8 containers 40HC" ou similares
        m = re.search(r"(\d+)\s*(?:containers?|cntr|ctr)[^\n]*?(20|40|45)\s*['']?\s*([A-Za-z]{2,})", text, re.IGNORECASE)
        if m:
            qty = m.group(1)
            size = m.group(2)
            ctype = m.group(3)
            return qty, f"{size}{ctype.upper()}"
        return None, None

    # 1) Booking reference
    booking_patterns = CARRIER_PATTERNS["CMA CGM"]["booking_reference"] + [
        r"BOOKING\s+NUMBER\s*:?\s*([\w-]+)",
        r"Booking\s+No\.?\s*:?\s*([\w-]+)",
    ]
    for pat in booking_patterns:
        m = re.search(pat, text_content, re.IGNORECASE)
        if m:
            data["booking_reference"] = m.group(1).strip()
            break

    # 2) Vessel / Voyage / ETD
    vessel, voyage, etd = extract_vessel_voyage_info(text_content)
    if vessel:
        data["vessel_name"] = vessel
    if voyage:
        data["voyage"] = voyage
    if etd:
        data["etd"] = etd

    # 3) POL
    # Preferir capturar a primeira linha útil após "Port Of Loading:", ignorando rótulos como "Loading Terminal:"
    anchor = re.search(r"Port\s+Of\s+Loading\s*:?", text_content, re.IGNORECASE)
    if anchor:
        tail = text_content[anchor.end():]
        lines = tail.split("\n")
        for line in lines[:12]:  # procura nas próximas linhas
            candidate = line.strip()
            if not candidate:
                continue
            if re.search(r"Loading\s+Terminal\s*:?", candidate, re.IGNORECASE):
                # Coleta as próximas linhas úteis para o terminal (ex.: "SALVADOR" e depois "TECON SALVADOR")
                # Vamos selecionar a última linha não vazia até encontrar outro rótulo
                idx = lines.index(line)
                terminal_candidates = []
                for ln in lines[idx+1:idx+6]:
                    t = ln.strip()
                    if not t:
                        continue
                    if t.endswith(":") or re.search(r"(Ramp|Transhipment|Port\s+Of\s+Discharge|Final\s+Place|Earliest|SI\s*Cut|VGM\s*Cut|CY\s*Cut|Port\s*Cut|ETD|ETA|FPD)", t, re.IGNORECASE):
                        break
                    terminal_candidates.append(t)
                if terminal_candidates:
                    # Escolhe o candidato mais longo (provável terminal + cidade, ex.: TECON SALVADOR)
                    best = max(terminal_candidates, key=len)
                    data["port_terminal_city"] = best
                continue
            if candidate.endswith(":"):
                continue
            pol_city = extract_city_only(candidate)
            if pol_city:
                data["pol"] = pol_city
                break
    # Fallback para padrões simples em linha única
    if "pol" not in data:
        for pat in [r"PORT OF LOADING\s*:?\s*([^\n]+)", r"POL\s*:?\s*([^\n]+)"]:
            m = re.search(pat, text_content, re.IGNORECASE)
            if m:
                pol_city = extract_city_only(m.group(1))
                if pol_city:
                    data["pol"] = pol_city
                    break

    # 4) POD
    # Caso 1: valor na mesma linha (só se não for outro rótulo)
    for pat in [r"PORT OF DISCHARGE\s*:?\s*([^\n]+)", r"POD\s*:?\s*([^\n]+)"]:
        m = re.search(pat, text_content, re.IGNORECASE)
        if m and m.group(1).strip():
            candidate = m.group(1).strip()
            # Ignora se for outro rótulo
            if not (candidate.endswith(":") or re.search(r"(Final\s+Place|Loading\s+Terminal|Transhipment|Earliest|Cut.*Off)", candidate, re.IGNORECASE)):
                pod_city = extract_city_only(candidate)
                if pod_city:
                    data["pod"] = pod_city
                    break
    # Caso 2: valor em linhas subsequentes após "Port Of Discharge:" ou após "Final Place Of Delivery:" (ex.: duas linhas: POD e FINAL)
    if "pod" not in data:
        # Procura o padrão onde POD e Final Destination aparecem em sequência
        # Port Of Discharge:
        # Final Place Of Delivery:
        # SANTOS
        # HAIPHONG
        pod_anchor = re.search(r"Port\s+Of\s+Discharge\s*:?\s*\n\s*Final\s+Place\s+Of\s+Delivery\s*:?", text_content, re.IGNORECASE)
        if pod_anchor:
            tail = text_content[pod_anchor.end():]
            lines = tail.split("\n")
            values = []
            for ln in lines[:10]:
                t = ln.strip()
                if not t:
                    continue
                if t.endswith(":") or re.search(r"(Earliest|SI\s*Cut|VGM\s*Cut|CY\s*Cut|Port\s*Cut|ETD|ETA|FPD|Remarks)", t, re.IGNORECASE):
                    break
                values.append(t)
                if len(values) >= 2:
                    break
            if values:
                if len(values) >= 1:
                    pod_city = extract_city_only(values[0])
                    if pod_city:
                        data["pod"] = pod_city
                if len(values) >= 2:
                    fin_city = extract_city_only(values[1])
                    if fin_city:
                        data["final_destination"] = fin_city

    # 5) Transhipment Port (ignora se DIRECT)
    m = re.search(r"TRANSSHIPMENT PORT\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
    if m:
        raw = m.group(1)
        if not re.search(r"DIRECT", raw, re.IGNORECASE):
            # Ignorar frases genéricas
            if not re.search(r"Shall\s+Be\s+Clearly\s+Stated|Draft\s+Carriage\s+Document", raw, re.IGNORECASE):
                trans_city = extract_city_only(raw)
                if trans_city:
                    data["transhipment_port"] = trans_city
    else:
        # Alternativa: rótulo simples "Transhipment:" seguido por valor em linha subsequente ou vazio
        m2 = re.search(r"Transhipment\s*:\s*([^\n]*)", text_content, re.IGNORECASE)
        if m2:
            raw = m2.group(1).strip()
            # Ignora se for outro rótulo ou vazio
            if raw and not re.search(r"DIRECT", raw, re.IGNORECASE) and not (raw.endswith(":") or re.search(r"(Port\s+Of\s+Discharge|Final\s+Place|Loading|Cut.*Off)", raw, re.IGNORECASE)):
                if not re.search(r"Shall\s+Be\s+Clearly\s+Stated|Draft\s+Carriage\s+Document", raw, re.IGNORECASE):
                    trans_city = extract_city_only(raw)
                    if trans_city:
                        data["transhipment_port"] = trans_city
            # Se Transhipment: está vazio, não tenta extrair nada (deixa para fallback)
    # Sanitiza transhipment: não forçar fallback para POD quando rótulo ausente; se igual a Final, usar POD
    if data.get("transhipment_port") and data.get("final_destination") and data["transhipment_port"].lower() == data["final_destination"].lower() and data.get("pod"):
        data["transhipment_port"] = data["pod"]
    # Sanitiza transhipment: ignora frases genéricas; não preencher se inválido
    def _looks_invalid_trans(v: str) -> bool:
        if not v:
            return True
        if "(" in v or ")" in v:
            return True
        if re.search(r"Shall\s+Be\s+Clearly\s+Stated", v, re.IGNORECASE):
            return True
        # muitas palavras minúsculas indica frase e não porto
        lw = re.findall(r"\b[a-z]{3,}\b", v)
        return len(lw) >= 3
    # Se transhipment inválido/ausente, não preencher automaticamente com POD
    def _looks_invalid_trans(v: str) -> bool:
        if not v:
            return True
        if "(" in v or ")" in v:
            return True
        lw = re.findall(r"\b[a-z]{3,}\b", v)
        return len(lw) >= 3
    # Removido fallback para POD quando diferente de Final

    # 6) Final Destination (ignora se igual a POD ou transhipment)
    # Suporta também "Final Place Of Delivery"
    m = re.search(r"FINAL DESTINATION\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
    if not m:
        m = re.search(r"FINAL\s+PLACE\s+OF\s+DELIVERY\s*:?\s*([^\n]+)", text_content, re.IGNORECASE)
    if m:
        city = extract_city_only(m.group(1))
        if city and data.get("pod") and city.lower() == data["pod"].lower():
            city = None
        if city and data.get("transhipment_port") and city.lower() == data["transhipment_port"].lower():
            city = None
        if city:
            data["final_destination"] = city

    # 7) Quantidade e tipo de contêiner
    qty, ctype = extract_container_info(text_content)
    if qty:
        data["quantity"] = qty
    if ctype:
        data["container_type"] = ctype

    # 8) Port Terminal City (captura em linha)
    if "port_terminal_city" not in data:
        m_lt = re.search(r"Loading\s+Terminal\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_lt:
            val = m_lt.group(1)
            # Remover rótulos subsequentes na mesma linha
            val = re.sub(r"\s*(?:SI|eSI|CY|VGM|Port)\s*Cut[- ]?Off.*$", "", val, flags=re.IGNORECASE)
            val = re.split(r"\b(?:ETD|ETA|Transhipment|Port\s+Of\s+Discharge|Final\s+Place|Remarks)\b", val, maxsplit=1, flags=re.IGNORECASE)[0]
            val = re.sub(r"\s+", " ", val).strip(" ,:")
            if val:
                data["port_terminal_city"] = val

    # 8a) Extrair Transhipment usando regex simples
    if not data.get("transhipment_port"):
        # Lista de portos comuns de transbordo
        common_ports = [
            "COLOMBO", "SANTOS", "SINGAPORE", "TANGER", "TANGIER", "SALALAH",
            "PORT KLANG", "HONG KONG", "BUSAN", "JEBEL ALI", "VALENCIA", "ALGECIRAS",
            "DUBAI", "KOPER", "GIOIA TAURO", "PIRAEUS", "BARCELONA", "ROTTERDAM"
        ]
        # Procurar texto entre "Transhipment:" e o próximo rótulo
        match = re.search(r'Transhipment\s*:\s*([^:\n]*?)(?:\s+(?:ETD|ETA|Port Of|Final Place|Remarks|Payable)\s*:|$)', text_content, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if not value:  # Se não houver texto entre os rótulos
                return data
            # Se houver texto, procurar portos conhecidos
            value_up = value.upper()
            for port in common_ports:
                # Procurar palavra exata (com limites de palavra)
                if re.search(r'\b' + re.escape(port) + r'\b', value_up):
                    data["transhipment_port"] = port.title()
                    break

    # 8b) Inferir Transhipment entre Loading Terminal e 'Transhipment:' quando não houver rótulo com valor
    if not data.get("transhipment_port"):
        seg_m = re.search(r"Loading\s+Terminal\s*:([\s\S]*?)Transhipment\s*:", text_content, re.IGNORECASE)
        if seg_m:
            seg = seg_m.group(1)
            lines = [ln.strip() for ln in seg.split("\n") if ln.strip()]
            pol_up = (data.get("pol") or "").upper()
            ptc_up = (data.get("port_terminal_city") or "").upper()
            pod_up = (data.get("pod") or "").upper()
            candidates = []
            for ln in lines:
                if ":" in ln or any(ch.isdigit() for ch in ln):
                    continue
                u = ln.upper()
                # Ignorar rótulos/terminais
                if re.search(r"TERMINAL|TECON|LOADING|PORT OF|FINAL PLACE|REMARKS", u):
                    continue
                # Aceitar somente palavras/letras e espaços
                if re.fullmatch(r"[A-Za-z][A-Za-z\s\-'&/]*", ln.strip()):
                    # Filtros de qualidade: evitar siglas/linhas muito longas/ruído
                    words = [w for w in u.split() if w]
                    if len(words) > 2:
                        continue
                    if len(u.replace(" ", "")) < 4:
                        continue
                    if not re.search(r"[AEIOU]", u):
                        continue
                    if any(bad in words for bad in ["EMPRESA","ZONA","RURAL","LA","B"]):
                        continue
                    # Excluir se igual a POL ou ao Terminal
                    if u == pol_up or u == ptc_up:
                        continue
                    # Evitar escolher igual ao POD se já conhecido
                    if pod_up and u == pod_up:
                        continue
                    candidates.append(u)
            if candidates:
                # Usa o primeiro candidato válido encontrado (ex.: 'SANTOS')
                data["transhipment_port"] = candidates[0].title()

    # 8c) Fallback: procurar candidato logo APÓS o rótulo 'Transhipment:' em uma janela ampla (preferência)
    if not data.get("transhipment_port"):
        anchor = re.search(r"Transhipment\s*:\s*\n?", text_content, re.IGNORECASE)
        if anchor:
            tail = text_content[anchor.end():]
            lines = [ln.strip() for ln in tail.split("\n") if ln.strip()]
            pol_up = (data.get("pol") or "").upper()
            ptc_up = (data.get("port_terminal_city") or "").upper()
            pod_up = (data.get("pod") or "").upper()
            candidates = []
            for ln in lines[:120]:
                u = ln.upper()
                if ":" in ln or any(ch.isdigit() for ch in ln):
                    continue
                if re.search(r"TERMINAL|TECON|LOADING|PORT OF|FINAL PLACE|REMARKS|CUT-?OFF|DATE/Time", u, re.IGNORECASE):
                    continue
                if not re.fullmatch(r"[A-Za-z][A-Za-z\s\-'&/]*", ln.strip()):
                    continue
                # Filtros de qualidade
                words = [w for w in u.split() if w]
                if len(words) > 2:
                    continue
                if len(u.replace(" ", "")) < 4:
                    continue
                if not re.search(r"[AEIOU]", u):
                    continue
                if any(bad in words for bad in ["EMPRESA","ZONA","RURAL","LA","B","APARECIDA"]):
                    continue
                if u in (pol_up, ptc_up, pod_up):
                    continue
                candidates.append(u)
            if candidates:
                data["transhipment_port"] = candidates[0].title()

    # 8d) Fallback: procurar candidato imediatamente antes do rótulo 'Transhipment:' olhando algumas linhas acima (menos preferido)
    if not data.get("transhipment_port"):
        anchor = re.search(r"Transhipment\s*:", text_content, re.IGNORECASE)
        if anchor:
            prev_lines = text_content[:anchor.start()].split("\n")
            window = [ln.strip() for ln in prev_lines[-80:] if ln.strip()]
            pol_up = (data.get("pol") or "").upper()
            ptc_up = (data.get("port_terminal_city") or "").upper()
            pod_up = (data.get("pod") or "").upper()
            for ln in reversed(window):
                u = ln.upper()
                if ":" in ln or any(ch.isdigit() for ch in ln):
                    continue
                if re.search(r"TERMINAL|TECON|LOADING|PORT OF|FINAL PLACE|REMARKS|CUT-?OFF|DATE/Time", u, re.IGNORECASE):
                    continue
                if not re.fullmatch(r"[A-Za-z][A-Za-z\s\-'&/]*", ln.strip()):
                    continue
                # Rejeitar candidatos muito curtos/siglas e sem vogais
                words = [w for w in u.split() if w]
                if len(words) > 2:
                    continue
                if len(u.replace(" ", "")) < 4:
                    continue
                if not re.search(r"[AEIOU]", u):
                    continue
                if any(bad in words for bad in ["EMPRESA","ZONA","RURAL","LA","B","APARECIDA"]):
                    continue
                if u in (pol_up, ptc_up, pod_up):
                    continue
                # encontrado candidato (ex.: SANTOS)
                data["transhipment_port"] = u.title()
                break

    # 8e) Fallback final: hubs conhecidos aparecendo após 'Transhipment:'
    if not data.get("transhipment_port"):
        anchor = re.search(r"Transhipment\s*:\s*\n?", text_content, re.IGNORECASE)
        if anchor:
            tail_up = text_content[anchor.end():].upper()
            pol_up = (data.get("pol") or "").upper()
            pod_up = (data.get("pod") or "").upper()
            ptc_up = (data.get("port_terminal_city") or "").upper()
            known_hubs = [
                "COLOMBO","SANTOS","SINGAPORE","TANGER","TANGIER","SALALAH",
                "PORT KLANG","HONG KONG","BUSAN","JEBEL ALI","VALENCIA","ALGECIRAS",
                "DUBAI","KOPER","GIOIA TAURO","PIRAEUS","BARCELONA","ROTTERDAM"
            ]
            for hub in known_hubs:
                if re.search(r"\b"+re.escape(hub)+r"\b", tail_up):
                    if hub not in (pol_up, pod_up, ptc_up):
                        data["transhipment_port"] = hub.title()
                        break

    # 9) Deadlines: DocCut e PortCut
    for pat in [r"SI/?eSI CUT-OFF\s*:?\s*([^\n]+)", r"DOC(?:UMENT)? CUT-?OFF\s*:?\s*([^\n]+)"]:
        m = re.search(pat, text_content, re.IGNORECASE)
        if m:
            dc = extract_date(m.group(1))
            if dc:
                data["doc_cut"] = dc
                break

    for pat in [r"CY CUT-?OFF\s*:?\s*([^\n]+)", r"Closing Date Yard\s*:?\s*([^\n]+)"]:
        m = re.search(pat, text_content, re.IGNORECASE)
        if m:
            pc = extract_date(m.group(1))
            if pc:
                data["port_cut"] = pc
                break

    # 9) ETD/ETA suportando dd-MON-YYYY HH:MM em mesma linha ou na linha seguinte
    # ETD (primeira ocorrência)
    etd_matches = re.findall(r"ETD\s*:?\s*([0-9]{2}[-/][A-Za-z]{3}[-/][0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?|[0-9]{2}/[0-9]{2}/[0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?)", text_content, re.IGNORECASE | re.MULTILINE)
    if not etd_matches:
        m_lbl = re.search(r"ETD\s*:\s*\n\s*([^\n]+)", text_content, re.IGNORECASE)
        if m_lbl:
            etd_matches = [m_lbl.group(1).strip()]
    if etd_matches:
        data["etd"] = etd_matches[0].strip()

    # ETA (última ocorrência)
    eta_matches = re.findall(r"ETA\s*:?\s*([0-9]{2}[-/][A-Za-z]{3}[-/][0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?|[0-9]{2}/[0-9]{2}/[0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?)", text_content, re.IGNORECASE | re.MULTILINE)
    if not eta_matches:
        m_lbl = re.finditer(r"ETA\s*:\s*\n\s*([^\n]+)", text_content, re.IGNORECASE)
        eta_matches = [m.group(1).strip() for m in m_lbl]
    if eta_matches:
        data["eta"] = eta_matches[-1].strip()

    # 10) Booking/Print date (CMA usa frequentemente a palavra 'Run' com data curta)
    # Preferir linha com "Run <dd-MON-yy HH:MM>"
    m = re.search(r"\bRun\b\s*[:\-]?\s*([0-9]{2}-[A-Za-z]{3}-[0-9]{2,4}\s+[0-9]{2}:[0-9]{2})", text_content, re.IGNORECASE)
    if not m:
        # Suporta quebra de linha após 'Run:'
        m = re.search(r"\bRun\b\s*[:\-]?\s*\n\s*([0-9]{2}-[A-Za-z]{3}-[0-9]{2,4}\s+[0-9]{2}:[0-9]{2})", text_content, re.IGNORECASE)
    if not m:
        # Fallback: rótulo DATE comum
        m = re.search(r"\bDATE\s*:?\s*(\d{2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4})", text_content, re.IGNORECASE)
    if m:
        data["pdf_print_date"] = m.group(1).strip()

    # Detectar tipo de documento
    for keyword, label in [("BOOKING CONFIRMATION", "BOOKING CONFIRMATION"), ("BOOKING AMENDMENT", "BOOKING AMENDMENT"), ("BOOKING CANCELLATION", "BOOKING CANCELLATION")]:
        if keyword in text_content.upper():
            data["document_type"] = label
            break

    # Limpar campos de porto para formato consistente
    if "pol" in data:
        data["pol"] = clean_port_field(data["pol"]) or data["pol"]
    if "pod" in data:
        data["pod"] = clean_port_field(data["pod"]) or data["pod"]

    return data


def extract_pil_data(text_content: str):
    """Extrai dados específicos para PDFs da PIL (Pacific International Lines)."""
    data = {}

    # Helpers
    def clean_city(value: str):
        if not value:
            return None
        s = str(value)
        # Corta conteúdo dentro de parênteses e após vírgula (país/terminal)
        s = s.split("(")[0]
        s = s.split(",")[0]
        s = s.replace("  ", " ")
        return s.strip().title() if s.strip() else None

    # Booking reference
    m_bkg = re.search(r"\bBooking\s+No\s*:\s*([\w-]+)", text_content, re.IGNORECASE)
    if m_bkg:
        data["booking_reference"] = m_bkg.group(1).strip()

    # Quantity a partir de "Equipment Type/Q'ty : 40HC-20" (pode haver múltiplos tipos)
    qty_total = 0
    for m in re.findall(r"Equipment\s+Type/Q[']'`]?ty\s*:\s*([^\n]+)", text_content, re.IGNORECASE):
        # Capturar todos os números após hífen (ex.: 40HC-20 -> 20)
        hyphen_qty = re.findall(r"[A-Za-z0-9]+-(\d+)\b", m)
        qty_total += sum(int(q) for q in hyphen_qty)
    if qty_total > 0:
        data["quantity"] = str(qty_total)

    # PDF Print Date (cabeçalho do documento), ex.: "16 JUL 25 10:37"
    # Procurar a primeira ocorrência de DD MMM YY HH:MM em qualquer lugar do texto
    m_pdf_dt = re.search(r"\b(\d{1,2}\s+[A-Z]{3}\s+\d{2}\s+\d{2}:\d{2})\b", text_content)
    if m_pdf_dt:
        # Normaliza mês para formato Title (Jul) para facilitar parsing posterior
        raw_dt = m_pdf_dt.group(1)
        try:
            parts = raw_dt.split()
            if len(parts) >= 4:
                # parts: [DD, MMM, YY, HH:MM]
                parts[1] = parts[1].title()
                data["pdf_print_date"] = " ".join(parts[:4])
            else:
                data["pdf_print_date"] = raw_dt
        except Exception:
            data["pdf_print_date"] = raw_dt

    # Vessel/Voyage (Trunk Vessel line)
    m_vsl = re.search(r"\bTrunk\s+Vessel\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
    if m_vsl:
        tail = m_vsl.group(1).strip()
        # Ex.: "CMA CGM BELEM 0BDLNE1MA ETA/ETD : 09Aug25/11Aug25"
        # Separar antes de ETA/ETD
        tail = re.split(r"ETA/ETD\s*:\s*", tail, maxsplit=1)[0].strip()
        # Tentar separar voyage: último token alfanumérico
        parts = tail.split()
        if len(parts) >= 2 and re.search(r"[A-Za-z]\d|\d[A-Za-z]", parts[-1]):
            data["vessel_name"] = " ".join(parts[:-1])
            data["voyage"] = parts[-1]
        else:
            data["vessel_name"] = tail

    # POL
    m_pol = re.search(r"\bPort\s+of\s+Loading\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
    if m_pol:
        pol = clean_city(m_pol.group(1))
        if pol:
            data["pol"] = pol

    # POD
    m_pod = re.search(r"\bPort\s+of\s+Discharging\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
    if m_pod:
        pod_raw = m_pod.group(1).strip()
        pod = clean_city(pod_raw)
        if pod:
            data["pod"] = pod

    # Port Terminal City (linha iniciando com "Terminal ...")
    m_term = re.search(r"^\s*Terminal\s+([^\n]+)", text_content, re.IGNORECASE | re.MULTILINE)
    if m_term:
        term = re.sub(r"\s+", " ", m_term.group(1)).strip()
        data["port_terminal_city"] = term

    # Port Terminal City (prioritário): "Full Return CY : SANTOS BRASIL S/A"
    # Cortar antes de próximos rótulos na mesma linha (ex.: "Full Return Date :")
    m_full_return = re.search(r"\bFull\s+Return\s+CY\s*:\s*([^\n]+?)(?:\s+Full\s+Return\s+Date\s*:|$)", text_content, re.IGNORECASE)
    if m_full_return:
        full_return = re.sub(r"\s+", " ", m_full_return.group(1)).strip()
        if full_return:
            data["port_terminal_city"] = full_return

    # Transhipment Port (T/S Port dentro do Ocean Route Type)
    m_ts = re.search(r"\bT/S\s*Port\s*:\s*([^)]+)\)", text_content, re.IGNORECASE)
    if m_ts:
        data["transhipment_port"] = clean_city(m_ts.group(1))

    # ETA/ETD (Trunk Vessel): capturar ambos especificamente da linha de Trunk Vessel
    # Ex.: "Trunk Vessel : ... ETA/ETD : 26Aug25/28Aug25"
    m_tv = re.search(r"Trunk\s+Vessel\s*:\s*[^\n]*?ETA/ETD\s*:\s*([0-9A-Za-z]{5,})/([0-9A-Za-z]{5,})", text_content, re.IGNORECASE)
    if m_tv:
        data["eta"] = m_tv.group(1).strip()
        data["etd"] = m_tv.group(2).strip()
    else:
        # Fallback: qualquer ETA/ETD
        m_et = re.search(r"ETA/ETD\s*:\s*([0-9A-Za-z]{5,})/([0-9A-Za-z]{5,})", text_content, re.IGNORECASE)
        if m_et:
            data["eta"] = m_et.group(1).strip()
            data["etd"] = m_et.group(2).strip()

    # ETA do Port of Discharging (POC/POD) se existir (buscar após o rótulo, janela limitada)
    m_pod_label = re.search(r"Port\s+of\s+Discharg\w*\s*:\s*", text_content, re.IGNORECASE)
    if m_pod_label:
        start = m_pod_label.end()
        window = text_content[start:start+1500]
        m_pod_eta = re.search(r"ETA\s*:\s*([0-9A-Za-z]{5,})", window, re.IGNORECASE)
        if m_pod_eta and "eta" not in data:
            data["eta"] = m_pod_eta.group(1).strip()

    # Sobrescrever ETA com a ETA do Place of Delivery (prioridade máxima)
    m_podl_label = re.search(r"Place\s+of\s+Delivery\s*:\s*", text_content, re.IGNORECASE)
    if m_podl_label:
        start = m_podl_label.end()
        window = text_content[start:start+2000]
        m_podl_eta = re.search(r"ETA\s*:\s*([0-9A-Za-z]{5,})", window, re.IGNORECASE)
        if m_podl_eta:
            data["eta"] = m_podl_eta.group(1).strip()

    return data

def extract_cosco_data(text_content):
    """Extrai dados específicos para PDFs da COSCO"""
    data = {}
    
    # Usar padrões específicos da COSCO
    patterns = CARRIER_PATTERNS["GENERIC"]  # Usar padrões genéricos por enquanto
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    
    return data

def extract_evergreen_data(text_content):
    """Extrai dados específicos para PDFs da Evergreen"""
    data = {}
    
    # Usar padrões específicos da Evergreen
    patterns = CARRIER_PATTERNS["GENERIC"]  # Usar padrões genéricos por enquanto
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    
    return data

def extract_generic_data(text_content):
    """Extrai dados usando padrões genéricos para outros armadores"""
    data = {}
    
    # Usar padrões genéricos
    patterns = CARRIER_PATTERNS["GENERIC"]
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    
    return data

def extract_oocl_data(text_content: str):
    """Extrai dados específicos para PDFs da OOCL (Orient Overseas Container Line)."""
    data = {}
    
    # PDF Print Date - "DATE: 01 Jul 2025 22:00"
    m_date = re.search(r"DATE:\s*(\d{1,2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})", text_content, re.IGNORECASE)
    if m_date:
        data["pdf_print_date"] = m_date.group(1).strip()
    
    # Booking Reference - "BOOKING NUMBER: 2160389150"
    m_booking = re.search(r"BOOKING\s+NUMBER:\s*(\w+)", text_content, re.IGNORECASE)
    if m_booking:
        data["booking_reference"] = m_booking.group(1).strip()
    
    # Quantity - "TOTAL BOOKING CONTAINER QTY: 20 X 40' Hi-Cube Container"
    m_qty = re.search(r"TOTAL\s+BOOKING\s+CONTAINER\s+QTY[:\s]*(\d+)", text_content, re.IGNORECASE)
    if m_qty:
        data["quantity"] = m_qty.group(1).strip()
    
    # Vessel Name e Voyage - "INTENDED VESSEL/VOYAGE: KOTA EBONY 002 E"
    # Padrão mais flexível para capturar nome do navio e voyage
    m_vessel = re.search(r"INTENDED\s+VESSEL/VOYAGE:\s*([A-Z][A-Z\s]+?)\s+(\d{3}\s*[A-Z])", text_content, re.IGNORECASE)
    if m_vessel:
        vessel_name = m_vessel.group(1).strip()
        voyage = m_vessel.group(2).strip()
        
        # Limpar o nome do navio removendo espaços extras
        vessel_name = re.sub(r'\s+', ' ', vessel_name).strip()
        data["vessel_name"] = vessel_name
        data["voyage"] = voyage
    
    # Flag - "VESSEL FLAG: Singapore"
    m_flag = re.search(r"VESSEL\s+FLAG:\s*([^\n]+)", text_content, re.IGNORECASE)
    if m_flag:
        data["flag"] = m_flag.group(1).strip()
    
    # Carrier/Armador - "FROM: COSCO Shipping Lines (Brazil) S.A. as agent for OOCL (USA) Inc"
    m_carrier = re.search(r"FROM:\s*([^(]+)", text_content, re.IGNORECASE)
    if m_carrier:
        carrier = m_carrier.group(1).strip()
        # Extrair apenas o nome principal da empresa
        if "COSCO" in carrier.upper():
            data["carrier"] = "COSCO"
        elif "OOCL" in carrier.upper():
            data["carrier"] = "OOCL"
        else:
            data["carrier"] = carrier
    
    # Port of Loading (POL) - "PORT OF LOADING: Porto de Santos / Santos Brazil"
    m_pol = re.search(r"PORT\s+OF\s+LOADING:\s*([^/\n]+)", text_content, re.IGNORECASE)
    if m_pol:
        pol = m_pol.group(1).strip()
        data["pol"] = pol
    
    # Port of Discharge (POD) - "PORT OF DISCHARGE: Ho Chi Minh (Cat Lai) / Cat Lai Terminal"
    m_pod = re.search(r"PORT\s+OF\s+DISCHARGE:\s*([^/\n]+)", text_content, re.IGNORECASE)
    if m_pod:
        pod = m_pod.group(1).strip()
        data["pod"] = pod
    
    # Transhipment Port - "TRANSSHIPMENT PORT: Singapore / PSA Corporation Limited"
    m_tranship = re.search(r"TRANSSHIPMENT\s+PORT:\s*([^/\n]+)", text_content, re.IGNORECASE)
    if m_tranship:
        tranship = m_tranship.group(1).strip()
        data["transhipment_port"] = tranship
    
    # ETD - "INTENDED VESSEL/VOYAGE: KOTA EBONY 002 E ETD: 04 Aug 2025"
    m_etd = re.search(r"INTENDED\s+VESSEL/VOYAGE:.*?ETD:\s*(\d{1,2}\s+\w{3}\s+\d{4})", text_content, re.IGNORECASE | re.DOTALL)
    if m_etd:
        data["etd"] = m_etd.group(1).strip()
    
    # ETA - "FINAL DESTINATION: Ho Chi Minh,Vietnam ETA: 06 Sep 2025"
    m_eta = re.search(r"FINAL\s+DESTINATION:.*?ETA:\s*(\d{1,2}\s+\w{3}\s+\d{4})", text_content, re.IGNORECASE | re.DOTALL)
    if m_eta:
        data["eta"] = m_eta.group(1).strip()
    
    return data

def clean_port_field(value):
    """Limpa campo de porto para formato 'Cidade,Estado,País'"""
    if not value:
        return None
    # remover códigos ou complementos entre parênteses
    no_paren = re.sub(r"\s*\([^)]*\)", "", value)
    # quebrar por vírgula e pegar no máximo 3 partes
    parts = [p.strip() for p in no_paren.split(",") if p.strip()]
    if not parts:
        return None
    return ",".join(parts[:3])

def standardize_terminal_name(terminal_name):
    """
    Padroniza o nome do terminal para o formato usado na ferramenta Ellox
    
    Args:
        terminal_name (str): Nome do terminal extraído do PDF
        
    Returns:
        str: Nome padronizado do terminal
    """
    if not terminal_name:
        return ""
    
    # Mapeamento de terminais para nomes padrão da Ellox
    terminal_mapping = {
        # Santos
        "BRASIL TERMINAL PORTUARIO SA": "BTP",
        "BTP": "BTP",
        "BRASIL TERMINAL PORTUARIO": "BTP",
        "BRASIL TERMINAL": "BTP",
        
        "SANTOS BRASIL S/A": "Santos Brasil",
        "SANTOS BRASIL": "Santos Brasil",
        "SANTOS BRASIL SA": "Santos Brasil",
        
        "DP WORLD SANTOS": "DPW",
        "DPW": "DPW",
        "DP WORLD": "DPW",
        
        "ECOPORTO": "Ecoporto",
        
        # Rio de Janeiro
        "ICTSI RIO BRASIL": "ICTSI Rio Brasil",
        "ICTSI RIO": "ICTSI Rio Brasil",
        
        "MULTI-RIO": "Multi-Rio",
        "MULTI RIO": "Multi-Rio",
        
        # Paranaguá
        "PARANAGUA": "Paranagua",
        "PARANAGUÁ": "Paranagua",
        
        # Itajaí
        "ITAJAÍ": "Itajai",
        "ITAJAI": "Itajai",
        
        # Itapoá
        "ITAPOÁ": "Itapoa",
        "ITAPOA": "Itapoa",
        
        # Imbituba
        "IMBITUBA": "Imbituba",
        
        # Navegantes
        "NAVEGANTES": "Navegantes",
        
        # Rio Grande
        "RIO GRANDE": "Rio Grande",
        
        # Pecem
        "PECEM": "Pecem",
        "PECÉM": "Pecem",
        
        # Suape
        "SUAPE": "Suape",
        
        # Sepetiba
        "SEPETIBA": "Sepetiba",
        
        # Manaus
        "MANAUS CHIBATÃO": "Manaus Chibatão",
        "CHIBATÃO": "Manaus Chibatão",
        
        "MANAUS SUPER TERMINAIS": "Manaus Super Terminais",
        "SUPER TERMINAIS": "Manaus Super Terminais",
        
        # Salvador
        "TECON SALVADOR": "Tecon Salvador",
        "SALVADOR": "Tecon Salvador",
        
        # Vila do Conde
        "VILA DO CONDE": "Vila do Conde",
        
        # TVV
        "TVV": "TVV",
    }
    
    # Normalizar entrada (remover espaços extras, converter para maiúscula)
    normalized = re.sub(r'\s+', ' ', terminal_name.strip()).upper()
    
    # Buscar correspondência exata
    if normalized in terminal_mapping:
        return terminal_mapping[normalized]
    
    # Buscar correspondência parcial
    for key, value in terminal_mapping.items():
        if key in normalized or normalized in key:
            return value
    
    # Se não encontrar correspondência, retornar o nome original limpo
    return re.sub(r'\s+', ' ', terminal_name.strip())


def collect_voyage_monitoring_data(vessel_name, port_terminal_city, voyage_code=""):
    """
    Coleta dados de monitoramento da viagem usando a API Ellox Terminal.
    Primeiro solicita o monitoramento, depois visualiza os dados.
    
    Args:
        vessel_name: Nome do navio
        port_terminal_city: Nome do terminal/cidade
        voyage_code: Código da viagem (opcional)
    """
    try:
        import requests
        import json
        import pandas as pd
        from database import get_database_connection, upsert_terminal_monitorings_from_dataframe
        from sqlalchemy import text
        
        # Função para autenticar na API Ellox
        def authenticate_ellox():
            EMAIL = "diego_moura@cargill.com"
            SENHA = "Cargill@25"
            
            url_auth = "https://apidtz.comexia.digital/api/auth"
            payload_auth = {"email": EMAIL, "senha": SENHA}
            
            resp_auth = requests.post(
                url_auth, 
                json=payload_auth, 
                headers={"Content-Type": "application/json"}
            )
            
            if resp_auth.status_code != 200:
                return None
            
            data_auth = resp_auth.json()
            token = data_auth.get("access_token") or data_auth.get("token")
            if not token:
                raise ValueError("Token de autenticação ausente na resposta")
            return token
        
        # Função para solicitar monitoramento
        def solicitar_monitoramento(token, cnpj_terminal, vessel_name, voyage_code):
            url = "https://apidtz.comexia.digital/api/monitor/navio"
            payload = {
                "cnpj": "60.498.706/0001-57",  # CNPJ Cargill
                "lista": [
                    {
                        "cnpj_terminal": cnpj_terminal,
                        "nome_navio": vessel_name,
                        "viagem_navio": voyage_code or ""
                    }
                ]
            }
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload)
            
            if resp.status_code >= 400:
                body_text = (resp.text or "").lower()
                if "already exist" in body_text or "already tracked" in body_text:
                    return "already_exists"
                return None
            return "ok"
        
        # Função para visualizar monitoramentos
        def visualizar_monitoramentos(token, cnpj_terminal, vessel_name, voyage_code):
            url = "https://apidtz.comexia.digital/api/terminalmonitorings"
            payload = {
                "cnpj": "60.498.706/0001-57",  # CNPJ Cargill
                "cnpj_terminal": cnpj_terminal,
                "nome_navio": vessel_name,
                "viagem_navio": voyage_code or ""
            }
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resp = requests.post(url, headers=headers, json=payload)
            
            if resp.status_code >= 400:
                return pd.DataFrame()
            
            data = resp.json() if resp.content else []
            return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
        
        # Mapeamento de terminais para CNPJs (expandido)
        terminal_cnpj_map = {
            "BTP": "04.887.625/0001-78",
            "BRASIL TERMINAL PORTUARIO": "04.887.625/0001-78", 
            "BRASIL TERMINAL PORTUARIO SA": "04.887.625/0001-78",
            "BRASIL TERMINAL PORTUARIO S/A": "04.887.625/0001-78",
            "SANTOS BRASIL": "02.762.121/0001-04",  # Atualizado conforme teste.ipynb
            "SANTOS BRASIL S.A.": "02.762.121/0001-04",
            "SANTOS BRASIL SA": "02.762.121/0001-04",
            "TECON SANTOS": "03.518.221/0001-06",
            "COSCO": "02.762.121/0001-04"  # Default: Santos Brasil (conforme teste)
        }
        
        # Buscar CNPJ do terminal
        cnpj_terminal = "02.762.121/0001-04"  # Default: Santos Brasil (conforme teste.ipynb)
        
        # Normalizar nome do terminal para busca
        terminal_normalized = (port_terminal_city or "").upper().strip()
        
        for terminal_key, cnpj in terminal_cnpj_map.items():
            if terminal_key in terminal_normalized:
                cnpj_terminal = cnpj
                break

        # Caso especial: Embraport (DP World Santos)
        # Alguns PDFs trazem "Embraport Empresa Brasileira"; na API é reconhecido como DPW/DP WORLD
        if "EMBRAPORT" in terminal_normalized or "EMPRESA BRASILEIRA" in terminal_normalized:
            try:
                conn = get_database_connection()
                query = text("""
                    SELECT CNPJ, NOME
                    FROM F_ELLOX_TERMINALS
                    WHERE UPPER(NOME) LIKE '%DPW%'
                       OR UPPER(NOME) LIKE '%DP WORLD%'
                       OR UPPER(NOME) LIKE '%EMBRAPORT%'
                    FETCH FIRST 1 ROWS ONLY
                """)
                res = conn.execute(query).mappings().fetchone()
                conn.close()
                if res and res.get("cnpj"):
                    cnpj_terminal = res["cnpj"]
            except Exception:
                # mantém fallback se não encontrar
                pass
        
        # Buscar na base local se não encontrou
        if cnpj_terminal == "02.762.121/0001-04" and "SANTOS BRASIL" not in terminal_normalized:
            try:
                conn = get_database_connection()
                query = text("""
                    SELECT DISTINCT CNPJ, NOME
                    FROM F_ELLOX_TERMINALS
                    WHERE UPPER(NOME) LIKE UPPER(:terminal_name)
                    FETCH FIRST 1 ROWS ONLY
                """)
                result = conn.execute(query, {
                    "terminal_name": f"%{port_terminal_city}%"
                }).mappings().fetchone()
                
                if result:
                    cnpj_terminal = result["cnpj"]
                
                conn.close()
            except:
                pass  # Usar default
        
        # 1) Autenticar na API
        token = authenticate_ellox()
        if not token:
            st.warning("⚠️ Erro na autenticação com API Ellox")
            return
        
        # 2) Solicitar monitoramento (mesmo se já existir)
        status_solicitacao = solicitar_monitoramento(token, cnpj_terminal, vessel_name, voyage_code)
        
        if status_solicitacao in ("ok", "already_exists"):
            if status_solicitacao == "already_exists":
                st.info(f"ℹ️ Navio **{vessel_name}** já está sendo monitorado. Coletando dados...")
            else:
                st.info(f"✅ Monitoramento solicitado para **{vessel_name}**")
            
            # 3) Visualizar monitoramentos
            df_monitoring = visualizar_monitoramentos(token, cnpj_terminal, vessel_name, voyage_code)
            
            if not df_monitoring.empty:
                # Salvar no Oracle (F_ELLOX_TERMINAL_MONITORINGS)
                try:
                    processed_count = upsert_terminal_monitorings_from_dataframe(df_monitoring)
                    if processed_count > 0:
                        st.success(f"✅ {processed_count} registros de monitoramento coletados via API Ellox!")
                        st.info(f"🚢 Navio: **{vessel_name}** | 🏗️ Terminal: **{cnpj_terminal}**")
                    else:
                        st.info("ℹ️ Nenhum novo registro de monitoramento encontrado (dados já existem)")
                except Exception as e:
                    st.warning(f"⚠️ Erro ao salvar monitoramentos no Oracle: {str(e)}")
            else:
                st.info(f"ℹ️ Nenhum dado de monitoramento encontrado para **{vessel_name}** no terminal {cnpj_terminal}")
                st.info("💡 O navio pode não estar na base Ellox ainda ou usar nome diferente na agência")
        else:
            st.warning("⚠️ Não foi possível solicitar o monitoramento. Verifique os dados do navio.")
            
    except Exception as e:
        # Log do erro para debug, mas não quebra o fluxo principal
        st.warning(f"⚠️ Erro na coleta de monitoramento: {str(e)}")
        import traceback
        print(f"collect_voyage_monitoring_data error: {traceback.format_exc()}")

@st.cache_data(ttl=300)  # Cache com TTL de 5 minutos para permitir atualizações
def load_ships_from_database():
    """
    Carrega lista de navios únicos da tabela F_ELLOX_SHIPS.
    Como um navio pode estar em múltiplos terminais, retorna apenas uma entrada por navio.
    
    Returns:
        list: Lista de tuplas (nome, carrier) dos navios únicos
    """
    try:
        conn = get_database_connection()
        # Buscar navios únicos (um registro por nome de navio)
        query = text("""
            SELECT DISTINCT NOME, CARRIER 
            FROM F_ELLOX_SHIPS 
            ORDER BY NOME
        """)
        result = conn.execute(query).fetchall()
        conn.close()
        
        ships = [(row[0], row[1]) for row in result]
        return ships
    except Exception as e:
        st.error(f"Erro ao carregar navios: {str(e)}")
        return []

@st.cache_data(ttl=300)  # Cache com TTL de 5 minutos para permitir atualizações
def load_terminals_from_database():
    """
    Carrega lista de terminais da tabela F_ELLOX_TERMINALS.
    
    Returns:
        list: Lista de nomes dos terminais
    """
    try:
        conn = get_database_connection()
        query = text("SELECT NOME FROM F_ELLOX_TERMINALS ORDER BY NOME")
        result = conn.execute(query).fetchall()
        conn.close()
        
        terminals = [row[0] for row in result]
        return terminals
    except Exception as e:
        st.error(f"Erro ao carregar terminais: {str(e)}")
        return []


def normalize_extracted_data(extracted_data):
    """
    Normaliza e valida os dados extraídos.
    
    Args:
        extracted_data (dict): Dados extraídos brutos
    
    Returns:
        dict: Dados normalizados
    """
    normalized = {}
    
    # Normaliza booking reference
    if "booking_reference" in extracted_data:
        booking_ref = extracted_data["booking_reference"]
        # Remove espaços e caracteres especiais
        booking_ref = re.sub(r'[^\w]', '', booking_ref).upper()
        normalized["booking_reference"] = booking_ref
    
    # Normaliza vessel name
    if "vessel_name" in extracted_data:
        vessel = extracted_data["vessel_name"]
        # Remove prefixos comuns e normaliza
        vessel = re.sub(r'^(M/V|MV|MS)\s+', '', vessel, flags=re.IGNORECASE)
        vessel_clean = vessel.strip()
        # Se o nome original vier todo em maiúsculas (padrão OOCL), manter
        if vessel_clean.isupper():
            normalized["vessel_name"] = vessel_clean
        else:
            normalized["vessel_name"] = vessel_clean.title()
    
    # Normaliza voyage removendo espaços internos (ex.: "002 E" -> "002E")
    if "voyage" in extracted_data:
        voyage = re.sub(r"\s+", "", str(extracted_data["voyage"]))
        normalized["voyage"] = voyage.upper()
    
    # Normaliza quantity
    if "quantity" in extracted_data:
        try:
            q = int(str(extracted_data["quantity"]).strip())
            if q < 1:
                q = 1
            normalized["quantity"] = q
        except Exception:
            normalized["quantity"] = 1  # Default
    
    # Normaliza flag
    if "flag" in extracted_data:
        normalized["flag"] = extracted_data["flag"].strip().title()
    
    # Normaliza carrier
    if "carrier" in extracted_data:
        normalized["carrier"] = extracted_data["carrier"].strip().upper()
    
    # Normaliza portos
    for port_field in ["pol", "pod", "transhipment_port", "port_terminal_city"]:
        if port_field in extracted_data:
            port = extracted_data[port_field]
            # Remove conteúdo entre parênteses e após vírgulas
            port = re.sub(r"\s*\([^)]*\)", "", port)
            port = re.sub(r",.*", "", port)
            # Normaliza espaços
            port = re.sub(r"\s+", " ", port).strip()
            
            # Para port_terminal_city, aplicar padronização com Ellox
            if port_field == "port_terminal_city":
                normalized[port_field] = standardize_terminal_name(port)
            else:
                normalized[port_field] = port.title()
    
    # Normaliza datas
    for date_field in ["etd", "eta", "pdf_print_date"]:
        if date_field in extracted_data:
            date_str = extracted_data[date_field]
            try:
                # Tenta diferentes formatos de data
                for fmt in [
                    "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y",
                    "%d/%m/%y", "%d-%m-%y",
                    "%d-%b-%Y", "%d-%b-%Y %H:%M", "%d %b %Y",
                    "%d%b%y", "%d%b%Y"
                ]:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        normalized[date_field] = date_obj.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            except Exception:
                normalized[date_field] = date_str  # Mantém original se não conseguir converter
    
    # Normaliza print_date (datetime com hora)
    if "print_date" in extracted_data:
        raw = extracted_data["print_date"] or ""
        cleaned = raw.replace(" UTC", "").replace(" UT", "").strip()
        parsed = None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%b-%y %H:%M", "%d-%b-%Y %H:%M"]:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                break
            except Exception:
                continue
        if parsed:
            normalized["print_date"] = parsed.strftime("%Y-%m-%d %H:%M:%S")
        else:
            normalized["print_date"] = cleaned

    # Normaliza pdf_print_date (datetime com hora) — alinhar com padrão da CMA (YYYY-MM-DD HH:MM:SS)
    if "pdf_print_date" in extracted_data:
        raw = extracted_data["pdf_print_date"] or ""
        # Remover sufixos de timezone/eventuais rótulos cortados como "PT", "UTC", "UT"
        cleaned = (
            raw.replace(" UTC", "").replace(" UT", "").replace(" PT", "").strip()
        )
        parsed = None
        # Suportar diversos formatos, incluindo segundos
        parse_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%b-%y %H:%M:%S",
            "%d-%b-%y %H:%M",
            "%d-%b-%Y %H:%M:%S",
            "%d-%b-%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d %b %Y %H:%M",
            "%d %b %y %H:%M",
        ]
        for fmt in parse_formats:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                # Corrigir século quando usar %y
                if "%y" in fmt and parsed.year < 1930:
                    parsed = parsed.replace(year=2000 + parsed.year % 100)
                break
            except Exception:
                continue
        if parsed:
            normalized["pdf_print_date"] = parsed.strftime("%Y-%m-%d %H:%M:%S")
        else:
            normalized["pdf_print_date"] = cleaned
    
    return normalized

def process_pdf_booking(pdf_content, farol_reference):
    """
    Processa um PDF de booking e extrai os dados relevantes.
    
    Args:
        pdf_content: Conteúdo do PDF (bytes)
        farol_reference (str): Referência do Farol
    
    Returns:
        dict: Dados extraídos e processados
    """
    try:
        if not PDF_AVAILABLE:
            st.error("⚠️ PyPDF2 não está disponível para processamento de PDF")
            return None
        
        # Extrai texto do PDF
        text = extract_text_from_pdf(pdf_content)
        if not text:
            st.error("❌ Não foi possível extrair texto do PDF")
            return None
        
        # Identifica o carrier
        carrier = identify_carrier(text)
        
    except Exception as e:
        st.error(f"❌ Erro durante o processamento inicial: {str(e)}")
        return None
    
    # Extrai dados usando função específica do carrier
    if carrier == "MAERSK":
        extracted_data = extract_maersk_data(text)
    elif carrier == "HAPAG-LLOYD":
        extracted_data = extract_hapag_lloyd_data(text)
    elif carrier == "MSC":
        extracted_data = extract_msc_data(text)
    elif carrier == "CMA CGM":
        extracted_data = extract_cma_cgm_data(text)
    elif carrier == "COSCO":
        extracted_data = extract_cosco_data(text)
    elif carrier == "EVERGREEN":
        extracted_data = extract_evergreen_data(text)
    elif carrier == "OOCL":
        extracted_data = extract_oocl_data(text)
    elif carrier == "PIL":
        extracted_data = extract_pil_data(text)
    else:
        # Usar padrões genéricos para outros armadores
        patterns = CARRIER_PATTERNS.get(carrier, CARRIER_PATTERNS["GENERIC"])
        extracted_data = extract_data_with_patterns(text, patterns)
    
    try:
        # Normaliza os dados
        normalized_data = normalize_extracted_data(extracted_data)
        
        # Prepara dados para exibição/validação
        processed_data = {
            "farol_reference": farol_reference,
            "carrier": carrier,
            "booking_reference": normalized_data.get("booking_reference", ""),
            "vessel_name": normalized_data.get("vessel_name", ""),
            "voyage": normalized_data.get("voyage", ""),
            "quantity": normalized_data.get("quantity", 1),
            "pol": normalized_data.get("pol", ""),
            "pod": normalized_data.get("pod", ""),
            "etd": normalized_data.get("etd", ""),
            "eta": normalized_data.get("eta", ""),
            "transhipment_port": normalized_data.get("transhipment_port", ""),
            "port_terminal_city": normalized_data.get("port_terminal_city", ""),
            "cargo_type": extracted_data.get("cargo_type", ""),
            "gross_weight": extracted_data.get("gross_weight", ""),
            "document_type": extracted_data.get("document_type", ""),
            "print_date": normalized_data.get("print_date", ""),
            "pdf_print_date": normalized_data.get("pdf_print_date", normalized_data.get("print_date", "")),
            "extracted_text": text[:500] + "..." if len(text) > 500 else text  # Primeiros 500 caracteres para debug
        }
        
        return processed_data
        
    except Exception as e:
        st.error(f"❌ Erro durante a normalização: {str(e)}")
        return None

def display_pdf_validation_interface(processed_data):
    """
    Exibe interface para validação dos dados extraídos do PDF.
    
    Args:
        processed_data (dict): Dados processados do PDF
    
    Returns:
        dict: Dados validados pelo usuário ou None se cancelado
    """
    # Interface de validação dos dados extraídos do PDF
    
    # Cria formulário de validação
    with st.form("pdf_validation_form"):
        # Layout mais compacto e organizado (padronizado com demais telas)
        st.markdown("**📋 Validação de Booking**")
        
        # Primeira linha: Booking Reference e Quantidade de Containers
        col1, col2 = st.columns(2)
        with col1:
            booking_reference = st.text_input(
                "Booking Reference",
                value=processed_data.get("booking_reference", ""),
                help="Referência do booking do armador"
            )
        with col2:
            _raw_qty = processed_data.get("quantity", 1)
            try:
                _qty = int(_raw_qty)
            except Exception:
                _qty = 1
            if _qty < 1:
                _qty = 1
            quantity = st.number_input(
                "Quantity of Containers",
                min_value=1,
                value=_qty,
                help="Número de containers"
            )
        
        # Segunda linha: Nome do Navio, Carrier/Armador e Voyage
        col3, col4, col5 = st.columns(3)
        with col4:
            carrier = st.selectbox(
                "Voyage Carrier",
                ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL", "OTHER"],
                index=0 if processed_data["carrier"] == "GENERIC" else 
                      ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"].index(processed_data["carrier"]) 
                      if processed_data["carrier"] in ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"] else 8
            )
        with col3:
            # Carregar navios do banco de dados
            ships_data = load_ships_from_database()
            ship_names = [ship[0] for ship in ships_data]
            
            # Encontrar índice do navio extraído
            extracted_vessel = processed_data.get("vessel_name", "")
            vessel_index = 0
            
            if extracted_vessel:
                # Buscar correspondência case-insensitive
                extracted_lower = extracted_vessel.lower()
                ship_names_lower = [name.lower() for name in ship_names]
                
                if extracted_lower in ship_names_lower:
                    # Encontrou correspondência case-insensitive, usar a versão do banco
                    vessel_index = ship_names_lower.index(extracted_lower)
                else:
                    # Normalizar o nome extraído para Title Case antes de adicionar
                    normalized_vessel = extracted_vessel.title()
                    ship_names.insert(0, normalized_vessel)
                    vessel_index = 0
            
            vessel_name = st.selectbox(
                "Vessel Name",
                options=ship_names,
                index=vessel_index,
                help="Selecione o navio da lista"
            )
        with col5:
            voyage = st.text_input(
                "Voyage Code",
                value=processed_data.get("voyage", ""),
                help="Código da viagem"
            )
        
        # Terceira linha: Porto de Origem (POL) e Porto de Destino (POD)
        col6, col7 = st.columns(2)
        with col6:
            pol = st.text_input(
                "Port of Loading POL",
                value=processed_data.get("pol", ""),
                help="Port of Loading"
            )
        with col7:
            pod = st.text_input(
                "Port of Delivery POD",
                value=processed_data.get("pod", ""),
                help="Port of Discharge"
            )
        # Linha adicional: Transhipment Port e Port Terminal City
        col6b, col7b = st.columns(2)
        with col6b:
            transhipment_port = st.text_input(
                "Transhipment Port",
                value=processed_data.get("transhipment_port", ""),
                help="Porto de transbordo (se houver)"
            )
        with col7b:
            # Carregar terminais do banco de dados
            terminals_data = load_terminals_from_database()
            
            # Encontrar índice do terminal extraído
            extracted_terminal = processed_data.get("port_terminal_city", "")
            terminal_index = 0
            if extracted_terminal and extracted_terminal in terminals_data:
                terminal_index = terminals_data.index(extracted_terminal)
            elif extracted_terminal:
                # Se não encontrar exato, adicionar como opção
                terminals_data.insert(0, extracted_terminal)
                terminal_index = 0
            
            port_terminal_city = st.selectbox(
                "Port Terminal City",
                options=terminals_data,
                index=terminal_index,
                help="Selecione o terminal da lista ou digite para buscar"
            )
        
        # Converte datas do formato DD/MM/YYYY para datetime
        def parse_brazilian_date(date_str):
            if not date_str or date_str == "":
                return None
            try:
                # Tenta converter do formato DD/MM/YYYY
                if "/" in date_str:
                    return datetime.strptime(date_str, "%d/%m/%Y").date()
                # Fallback para formato YYYY-MM-DD
                elif "-" in date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d").date()
                else:
                    return None
            except:
                return None
        
        # Converte data de emissão do PDF (formato: 2024-09-06 18:23 UTC)
        def parse_print_date(date_str):
            if not date_str or date_str == "":
                return None
            try:
                # Remove UTC se presente
                date_clean = date_str.replace(" UTC", "").strip()
                # Tenta converter formato YYYY-MM-DD HH:MM
                if len(date_clean) == 16:  # 2024-09-06 18:23
                    return datetime.strptime(date_clean, "%Y-%m-%d %H:%M")
                # Tenta converter formato com segundos YYYY-MM-DD HH:MM:SS
                elif len(date_clean) == 19:  # 2024-09-06 18:23:45
                    return datetime.strptime(date_clean, "%Y-%m-%d %H:%M:%S")
                else:
                    return None
            except:
                return None
        
        # Quarta linha: ETD e ETA
        col8, col9 = st.columns(2)
        with col8:
            # Para MSC, não usar default se ETD não foi extraído
            if processed_data.get("carrier") == "MSC" and not processed_data.get("etd"):
                _etd_default = None
            else:
                _etd_default = parse_brazilian_date(processed_data.get("etd")) or datetime.today().date()
            
            etd = st.date_input(
                "Data Estimativa Saída ETD",
                value=_etd_default,
                help="Data estimada de partida"
            )
        with col9:
            _eta_default = parse_brazilian_date(processed_data.get("eta")) or datetime.today().date()
            eta = st.date_input(
                "Data Estimativa Chegada ETA",
                value=_eta_default,
                help="Data estimada de chegada"
            )
        
        # Quinta linha: PDF Print Date
        col10, col_spacer = st.columns([1, 1])
        with col10:
            pdf_print_date = st.text_input(
                "PDF Print Date",
                value=processed_data.get("pdf_print_date", ""),
                help="Data e hora de emissão do PDF (formato: 2024-09-06 18:23 UTC)"
            )
        
        
        # Campos ETD e ETA movidos para a quarta linha acima
        
        # Área de texto extraído removida para interface mais limpa
        
        # Botões de ação
        col1, col2, col_spacer_btn = st.columns([1, 1, 2])
        with col1:
            submitted = st.form_submit_button("✅ Validar e Salvar", type="primary", use_container_width=False)
        with col2:
            cancelled = st.form_submit_button("❌ Cancelar", use_container_width=False)
        
        if submitted:
            # Prepara dados validados com campos mapeados corretamente para insert_return_carrier_from_ui
            validated_data = {
                "Farol Reference": processed_data["farol_reference"],
                "Booking Reference": booking_reference,
                "Voyage Carrier": carrier,
                "Voyage Code": voyage,
                "Vessel Name": vessel_name,
                # Não é split neste fluxo de PDF; manter vazio
                "Splitted Booking Reference": "",
                "Quantity of Containers": int(quantity),
                "Port of Loading POL": pol,
                "Port of Delivery POD": pod,
                "Place of Receipt": pol,
                "Final Destination": pod,
                "Transhipment Port": transhipment_port,
                "Port Terminal City": port_terminal_city,
                # Preenchimentos padronizados esperados por insert_return_carrier_from_ui
                # ETD → Requested Deadline Start Date
                "Requested Deadline Start Date": etd.strftime("%Y-%m-%d") if etd else "",
                "Requested Deadline End Date": "",
                "Required Arrival Date": eta.strftime("%Y-%m-%d") if eta else "",
                "PDF Booking Emission Date": pdf_print_date
            }

            # Compatibilidade: alguns fluxos esperam a chave 'Terminal'
            if port_terminal_city:
                validated_data["Terminal"] = port_terminal_city
            
            # Debug simples para verificar se chegou aqui
            st.info("🔍 Dados preparados para salvamento")
            st.write("Farol Reference:", validated_data["Farol Reference"])
            st.write("Voyage Carrier:", validated_data["Voyage Carrier"])
            st.write("Quantity:", validated_data["Quantity of Containers"])
            
            return validated_data
        
        if cancelled:
            return "CANCELLED"
    
    return None

def save_pdf_booking_data(validated_data):
    """
    Salva os dados validados do PDF na tabela F_CON_RETURN_CARRIERS.
    
    Args:
        validated_data (dict): Dados validados pelo usuário
    
    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        # Tenta capturar o nome do arquivo PDF do session_state
        farol_reference = validated_data.get("Farol Reference")
        pdf_file = st.session_state.get(f"booking_pdf_file_{farol_reference}")
        
        if pdf_file and hasattr(pdf_file, 'name'):
            pdf_name = pdf_file.name
            # Adiciona o nome do PDF aos dados validados
            validated_data["PDF Name"] = pdf_name
        
        # ====== Validação de duplicidade (com base nos dados coletados) ======
        try:
            conn = get_database_connection()
            dup_sql = text(
                """
                SELECT COUNT(*) AS ct
                  FROM LogTransp.F_CON_RETURN_CARRIERS
                 WHERE FAROL_REFERENCE = :ref
                   AND NVL(B_BOOKING_REFERENCE,'') = NVL(:booking,'')
                   AND NVL(B_VOYAGE_CARRIER,'') = NVL(:carrier,'')
                   AND NVL(B_VOYAGE_CODE,'') = NVL(:voyage,'')
                   AND NVL(B_VESSEL_NAME,'') = NVL(:vessel,'')
                   AND NVL(PDF_BOOKING_EMISSION_DATE,'') = NVL(:pdf_date,'')
                """
            )
            dup_params = {
                "ref": farol_reference,
                "booking": (validated_data.get("Booking Reference") or "").strip(),
                "carrier": (validated_data.get("Voyage Carrier") or "").strip(),
                "voyage": (validated_data.get("Voyage Code") or "").strip(),
                "vessel": (validated_data.get("Vessel Name") or "").strip(),
                # Normaliza o campo de emissão para o formato salvo no banco (YYYY-MM-DD HH:MM)
                "pdf_date": (str(validated_data.get("PDF Booking Emission Date") or "").replace("UTC", "").replace("UT", "").strip()[:16])
            }
            ct = conn.execute(dup_sql, dup_params).scalar() or 0
            conn.close()
            if ct > 0:
                st.warning("⚠️ Este PDF já foi processado para esta Farol Reference com os mesmos dados (Booking/Carrier/Voyage/Vessel/Print Date). Operação cancelada.")
                # Ainda assim tenta coletar o monitoramento para atualizar a aba Histórico de Viagens
                try:
                    collect_voyage_monitoring_data(
                        validated_data.get("Vessel Name"),
                        validated_data.get("Port Terminal City"),
                        validated_data.get("Voyage Code", "")
                    )
                except Exception as e:
                    st.info(f"ℹ️ Coleta de monitoramento não realizada: {str(e)}")
                return False
        except Exception as _:
            # Em caso de falha na checagem, prossegue sem bloquear
            pass
        # ====== Fim validação duplicidade ======
        
        # Usa a função existente de inserção com status "Received from Carrier"
        success = insert_return_carrier_from_ui(validated_data, user_insert="PDF_PROCESSOR", status_override="Received from Carrier")
        
        if success:
            st.success("✅ Dados do PDF salvos com sucesso na tabela F_CON_RETURN_CARRIERS!")
            st.info("📋 Status definido como: **Received from Carrier**")
            st.info("ℹ️ **Voyage Monitoring:** Os dados de monitoramento serão coletados automaticamente durante a aprovação do registro.")
            
            # Salva também o PDF como anexo
            if pdf_file:
                try:
                    # Importa a função de salvamento de anexos do history.py
                    import sys
                    import os
                    sys.path.append(os.path.dirname(__file__))
                    from history import save_attachment_to_db
                    
                    # Reseta o ponteiro do arquivo para leitura
                    pdf_file.seek(0)
                    
                    # Salva o PDF como anexo
                    if save_attachment_to_db(farol_reference, pdf_file, user_id="PDF_PROCESSOR"):
                        st.success("📎 PDF salvo com sucesso na lista de anexos!")
                    else:
                        st.warning("⚠️ PDF não foi salvo na lista de anexos, mas os dados foram salvos na tabela.")
                except Exception as e:
                    st.warning(f"⚠️ Erro ao salvar PDF como anexo: {str(e)}")
                    st.info("💡 Os dados foram salvos na tabela, mas o PDF não foi adicionado à lista de anexos.")
            
            return True
        else:
            st.error("❌ Erro ao salvar dados do PDF")
            return False
    
    except Exception as e:
        st.error(f"❌ Erro ao salvar dados: {str(e)}")
        st.error(f"🔍 Tipo do erro: {type(e).__name__}")
        import traceback
        st.error(f"📍 Detalhes do erro: {traceback.format_exc()}")
        return False

def display_pdf_booking_section(farol_reference):
    """
    Exibe a seção de processamento de PDF de Booking.
    Esta função deve ser integrada na seção de anexos existente.
    
    Args:
        farol_reference (str): Referência do Farol
    """
    st.markdown("---")
    st.markdown("### 📄 PDF Booking Processor")
    st.markdown("Upload e processe PDFs de Booking recebidos por e-mail para extrair dados automaticamente.")
    
    if not PDF_AVAILABLE:
        st.error("⚠️ **PyPDF2 não está instalado**")
        st.markdown("Para usar esta funcionalidade, instale a dependência:")
        st.code("pip install PyPDF2")
        return
    
    # Upload de PDF específico para booking
    uploaded_pdf = st.file_uploader(
        "📄 Selecione o PDF de Booking",
        type=['pdf'],
        key=f"pdf_booking_{farol_reference}",
        help="Selecione apenas PDFs de booking recebidos por e-mail"
    )
    
    if uploaded_pdf is not None:
        st.success(f"📄 PDF selecionado: **{uploaded_pdf.name}**")
        # Guarda o arquivo para uso posterior (salvar como anexo)
        st.session_state[f"booking_pdf_file_{farol_reference}"] = uploaded_pdf
        
        # Botão para processar
        if st.button("🔍 Processar PDF", key=f"process_pdf_{farol_reference}", type="primary"):
            with st.spinner("Processando PDF... Extraindo dados..."):
                # Lê o conteúdo do PDF
                pdf_content = uploaded_pdf.read()
                
                # Processa o PDF
                processed_data = process_pdf_booking(pdf_content, farol_reference)
                
                if processed_data:
                    # Armazena os dados processados no session_state para validação
                    st.session_state[f"processed_pdf_data_{farol_reference}"] = processed_data
                    st.rerun()
    
    # Interface de validação se há dados processados
    processed_data_key = f"processed_pdf_data_{farol_reference}"
    if processed_data_key in st.session_state:
        processed_data = st.session_state[processed_data_key]
        
        # Exibe interface de validação
        validated_data = display_pdf_validation_interface(processed_data)
        
        if validated_data == "CANCELLED":
            # Remove dados processados se cancelado
            del st.session_state[processed_data_key]
            st.rerun()
        elif validated_data:
            # Salva os dados validados
            if save_pdf_booking_data(validated_data):
                # Remove dados processados após salvar
                del st.session_state[processed_data_key]
                st.balloons()  # Celebração visual
                st.rerun()


def map_msc_pdfs_in_directory(dir_path: str, save_csv: bool = True, csv_name: str = "msc_mapping.csv"):
    """Mapeia todos os PDFs MSC no diretório e gera um CSV com os campos extraídos.

    Args:
        dir_path: Caminho da pasta contendo PDFs.
        save_csv: Se True, salva um CSV na mesma pasta.
        csv_name: Nome do arquivo CSV de saída.

    Returns:
        pandas.DataFrame com uma linha por PDF.
    """
    rows = []
    # aceita .pdf e .PDF (e variações de caixa)
    pdf_paths = sorted(glob.glob(os.path.join(dir_path, "*.[Pp][Dd][Ff]")))
    for p in pdf_paths:
        try:
            with open(p, "rb") as f:
                text = extract_text_from_pdf(f)
            if not text:
                rows.append({"file_name": os.path.basename(p), "status": "no_text"})
                continue
            extracted = extract_msc_data(text)
            normalized = normalize_extracted_data(extracted)
            rows.append({
                "file_name": os.path.basename(p),
                "booking_reference": normalized.get("booking_reference", ""),
                "vessel_name": normalized.get("vessel_name", ""),
                "voyage": normalized.get("voyage", ""),
                "quantity": normalized.get("quantity", ""),
                "pol": normalized.get("pol", ""),
                "pod": normalized.get("pod", ""),
                "transhipment_port": normalized.get("transhipment_port", ""),
                "port_terminal_city": normalized.get("port_terminal_city", ""),
                "etd": normalized.get("etd", ""),
                "eta": normalized.get("eta", ""),
                "pdf_print_date": normalized.get("pdf_print_date", normalized.get("print_date", "")),
            })
        except Exception as e:
            rows.append({"file_name": os.path.basename(p), "error": str(e)})

    df = pd.DataFrame(rows)
    if save_csv:
        csv_path = os.path.join(dir_path, csv_name)
        df.to_csv(csv_path, index=False)
        print(f"CSV salvo em: {csv_path}")
    return df


def map_oocl_pdfs_in_directory(dir_path: str, save_csv: bool = True, csv_name: str = "oocl_mapping.csv"):
    """Mapeia todos os PDFs OOCL no diretório e gera um CSV com os campos extraídos.

    Args:
        dir_path: Caminho da pasta contendo PDFs.
        save_csv: Se True, salva um CSV na mesma pasta.
        csv_name: Nome do arquivo CSV de saída.

    Returns:
        pandas.DataFrame com uma linha por PDF.
    """
    rows = []
    # aceita .pdf e .PDF (e variações de caixa)
    pdf_paths = sorted(glob.glob(os.path.join(dir_path, "*.[Pp][Dd][Ff]")))
    for p in pdf_paths:
        try:
            with open(p, "rb") as f:
                text = extract_text_from_pdf(f)
            if not text:
                rows.append({"file_name": os.path.basename(p), "status": "no_text"})
                continue
            extracted = extract_oocl_data(text)
            normalized = normalize_extracted_data(extracted)
            rows.append({
                "file_name": os.path.basename(p),
                "booking_reference": normalized.get("booking_reference", ""),
                "vessel_name": normalized.get("vessel_name", ""),
                "voyage": normalized.get("voyage", ""),
                "quantity": normalized.get("quantity", ""),
                "flag": normalized.get("flag", ""),
                "carrier": normalized.get("carrier", ""),
                "pol": normalized.get("pol", ""),
                "pod": normalized.get("pod", ""),
                "transhipment_port": normalized.get("transhipment_port", ""),
                "port_terminal_city": normalized.get("port_terminal_city", ""),
                "etd": normalized.get("etd", ""),
                "eta": normalized.get("eta", ""),
                "pdf_print_date": normalized.get("pdf_print_date", normalized.get("print_date", "")),
            })
        except Exception as e:
            rows.append({"file_name": os.path.basename(p), "error": str(e)})

    df = pd.DataFrame(rows)
    if save_csv:
        csv_path = os.path.join(dir_path, csv_name)
        df.to_csv(csv_path, index=False)
        print(f"CSV salvo em: {csv_path}")
    return df


def map_pil_pdfs_in_directory(dir_path: str, save_csv: bool = True, csv_name: str = "pil_mapping.csv"):
    """Mapeia todos os PDFs PIL no diretório e gera um CSV com os campos extraídos.

    Args:
        dir_path: Caminho da pasta contendo PDFs.
        save_csv: Se True, salva um CSV na mesma pasta.
        csv_name: Nome do arquivo CSV de saída.

    Returns:
        pandas.DataFrame com uma linha por PDF.
    """
    rows = []
    # aceita .pdf e .PDF (e variações de caixa)
    pdf_paths = sorted(glob.glob(os.path.join(dir_path, "*.[Pp][Dd][Ff]")))
    for p in pdf_paths:
        try:
            with open(p, "rb") as f:
                text = extract_text_from_pdf(f)
            if not text:
                rows.append({"file_name": os.path.basename(p), "status": "no_text"})
                continue
            extracted = extract_generic_data(text)  # Usar extração genérica
            normalized = normalize_extracted_data(extracted)
            rows.append({
                "file_name": os.path.basename(p),
                "booking_reference": normalized.get("booking_reference", ""),
                "vessel_name": normalized.get("vessel_name", ""),
                "voyage": normalized.get("voyage", ""),
                "quantity": normalized.get("quantity", ""),
                "pol": normalized.get("pol", ""),
                "pod": normalized.get("pod", ""),
                "transhipment_port": normalized.get("transhipment_port", ""),
                "port_terminal_city": normalized.get("port_terminal_city", ""),
                "etd": normalized.get("etd", ""),
                "eta": normalized.get("eta", ""),
                "pdf_print_date": normalized.get("pdf_print_date", normalized.get("print_date", "")),
            })
        except Exception as e:
            rows.append({"file_name": os.path.basename(p), "error": str(e)})

    df = pd.DataFrame(rows)
    if save_csv:
        csv_path = os.path.join(dir_path, csv_name)
        df.to_csv(csv_path, index=False)
        print(f"CSV salvo em: {csv_path}")
    return df


def map_hapag_pdfs_in_directory(dir_path: str, save_csv: bool = True, csv_name: str = "hapag_mapping.csv"):
    """Mapeia todos os PDFs Hapag no diretório e gera um CSV com os campos extraídos.

    Args:
        dir_path: Caminho da pasta contendo PDFs.
        save_csv: Se True, salva um CSV na mesma pasta.
        csv_name: Nome do arquivo CSV de saída.

    Returns:
        pandas.DataFrame com uma linha por PDF.
    """
    rows = []
    # aceita .pdf e .PDF (e variações de caixa)
    pdf_paths = sorted(glob.glob(os.path.join(dir_path, "*.[Pp][Dd][Ff]")))
    for p in pdf_paths:
        try:
            with open(p, "rb") as f:
                text = extract_text_from_pdf(f)
            if not text:
                rows.append({"file_name": os.path.basename(p), "status": "no_text"})
                continue
            extracted = extract_hapag_lloyd_data(text)
            normalized = normalize_extracted_data(extracted)
            rows.append({
                "file_name": os.path.basename(p),
                "booking_reference": normalized.get("booking_reference", ""),
                "vessel_name": normalized.get("vessel_name", ""),
                "voyage": normalized.get("voyage", ""),
                "quantity": normalized.get("quantity", ""),
                "pol": normalized.get("pol", ""),
                "pod": normalized.get("pod", ""),
                "transhipment_port": normalized.get("transhipment_port", ""),
                "port_terminal_city": normalized.get("port_terminal_city", ""),
                "etd": normalized.get("etd", ""),
                "eta": normalized.get("eta", ""),
                "pdf_print_date": normalized.get("pdf_print_date", normalized.get("print_date", "")),
            })
        except Exception as e:
            rows.append({"file_name": os.path.basename(p), "error": str(e)})

    df = pd.DataFrame(rows)
    if save_csv:
        out_path = os.path.join(dir_path, csv_name)
        df.to_csv(out_path, index=False)
    return df


def map_all_carriers_pdfs(base_dirs: dict, save_csv: bool = True):
    """Mapeia PDFs de múltiplos carriers e gera relatório consolidado.
    
    Args:
        base_dirs: Dicionário {carrier: directory_path}
        save_csv: Se True, salva CSVs individuais
    
    Returns:
        dict: Resultados por carrier
    """
    mapping_functions = {
        "HAPAG": map_hapag_pdfs_in_directory,
        "MSC": map_msc_pdfs_in_directory,
        "OOCL": map_oocl_pdfs_in_directory,
        "PIL": map_pil_pdfs_in_directory
    }
    
    results = {}
    total_pdfs = 0
    total_successful = 0


