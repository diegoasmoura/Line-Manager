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
from database import get_database_connection, insert_return_carrier_from_ui
from sqlalchemy import text
import uuid

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
    },
    "HAPAG-LLOYD": {
        "booking_reference": [
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9]{8,12})",
            r"BKG\s+(?:REF|NO)[\s:]+([A-Z0-9]{8,12})",
            r"([A-Z]{4}\d{7})",  # Padrão típico HAPAG
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
        return None
    
    try:
        # Se é bytes, cria um file-like object
        if isinstance(pdf_file, bytes):
            from io import BytesIO
            pdf_file = BytesIO(pdf_file)
        
        # Reseta o ponteiro para o início
        pdf_file.seek(0)
        
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        return text.strip()
    
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {str(e)}")
        return None

def identify_carrier(text):
    """
    Identifica o armador/carrier baseado no conteúdo do PDF.
    
    Args:
        text (str): Texto extraído do PDF
    
    Returns:
        str: Nome do carrier identificado ou "GENERIC"
    """
    text_upper = text.upper()
    
    # Padrões de identificação de carriers
    carrier_indicators = {
        "HAPAG-LLOYD": ["HAPAG", "LLOYD", "HAPAG-LLOYD"],
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
        "booking_reference": r"Booking No\.?:\s*(\d+)",
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
        
        # Extrair informações da primeira linha MVS
        first_line = etd_eta_lines[0]
        first_dates = re.findall(r'\d{4}-\d{2}-\d{2}', first_line)
        first_etd = first_dates[0] if first_dates else None
        
        # Padrões para Vessel e Voy
        vessel_patterns = [
            r'MVS\s+PENDING MOTHER VSL\s+FLEX\s+(\d{4}-\d{2}-\d{2})',
            r'MVS\s+([^(]+?)(?:\s*\([^)]*\))?\s+(\d+[A-Z]?)',
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
        
        # Extrair informações da última linha MVS
        last_line = etd_eta_lines[-1]
        last_dates = re.findall(r'\d{4}-\d{2}-\d{2}', last_line)
        last_eta = last_dates[-1] if last_dates else None
        
        return first_etd, last_eta, first_vessel, first_voy
    
    # Extrair ETD, ETA, Vessel e Voy
    first_etd, last_eta, first_vessel, first_voy = extract_etd_eta_vessel(text_content)
    if first_etd:
        data["etd"] = first_etd
    if last_eta:
        data["eta"] = last_eta
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
        if keyword in text_content.upper():
            data["document_type"] = label
            break
    
    # Limpar campos de porto usando a função do código de exemplo
    def clean_port_field_maersk(value):
        if not value:
            return None
        # remover códigos ou complementos entre parênteses
        no_paren = re.sub(r"\s*\([^)]*\)", "", value)
        # quebrar por vírgula e pegar no máximo 3 partes
        parts = [p.strip() for p in no_paren.split(",") if p.strip()]
        if not parts:
            return None
        return ",".join(parts[:3])
    
    if "pol" in data and data["pol"]:
        data["pol"] = clean_port_field_maersk(data["pol"])
    
    if "pod" in data and data["pod"]:
        data["pod"] = clean_port_field_maersk(data["pod"])
    
    return data

def extract_hapag_lloyd_data(text_content):
    """Extrai dados específicos para PDFs da Hapag-Lloyd"""
    data = {}
    
    # Usar padrões específicos da Hapag-Lloyd
    patterns = CARRIER_PATTERNS["HAPAG-LLOYD"]
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    
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
    
    return data

def extract_cma_cgm_data(text_content):
    """Extrai dados específicos para PDFs da CMA CGM"""
    data = {}
    
    # Usar padrões específicos da CMA CGM
    patterns = CARRIER_PATTERNS["GENERIC"]  # Usar padrões genéricos por enquanto
    
    # Extrair dados básicos
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_content, re.IGNORECASE | re.MULTILINE)
            if match:
                data[field] = match.group(1).strip()
                break
    
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
        normalized["vessel_name"] = vessel.strip().title()
    
    # Normaliza voyage
    if "voyage" in extracted_data:
        normalized["voyage"] = extracted_data["voyage"].upper()
    
    # Normaliza quantity
    if "quantity" in extracted_data:
        try:
            normalized["quantity"] = int(extracted_data["quantity"])
        except ValueError:
            normalized["quantity"] = 1  # Default
    
    # Normaliza portos
    for port_field in ["pol", "pod"]:
        if port_field in extracted_data:
            port = extracted_data[port_field]
            # Remove vírgulas e normaliza
            port = re.sub(r',.*', '', port).strip().title()
            normalized[port_field] = port
    
    # Normaliza datas
    for date_field in ["etd", "eta"]:
        if date_field in extracted_data:
            date_str = extracted_data[date_field]
            try:
                # Tenta diferentes formatos de data
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%y", "%d-%m-%y"]:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        normalized[date_field] = date_obj.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            except Exception:
                normalized[date_field] = date_str  # Mantém original se não conseguir converter
    
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
        
        st.info("📄 Iniciando processamento do PDF...")
        
        # Extrai texto do PDF
        text = extract_text_from_pdf(pdf_content)
        if not text:
            st.error("❌ Não foi possível extrair texto do PDF")
            return None
        
        st.success(f"📝 Texto extraído com sucesso! ({len(text)} caracteres)")
        
        # Identifica o carrier
        carrier = identify_carrier(text)
        st.info(f"🚢 Carrier identificado: **{carrier}**")
        
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
    else:
        # Usar padrões genéricos para outros armadores
        patterns = CARRIER_PATTERNS.get(carrier, CARRIER_PATTERNS["GENERIC"])
        extracted_data = extract_data_with_patterns(text, patterns)
    
    try:
        # Normaliza os dados
        st.info("🔄 Normalizando dados extraídos...")
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
            "cargo_type": extracted_data.get("cargo_type", ""),
            "gross_weight": extracted_data.get("gross_weight", ""),
            "document_type": extracted_data.get("document_type", ""),
            "extracted_text": text[:500] + "..." if len(text) > 500 else text  # Primeiros 500 caracteres para debug
        }
        
        st.success("✅ Processamento concluído com sucesso!")
        st.info(f"📊 Dados extraídos: Booking {processed_data.get('booking_reference')}, Vessel {processed_data.get('vessel_name')}")
        
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
    st.markdown("### 📋 Validação dos Dados Extraídos")
    st.markdown("Verifique e ajuste os dados extraídos do PDF antes de salvar:")
    
    # Cria formulário de validação
    with st.form("pdf_validation_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🚢 Informações do Navio")
            carrier = st.selectbox(
                "Carrier/Armador",
                ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OTHER"],
                index=0 if processed_data["carrier"] == "GENERIC" else 
                      ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN"].index(processed_data["carrier"]) 
                      if processed_data["carrier"] in ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN"] else 6
            )
            
            vessel_name = st.text_input(
                "Nome do Navio",
                value=processed_data.get("vessel_name", ""),
                help="Nome da embarcação"
            )
            
            voyage = st.text_input(
                "Voyage",
                value=processed_data.get("voyage", ""),
                help="Código da viagem"
            )
            
            booking_reference = st.text_input(
                "Booking Reference",
                value=processed_data.get("booking_reference", ""),
                help="Referência do booking do armador"
            )
        
        with col2:
            st.markdown("#### 📦 Informações da Carga")
            quantity = st.number_input(
                "Quantidade de Containers",
                min_value=1,
                value=int(processed_data.get("quantity", 1)),
                help="Número de containers"
            )
            
            pol = st.text_input(
                "Porto de Origem (POL)",
                value=processed_data.get("pol", ""),
                help="Port of Loading"
            )
            
            pod = st.text_input(
                "Porto de Destino (POD)",
                value=processed_data.get("pod", ""),
                help="Port of Discharge"
            )
            
            st.markdown("#### 📅 Datas")
            etd = st.date_input(
                "ETD (Estimated Time of Departure)",
                value=datetime.strptime(processed_data.get("etd"), "%Y-%m-%d").date() 
                      if processed_data.get("etd") and processed_data.get("etd") != "" else None,
                help="Data estimada de partida"
            )
            
            eta = st.date_input(
                "ETA (Estimated Time of Arrival)",
                value=datetime.strptime(processed_data.get("eta"), "%Y-%m-%d").date() 
                      if processed_data.get("eta") and processed_data.get("eta") != "" else None,
                help="Data estimada de chegada"
            )
        
        # Área de texto extraído (para debug/verificação)
        with st.expander("🔍 Texto Extraído (para verificação)", expanded=False):
            st.text_area(
                "Primeiros 500 caracteres do PDF:",
                value=processed_data.get("extracted_text", ""),
                height=150,
                disabled=True
            )
        
        # Botões de ação
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("✅ Validar e Salvar", type="primary", use_container_width=True)
        with col2:
            cancelled = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        if submitted:
            # Prepara dados validados
            validated_data = {
                "Farol Reference": processed_data["farol_reference"],
                "Voyage Carrier": carrier,
                "Voyage Code": voyage,
                "Vessel Name": vessel_name,
                "Splitted Booking Reference": booking_reference,
                "Quantity of Containers": quantity,
                "Port of Loading POL": pol,
                "Port of Delivery POD": pod,
                "ETD": etd.strftime("%Y-%m-%d") if etd else "",
                "ETA": eta.strftime("%Y-%m-%d") if eta else "",
                "Status": "Received from Carrier"  # Status específico para PDFs processados
            }
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
        # Usa a função existente de inserção, mas com status específico
        success = insert_return_carrier_from_ui(validated_data, user_insert="PDF_PROCESSOR")
        
        if success:
            st.success("✅ Dados do PDF salvos com sucesso na tabela F_CON_RETURN_CARRIERS!")
            st.info("📋 Status definido como: **Received from Carrier**")
            return True
        else:
            st.error("❌ Erro ao salvar dados do PDF")
            return False
    
    except Exception as e:
        st.error(f"❌ Erro ao salvar dados: {str(e)}")
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
