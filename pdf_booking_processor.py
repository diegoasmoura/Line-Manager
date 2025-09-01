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
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    st.error("⚠️ PyPDF2 não está instalado. Execute: pip install PyPDF2")

# Padrões de extração por armador/carrier
CARRIER_PATTERNS = {
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
    "MAERSK": {
        "booking_reference": [
            r"Booking\s+(?:Reference|Number|No)[\s:]+([A-Z0-9]{8,12})",
            r"([A-Z]{4}\d{6})",  # Padrão típico Maersk
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
        
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
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
    if not PDF_AVAILABLE:
        st.error("PyPDF2 não está disponível para processamento de PDF")
        return None
    
    # Extrai texto do PDF
    text = extract_text_from_pdf(pdf_content)
    if not text:
        st.error("Não foi possível extrair texto do PDF")
        return None
    
    # Identifica o carrier
    carrier = identify_carrier(text)
    st.info(f"🚢 Carrier identificado: **{carrier}**")
    
    # Seleciona os padrões apropriados
    patterns = CARRIER_PATTERNS.get(carrier, CARRIER_PATTERNS["GENERIC"])
    
    # Extrai dados usando os padrões
    extracted_data = extract_data_with_patterns(text, patterns)
    
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
        "extracted_text": text[:500] + "..." if len(text) > 500 else text  # Primeiros 500 caracteres para debug
    }
    
    return processed_data

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
