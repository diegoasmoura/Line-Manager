import streamlit as st
import pandas as pd
from database import (
    get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, 
    get_database_connection, get_current_status_from_main_table, 
    get_return_carrier_status_by_adjustment_id, get_terminal_monitorings,
    approve_carrier_return, update_record_status
)
from shipments_mapping import get_column_mapping, process_farol_status_for_display
from sqlalchemy import text
from datetime import datetime
import os
import base64
import mimetypes
import uuid
from pdf_booking_processor import process_pdf_booking, display_pdf_validation_interface, save_pdf_booking_data

# Carrega dados da UDC para justificativas
df_udc = load_df_udc()
Booking_adj_area = df_udc[df_udc["grupo"] == "Booking Adj Area"]["dado"].dropna().unique().tolist()
Booking_adj_reason = df_udc[df_udc["grupo"] == "Booking Adj Request Reason"]["dado"].dropna().unique().tolist()
Booking_adj_responsibility = df_udc[df_udc["grupo"] == "Booking Adj Responsibility"]["dado"].dropna().unique().tolist()

# Opções específicas para New Adjustment no history.py
Booking_adj_reason_car = df_udc[df_udc["grupo"] == "Booking Adj Request Reason Car"]["dado"].dropna().unique().tolist()
Booking_adj_responsibility_car = df_udc[df_udc["grupo"] == "Booking Adj Responsibility Car"]["dado"].dropna().unique().tolist()

def get_next_linked_reference_number(farol_reference=None):
    """
    Obtém o próximo número sequencial para Linked_Reference.
    Se farol_reference for fornecido, gera formato hierárquico: FR_XX.XX_XXXX-R01
    Senão, mantém comportamento atual (global).
    """
    try:
        conn = get_database_connection()
        
        if farol_reference:
            # Novo formato hierárquico: FR_25.09_0001-R01
            query = text("""
                SELECT NVL(MAX(
                    CAST(SUBSTR(Linked_Reference, LENGTH(:farol_ref) + 3) AS NUMBER)
                ), 0) + 1 as next_number
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE Linked_Reference LIKE :pattern
                  AND Linked_Reference NOT IN ('New Adjustment')
            """)
            pattern = f"{farol_reference}-R%"
            result = conn.execute(query, {
                "farol_ref": farol_reference, 
                "pattern": pattern
            }).scalar()
            conn.close()
            next_num = result if result else 1
            return f"{farol_reference}-R{next_num:02d}"
        else:
            # Comportamento atual (global)
            query = text("""
                SELECT NVL(MAX(Linked_Reference), 0) + 1 as next_number
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE Linked_Reference IS NOT NULL
                      AND Linked_Reference NOT LIKE '%-R%'
                      AND Linked_Reference != 'New Adjustment'
            """)
            result = conn.execute(query).scalar()
            conn.close()
            return result if result else 1
            
    except Exception as e:
        st.error(f"❌ Erro ao obter próximo número sequencial: {str(e)}")
        return f"{farol_reference}-R01" if farol_reference else 1

def get_referenced_line_data(linked_ref):
    """
    Busca dados da linha referenciada pelo ID do Linked Reference.
    Retorna dicionário com dados da linha ou None se não encontrar.
    """
    if not linked_ref or str(linked_ref).strip() == "" or str(linked_ref).upper() == "NULL":
        return None
    
    linked_ref_str = str(linked_ref)
    
    # Se for "New Adjustment", não há linha referenciada
    if linked_ref_str == "New Adjustment":
        return None
    
    # Se for um ID numérico, busca a linha
    if linked_ref_str.isdigit():
        try:
            conn = get_database_connection()
            query = text("""
                SELECT ID, ROW_INSERTED_DATE, FAROL_REFERENCE, FAROL_STATUS
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE ID = :line_id
            """)
            result = conn.execute(query, {"line_id": int(linked_ref_str)}).fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'inserted_date': result[1],
                    'farol_reference': result[2],
                    'status': result[3]
                }
        except Exception as e:
            print(f"Erro ao buscar linha referenciada: {e}")
    
    return None

def format_linked_reference_display(linked_ref, farol_ref=None):
    """
    Formata Linked Reference para exibição amigável na UI.
    Exemplos:
    - "123" -> "Line 2 | 2025-10-24 15:35:24" (se ID 123 for linha 2)
    - "New Adjustment" -> "🆕 New Adjustment"
    - None/NULL -> "" (campo vazio)
    """
    # Se não há linked_ref, retorna vazio
    if not linked_ref or str(linked_ref).strip() == "" or str(linked_ref).upper() == "NULL":
        return ""
    
    linked_ref_str = str(linked_ref)
    
    if linked_ref_str == "New Adjustment":
        return "🆕 New Adjustment"
    
    # Se for um ID numérico, busca dados da linha referenciada
    if linked_ref_str.isdigit():
        line_data = get_referenced_line_data(linked_ref_str)
        if line_data:
            # Formata a data
            inserted_date = line_data.get('inserted_date')
            if inserted_date:
                try:
                    # Converte para datetime se necessário
                    if isinstance(inserted_date, str):
                        from datetime import datetime
                        parsed_date = datetime.fromisoformat(inserted_date.replace('Z', '+00:00'))
                    else:
                        parsed_date = inserted_date
                    
                    # Formata para YYYY-MM-DD HH:MM:SS
                    date_str = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    # Se não conseguir formatar, usa a string original
                    date_str = str(inserted_date)
            else:
                date_str = "N/A"
            
            # Retorna no formato: Line X | YYYY-MM-DD HH:MM:SS
            return f"Line {line_data['id']} | {date_str}"
        else:
            # Se não encontrar a linha, mostra o ID original
            return f"📋 Global Request #{linked_ref_str}"
    
    # Formato hierárquico: FR_25.09_0001-R01 (mantém formato original)
    if "-R" in linked_ref_str:
        parts = linked_ref_str.split("-R")
        if len(parts) == 2:
            farol_part = parts[0]
            request_num = parts[1]
            return f"📋 Request #{request_num} ({farol_part})"
    
    # Fallback
    return str(linked_ref)

def update_missing_linked_references():
    """
    Atualiza registros antigos que não têm LINKED_REFERENCE definido.
    Gera automaticamente o novo formato hierárquico.
    """
    try:
        conn = get_database_connection()
        
        # Busca registros sem LINKED_REFERENCE
        query = text("""
            SELECT ID, FAROL_REFERENCE 
            FROM LogTransp.F_CON_RETURN_CARRIERS 
            WHERE LINKED_REFERENCE IS NULL 
               OR LINKED_REFERENCE = ''
            ORDER BY FAROL_REFERENCE, ROW_INSERTED_DATE
        """)
        
        records = conn.execute(query).mappings().fetchall()
        
        if not records:
            return 0
        
        updated_count = 0
        for record in records:
            farol_ref = record['FAROL_REFERENCE']
            record_id = record['ID']
            
            # Gera novo Linked Reference
            new_linked_ref = get_next_linked_reference_number(farol_ref)
            
            # Atualiza o registro
            update_query = text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS 
                SET LINKED_REFERENCE = :linked_ref 
                WHERE ID = :record_id
            """)
            
            conn.execute(update_query, {
                "linked_ref": new_linked_ref,
                "record_id": record_id
            })
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
        
    except Exception as e:
        st.error(f"❌ Erro ao atualizar Linked References: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0

def get_voyage_monitoring_for_reference(farol_reference):
    """Busca dados de monitoramento de viagens relacionados a uma referência Farol"""
    try:
        conn = get_database_connection()
        
        # Busca navios associados a esta referência na tabela F_CON_RETURN_CARRIERS
        vessels_query = text("""
            SELECT DISTINCT B_VESSEL_NAME
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE FAROL_REFERENCE = :ref
              AND B_VESSEL_NAME IS NOT NULL
              AND LENGTH(TRIM(B_VESSEL_NAME)) > 0
        """)
        vessels_result = conn.execute(vessels_query, {"ref": farol_reference}).fetchall()
        
        if not vessels_result:
            return pd.DataFrame()
        
        # Lista de navios únicos
        vessel_names = [row[0] for row in vessels_result if row[0]]
        
        if not vessel_names:
            return pd.DataFrame()
        
        # Busca dados de monitoramento para esses navios
        # Só mostra registros que tenham vinculação com registros APROVADOS
        placeholders = ", ".join([f":vessel_{i}" for i in range(len(vessel_names))])
        monitoring_query = text(f"""
            SELECT DISTINCT m.DATA_SOURCE, m.*, r.ROW_INSERTED_DATE as APROVACAO_DATE
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS m
            INNER JOIN LogTransp.F_CON_RETURN_CARRIERS r ON (
                UPPER(m.NAVIO) = UPPER(r.B_VESSEL_NAME)
                AND UPPER(m.VIAGEM) = UPPER(r.B_VOYAGE_CODE)
                AND UPPER(m.TERMINAL) = UPPER(r.B_TERMINAL)
                AND r.FAROL_REFERENCE = :farol_ref
                AND r.FAROL_STATUS IN ('Booking Approved', 'Received from Carrier')
            )
            WHERE UPPER(m.NAVIO) IN ({placeholders})
            ORDER BY NVL(m.DATA_ATUALIZACAO, m.ROW_INSERTED_DATE) DESC
        """)
        
        # Prepara parâmetros com nomes em maiúsculas para busca
        params = {f"vessel_{i}": vessel_name.upper() for i, vessel_name in enumerate(vessel_names)}
        params["farol_ref"] = farol_reference
        
        result = conn.execute(monitoring_query, params).mappings().fetchall()
        conn.close()
        
        df = pd.DataFrame([dict(r) for r in result]) if result else pd.DataFrame()
        
        # Converter APROVACAO_DATE de UTC para horário local do Brasil
        if not df.empty and 'aprovacao_date' in df.columns:
            import pytz
            from datetime import datetime
            
            def convert_utc_to_brazil_time(utc_timestamp):
                if utc_timestamp is None:
                    return None
                try:
                    # Se já tem timezone, não converter (já está no horário correto)
                    if hasattr(utc_timestamp, 'tzinfo') and utc_timestamp.tzinfo is not None:
                        return utc_timestamp
                    
                    # Se não tem timezone, assumir que JÁ ESTÁ no horário local do Brasil
                    # (não converter, apenas adicionar timezone para consistência)
                    brazil_tz = pytz.timezone('America/Sao_Paulo')
                    brazil_dt = brazil_tz.localize(utc_timestamp)
                    return brazil_dt
                except Exception:
                    return utc_timestamp
            
            # Aplicar conversão
            df['aprovacao_date'] = df['aprovacao_date'].apply(convert_utc_to_brazil_time)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        return pd.DataFrame()


def get_available_references_for_relation(farol_reference=None):
    """Busca referências na aba 'Other Status' para relacionamento.

    Regra: se uma Farol Reference específica for fornecida (ex.: FR_25.09_0001.1),
    retornar apenas registros dessa mesma referência (exatos), excluindo apenas
    os com status 'Received from Carrier'. Caso contrário, mantém o comportamento
    anterior (listar originais/base de todas as referências).
    """
    try:
        conn = get_database_connection()
        if farol_reference:
            # Lista somente a própria referência (exata), na aba Other Status
            query = text("""
                SELECT ID, FAROL_REFERENCE, FAROL_STATUS, P_STATUS, ROW_INSERTED_DATE, Linked_Reference
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE FAROL_STATUS != 'Received from Carrier'
                  AND UPPER(FAROL_REFERENCE) = UPPER(:farol_reference)
                ORDER BY ROW_INSERTED_DATE ASC
            """)
            params = {"farol_reference": farol_reference}
            result = conn.execute(query, params).mappings().fetchall()
        else:
            # Comportamento legado: somente originais (não-split) de todas as referências
            query = text("""
                SELECT ID, FAROL_REFERENCE, FAROL_STATUS, P_STATUS, ROW_INSERTED_DATE, Linked_Reference
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE FAROL_STATUS != 'Received from Carrier'
                  AND NVL(S_SPLITTED_BOOKING_REFERENCE, '##NULL##') = '##NULL##' -- apenas originais
                  AND NOT REGEXP_LIKE(FAROL_REFERENCE, '\\.\\d+$')             -- exclui refs com sufixo .n
                ORDER BY ROW_INSERTED_DATE ASC
            """)
            result = conn.execute(query).mappings().fetchall()
        conn.close()
        # Converte as chaves para maiúsculas para consistência
        return [{k.upper(): v for k, v in dict(row).items()} for row in result] if result else []
    except Exception as e:
        st.error(f"❌ Erro ao buscar referências disponíveis: {str(e)}")
        return []

def get_file_type(uploaded_file):
    ext = uploaded_file.name.split('.')[-1].lower()
    mapping = {
        'pdf': 'PDF',
        'doc': 'Word',
        'docx': 'Word',
        'xls': 'Excel',
        'xlsx': 'Excel',
        'ppt': 'PowerPoint',
        'pptx': 'PowerPoint',
        'txt': 'Texto',
        'csv': 'CSV',
        'png': 'Imagem',
        'jpg': 'Imagem',
        'jpeg': 'Imagem',
        'gif': 'Imagem',
        'zip': 'Compactado',
        'rar': 'Compactado'
    }
    return mapping.get(ext, 'Outro')

def save_attachment_to_db(farol_reference, uploaded_file, user_id="system"):
    """
    Salva um anexo na tabela F_CON_ANEXOS.
    
    Args:
        farol_reference: Referência do Farol
        uploaded_file: Arquivo enviado pelo Streamlit file_uploader
        user_id: ID do usuário que enviou o arquivo
    
    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        conn = get_database_connection()
        
        # Lê o conteúdo do arquivo
        file_content = uploaded_file.read()
        
        # Obtém informações do arquivo
        file_name = uploaded_file.name
        # Obtém apenas o nome sem extensão e a extensão separadamente
        file_name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        file_extension = file_name.rsplit('.', 1)[1].upper() if '.' in file_name else ''
        # file_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        file_type = get_file_type(uploaded_file)
        
        # SQL com estrutura REAL da tabela (deixe trigger preencher ID)
        insert_query = text("""
            INSERT INTO LogTransp.F_CON_ANEXOS (
                id,
                farol_reference,
                adjustment_id,
                process_stage,
                type_,
                file_name,
                file_extension,
                upload_timestamp,
                attachment,
                user_insert
            ) VALUES (
                :id,
                :farol_reference,
                :adjustment_id,
                :process_stage,
                :type_,
                :file_name,
                :file_extension,
                :upload_timestamp,
                :attachment,
                :user_insert
            )
        """)
        
        conn.execute(insert_query, {
            "id": None,
            "farol_reference": farol_reference,
            "adjustment_id": str(uuid.uuid4()),  # Gera UUID para adjustment_id
            "process_stage": "Attachment Management",
            "type_": file_type,
            "file_name": file_name_without_ext,
            "file_extension": file_extension,
            "upload_timestamp": datetime.now(),
            "attachment": file_content,
            "user_insert": user_id
        })
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Erro ao salvar anexo: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def get_attachments_for_farol(farol_reference):
    """
    Busca todos os anexos para uma referência específica do Farol.
    
    Args:
        farol_reference: Referência do Farol
    
    Returns:
        DataFrame: DataFrame com os anexos encontrados
    """
    try:
        conn = get_database_connection()
        
        # SQL com estrutura REAL da tabela
        query = text("""
            SELECT 
                id,
                farol_reference,
                adjustment_id,
                process_stage,
                type_ as mime_type,
                file_name,
                file_extension,
                upload_timestamp as upload_date,
                user_insert as uploaded_by
            FROM LogTransp.F_CON_ANEXOS 
            WHERE farol_reference = :farol_reference
              AND (process_stage IS NULL OR process_stage <> 'Attachment Deleted')
            ORDER BY upload_timestamp DESC
        """)
        
        result = conn.execute(query, {"farol_reference": farol_reference}).mappings().fetchall()
        conn.close()
        
        if result:
            df = pd.DataFrame([dict(row) for row in result])
            # Adiciona colunas compatíveis para o código existente
            df['description'] = "Anexo para " + farol_reference
            # Reconstrói nome completo do arquivo
            df['full_file_name'] = df.apply(lambda row: f"{row['file_name']}.{row['file_extension']}" if row['file_extension'] else row['file_name'], axis=1)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Erro ao buscar anexos: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return pd.DataFrame()

def delete_attachment(attachment_id, deleted_by="system"):
    """
    Marca um anexo como excluído (soft delete) para respeitar o trigger que bloqueia DELETE.
    
    Args:
        attachment_id: ID numérico do anexo
        deleted_by: usuário que solicitou a exclusão
    
    Returns:
        bool: True se marcado como excluído com sucesso, False caso contrário
    """
    try:
        conn = get_database_connection()
        
        # Atualiza metadados e marca o estágio como deletado
        query = text("""
            UPDATE LogTransp.F_CON_ANEXOS
               SET process_stage = 'Attachment Deleted',
                   user_update = :user_update,
                   date_update = SYSDATE
             WHERE id = :attachment_id
        """)
        result = conn.execute(query, {"attachment_id": attachment_id, "user_update": deleted_by})
        conn.commit()
        conn.close()
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao excluir anexo: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def get_attachment_content(attachment_id):
    """
    Busca o conteúdo de um anexo específico.
    
    Args:
        attachment_id: ID numérico do anexo
    
    Returns:
        tuple: (file_content, file_name, mime_type) ou (None, None, None) se não encontrado
    """
    try:
        conn = get_database_connection()
        
        query = text("""
            SELECT attachment, file_name, file_extension, type_ as mime_type
            FROM LogTransp.F_CON_ANEXOS 
            WHERE id = :attachment_id
        """)
        
        result = conn.execute(query, {"attachment_id": attachment_id}).mappings().fetchone()
        conn.close()
        
        if result:
            # Reconstrói o nome do arquivo com extensão
            full_file_name = f"{result['file_name']}.{result['file_extension']}" if result['file_extension'] else result['file_name']
            return result['attachment'], full_file_name, result['mime_type']
        else:
            return None, None, None
            
    except Exception as e:
        st.error(f"Erro ao buscar conteúdo do anexo: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return None, None, None

def format_file_size(size_bytes):
    """Formata o tamanho do arquivo em uma string legível."""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def get_file_icon(mime_type, file_name):
    """Retorna um ícone apropriado baseado no tipo de arquivo."""
    if not mime_type:
        return "📄"
    
    if mime_type.startswith('image/'):
        return "🖼️"
    elif mime_type.startswith('video/'):
        return "🎥"
    elif mime_type.startswith('audio/'):
        return "🎵"
    elif mime_type in ['application/pdf']:
        return "📕"
    elif mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        return "📊"
    elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return "📝"
    elif mime_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
        return "📋"
    elif mime_type.startswith('text/'):
        return "📄"
    else:
        return "📎"

def get_main_table_data(farol_ref):
    """Busca dados específicos da tabela principal F_CON_SALES_BOOKING_DATA"""
    try:
        conn = get_database_connection()
        # Usando os mesmos nomes de coluna das outras funções que funcionam
        query = text("""
            SELECT 
                S_QUANTITY_OF_CONTAINERS,
                B_VOYAGE_CARRIER,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                ROW_INSERTED_DATE
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE FAROL_REFERENCE = :farol_reference
        """)
        result = conn.execute(query, {"farol_reference": farol_ref}).mappings().fetchone()
        conn.close()
        return result
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        st.error(f"❌ Erro na consulta: {str(e)}")
        return None

def display_attachments_section(farol_reference):
    """
    Exibe a seção de anexos para um Farol Reference específico.
    """
    # CSS personalizado para cards de anexos e métricas (garante visual igual em todas as telas)
    st.markdown("""
    <style>
    .attachment-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 18px;
        margin: 15px 0;
        background: linear-gradient(145deg, #ffffff, #f8f9fa);
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        text-align: center;
        border-left: 4px solid #1f77b4;
    }
    .attachment-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        border-left-color: #0d47a1;
    }
    .file-icon {
        font-size: 3em;
        margin-bottom: 15px;
        display: block;
    }
    .file-name {
        font-weight: bold;
        font-size: 16px;
        margin-bottom: 10px;
        color: #333;
        word-wrap: break-word;
    }
    .file-info {
        font-size: 13px;
        color: #666;
        margin: 5px 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    .metric-card {
        background: linear-gradient(145deg, #f0f8ff, #e6f3ff);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border: 1px solid #b3d9ff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .attachment-section {
        background-color: #fafafa;
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
        border: 1px solid #e0e0e0;
    }
    .upload-area {
        background-color: #f8f9fa;
        border: 2px dashed #dee2e6;
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
        text-align: center;
    }
    
    /* Reduz flickering entre abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        color: #262730;
        padding: 10px 16px;
        font-weight: 400;
        border: none;
        transition: none;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        color: #262730;
        border-bottom: 2px solid #00acb5;
        font-weight: 600;
    }
    
    /* Estabiliza elementos da interface */
    .stExpander {
        transition: none;
    }
    
    .stButton > button {
        transition: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # Controle de versão do uploader para permitir reset após salvar
    uploader_version_key = f"uploader_ver_{farol_reference}"
    if uploader_version_key not in st.session_state:
        st.session_state[uploader_version_key] = 0
    current_uploader_version = st.session_state[uploader_version_key]

    # Cache para reduzir re-renderização
    cache_key = f"attachment_cache_{farol_reference}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = {"last_update": 0}

    # Controle de estado do expander para manter aberto após processamento
    expander_key = f"expander_state_{farol_reference}"
    if expander_key not in st.session_state:
        st.session_state[expander_key] = False
    
    # Se há dados processados, mantém o expander aberto
    processed_data_key = f"processed_pdf_data_{farol_reference}"
    if processed_data_key in st.session_state:
        st.session_state[expander_key] = True

    # Seção de Upload Unificada
    with st.expander("📤 Add New Attachment", expanded=st.session_state[expander_key]):
        # Checkbox para ativar processamento de PDF de Booking
        process_booking_pdf = st.checkbox(
            "📄 Processar PDF de Booking recebido por e-mail", 
            key=f"process_booking_checkbox_{farol_reference}",
            help="Marque esta opção se o arquivo é um PDF de booking que precisa ser processado e validado"
        )
        
        # Mantém o expander aberto quando o checkbox é alterado
        if process_booking_pdf:
            st.session_state[expander_key] = True
        
        if process_booking_pdf:
            # Upload específico para PDFs de Booking
            uploaded_file = st.file_uploader(
                "Selecione o PDF de Booking",
                accept_multiple_files=False,  # Apenas um arquivo para booking
                type=['pdf'],  # Apenas PDFs
                key=f"uploader_booking_{farol_reference}_{current_uploader_version}",
                help="Selecione apenas PDFs de booking recebidos por e-mail • Limit 200MB per file • PDF"
            )
        else:
            # Upload de anexos regulares
            uploaded_files = st.file_uploader(
                "Drag and drop files here or click to select",
                accept_multiple_files=True,
                type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'],
                key=f"uploader_regular_{farol_reference}_{current_uploader_version}",
                help="Supported file types: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, PNG, JPG, JPEG, GIF, ZIP, RAR"
            )
        
        # Processamento baseado no tipo de upload
        if process_booking_pdf and uploaded_file:
            # Verificar se o arquivo é novo (automatizar processamento)
            import hashlib
            last_file_key = f"last_processed_file_{farol_reference}"
            current_file_key = f"uploaded_file_key_{farol_reference}"
            
            # Gera hash do arquivo atual
            uploaded_file.seek(0)
            file_hash = hashlib.md5(uploaded_file.read()).hexdigest()
            uploaded_file.seek(0)
            
            # Verifica se é um novo arquivo
            is_new_file = st.session_state.get(last_file_key, "") != file_hash
            
            if is_new_file:
                # Processa automaticamente o PDF
                with st.spinner("🔄 Processando PDF e extraindo dados..."):
                    try:
                        # Reseta o ponteiro do arquivo
                        uploaded_file.seek(0)
                        pdf_content = uploaded_file.read()
                        
                        # Processa o PDF
                        processed_data = process_pdf_booking(pdf_content, farol_reference)
                        
                        if processed_data:
                            # Limpar dados de navegação/API do PDF anterior (se existir)
                            # Isso garante que ao trocar de PDF, os campos sejam resetados
                            if f"api_dates_{farol_reference}" in st.session_state:
                                del st.session_state[f"api_dates_{farol_reference}"]
                            
                            # Armazena os dados processados no session_state para validação
                            st.session_state[f"processed_pdf_data_{farol_reference}"] = processed_data
                            st.session_state[f"booking_pdf_file_{farol_reference}"] = uploaded_file
                            st.session_state[last_file_key] = file_hash  # Armazena hash do arquivo processado
                            
                            # Atualiza cache para estabilizar a interface
                            if cache_key in st.session_state:
                                st.session_state[cache_key]["last_update"] = st.session_state[uploader_version_key]
                            
                            st.success("✅ Dados extraídos com sucesso! Valide as informações abaixo:")
                            st.rerun()
                        else:
                            st.error("❌ Processamento retornou dados vazios")
                            
                    except Exception as e:
                        st.error(f"❌ Erro durante o processamento: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
        
        elif not process_booking_pdf and uploaded_files:
            if st.button("💾 Save Attachments", key=f"save_attachments_{farol_reference}", type="primary"):
                progress_bar = st.progress(0, text="Saving attachments...")
                success_count = 0
                
                for i, file in enumerate(uploaded_files):
                    # Reseta o ponteiro do arquivo
                    file.seek(0)
                    
                    if save_attachment_to_db(farol_reference, file):
                        success_count += 1
                    
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress, text=f"Saving attachment {i+1} of {len(uploaded_files)}...")
                
                progress_bar.empty()
                
                if success_count == len(uploaded_files):
                    st.success(f"✅ {success_count} attachment(s) saved successfully!")
                else:
                    st.warning(f"⚠️ {success_count} of {len(uploaded_files)} attachments were saved.")

                # Incrementa a versão do uploader para resetar a seleção na próxima execução
                st.session_state[uploader_version_key] += 1

                # Atualiza cache para evitar re-renderização desnecessária
                if cache_key in st.session_state:
                    st.session_state[cache_key]["last_update"] = st.session_state[uploader_version_key]

                # Força atualização da lista (com uploader recriado)
                st.rerun()
        
        # Interface de validação se há dados processados armazenados (APENAS quando checkbox está marcado)
        if process_booking_pdf:
            processed_data_key = f"processed_pdf_data_{farol_reference}"
            if processed_data_key in st.session_state:
                processed_data = st.session_state[processed_data_key]
                
                # Exibe interface de validação
                validated_data = display_pdf_validation_interface(processed_data)
                
                if validated_data == "CANCELLED":
                    # Remove dados processados se cancelado
                    del st.session_state[processed_data_key]
                    if f"booking_pdf_file_{farol_reference}" in st.session_state:
                        del st.session_state[f"booking_pdf_file_{farol_reference}"]
                    # Fecha o expander após cancelar
                    st.session_state[expander_key] = False
                    st.rerun()
                elif validated_data:
                    # Salva os dados validados
                    if save_pdf_booking_data(validated_data):
                        # Remove dados processados após salvar
                        del st.session_state[processed_data_key]
                        if f"booking_pdf_file_{farol_reference}" in st.session_state:
                            del st.session_state[f"booking_pdf_file_{farol_reference}"]
                        # Fecha o expander após salvar com sucesso
                        st.session_state[expander_key] = False
                        
                        st.balloons()  # Celebração visual
                        st.rerun()

    # Lista de Anexos Existentes
    attachments_df = get_attachments_for_farol(farol_reference)

    st.divider()
    
    # Seção de anexos retraída por padrão
    with st.expander("📎 Attachments", expanded=False):
        if not attachments_df.empty:
            # Ordena por data/hora (mais recente primeiro)
            dfv = attachments_df.sort_values('upload_date', ascending=False).reset_index(drop=True)

            # Paginação
            page_size = st.selectbox(
                "Items per page",
                options=[6, 9, 12],
                index=1,
                key=f"att_page_size_{farol_reference}"
            )
            import math
            total_items = len(dfv)
            total_pages = max(1, math.ceil(total_items / page_size))
            page_key = f"att_page_{farol_reference}"
            current_page = st.session_state.get(page_key, 1)
            if current_page < 1:
                current_page = 1
            if current_page > total_pages:
                current_page = total_pages

            nav_prev, nav_info, nav_next = st.columns([1, 2, 1])
            with nav_prev:
                if st.button("⬅️ Prev", disabled=current_page <= 1, key=f"att_prev_{farol_reference}"):
                    st.session_state[page_key] = max(1, current_page - 1)
                    st.rerun()
            with nav_info:
                st.caption(f"Page {current_page} of {total_pages} • {total_items} item(s)")
            with nav_next:
                if st.button("Next ➡️", disabled=current_page >= total_pages, key=f"att_next_{farol_reference}"):
                    st.session_state[page_key] = min(total_pages, current_page + 1)
                    st.rerun()

            start_idx = (current_page - 1) * page_size
            end_idx = start_idx + page_size
            page_df = dfv.iloc[start_idx:end_idx].reset_index(drop=True)

            # Tabela com paginação
            h1, h2, h3, h4, h5, h6 = st.columns([5, 2, 2, 2, 1, 1])
            h1.markdown("**File**")
            h2.markdown("**Type/Ext**")
            h3.markdown("**User**")
            h4.markdown("**Date**")
            h5.markdown("**Download**")
            h6.markdown("**Delete**")

            for row_index, (_, att) in enumerate(page_df.iterrows()):
                row_key = f"{farol_reference}_{att['id']}_{start_idx + row_index}"
                confirm_key = f"confirm_del_flat_{row_key}"
                c1, c2, c3, c4, c5, c6 = st.columns([5, 2, 2, 2, 1, 1])
                with c1:
                    st.write(att.get('full_file_name', att['file_name']))
                with c2:
                    ext = (att.get('file_extension') or '').lower()
                    st.write(att.get('mime_type') or ext or 'N/A')
                with c3:
                    st.write(att.get('uploaded_by', ''))
                with c4:
                    st.write(att['upload_date'].strftime('%Y-%m-%d %H:%M') if pd.notna(att['upload_date']) else 'N/A')
                with c5:
                    fc, fn, mt = get_attachment_content(att['id'])
                    st.download_button("⬇️", data=fc or b"", file_name=fn or "file", mime=mt or "application/octet-stream",
                                       key=f"dl_flat_{row_key}", use_container_width=True, disabled=fc is None)
                with c6:
                    if not st.session_state.get(confirm_key, False):
                        if st.button("🗑️", key=f"del_flat_{row_key}", use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()

                if st.session_state.get(confirm_key, False):
                    wc1, wc2, wc3 = st.columns([6, 1, 1])
                    with wc1:
                        st.warning("⚠️ Are you sure you want to delete?")
                    with wc2:
                        if st.button("✅ Yes", key=f"yes_flat_{row_key}", use_container_width=True):
                            if delete_attachment(att['id'], deleted_by=st.session_state.get('current_user', 'system')):
                                st.success("✅ Attachment deleted successfully!")
                            else:
                                st.error("❌ Error deleting attachment!")
                            st.session_state[confirm_key] = False
                            st.rerun()
                    with wc3:
                        if st.button("❌ No", key=f"no_flat_{row_key}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()

            # Download em lote (zip) - todos
            from io import BytesIO
            import zipfile
            fc_total = []
            for _, att in dfv.iterrows():
                fc, fn, mt = get_attachment_content(att['id'])
                if fc and fn:
                    fc_total.append((fn, fc))
            if fc_total:
                buf = BytesIO()
                with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                    for fn, fc in fc_total:
                        zf.writestr(fn, fc)
                st.download_button("⬇️ Download all as .zip", data=buf.getvalue(), file_name="attachments.zip",
                                   mime="application/zip", key=f"dl_zip_all_{farol_reference}")
        else:
            st.info("📂 No attachments found for this reference.")
            st.markdown("💡 **Tip:** Use the 'Add New Attachment' section above to upload files related to this Farol Reference.")
    
    # Interface de validação agora está integrada na aba de processamento de PDF

def exibir_history():
    import pandas as pd
    import pytz
    from datetime import datetime
    
    def convert_utc_to_brazil_time(utc_timestamp):
        """Converte timestamp do banco para horário local do Brasil"""
        if utc_timestamp is None:
            return None
        
        try:
            # Se já é timezone-aware, assumir que é UTC
            if hasattr(utc_timestamp, 'tzinfo') and utc_timestamp.tzinfo is not None:
                # Se tem timezone UTC, converter para Brasil
                if str(utc_timestamp.tzinfo) == 'UTC' or str(utc_timestamp.tzinfo) == 'tzutc()':
                    brazil_tz = pytz.timezone('America/Sao_Paulo')
                    brazil_dt = utc_timestamp.astimezone(brazil_tz)
                    return brazil_dt
                else:
                    # Se já tem outro timezone, retornar como está
                    return utc_timestamp
            else:
                # Se é naive, assumir que JÁ ESTÁ no horário local do Brasil
                # (o banco Oracle armazena no horário local)
                brazil_tz = pytz.timezone('America/Sao_Paulo')
                brazil_dt = brazil_tz.localize(utc_timestamp)
                return brazil_dt
            
        except Exception:
            return utc_timestamp  # Retorna original se houver erro
    
    st.header("📜 Return Carriers History")


    
    # Exibe mensagens persistentes da última ação (flash)
    try:
        _flash = st.session_state.pop("history_flash", None)
        if _flash:
            level = _flash.get("type", "info")
            msg = _flash.get("msg", "")
            if level == "success":
                st.success(msg)
            elif level == "error":
                st.error(msg)
            elif level == "warning":
                st.warning(msg)
            else:
                st.info(msg)
    except Exception:
        pass
    
    # Espaçamento após o título
    st.markdown("<br>", unsafe_allow_html=True)

    farol_reference = st.session_state.get("selected_reference")
    if not farol_reference:
        st.info("Selecione uma linha em Shipments para visualizar o Ticket Journey.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return

    # Inicialização: ao entrar na tela pela primeira vez (por referência), retrai View Attachments e limpa estados residuais
    init_key = f"history_initialized_{farol_reference}"
    if not st.session_state.get(init_key):
        st.session_state["history_show_attachments"] = False
        # Limpa possíveis estados de processamento/expansão do módulo de anexos
        for k in [
            f"processed_pdf_data_{farol_reference}",
            f"booking_pdf_file_{farol_reference}",
            f"expander_state_{farol_reference}",
            f"attachment_cache_{farol_reference}",
            f"uploader_ver_{farol_reference}",
        ]:
            st.session_state.pop(k, None)
        st.session_state[init_key] = True


    df = get_return_carriers_by_farol(farol_reference)
    if df.empty:
        st.info("Nenhum registro para esta referência. Exibindo registros recentes:")
        df = get_return_carriers_recent(limit=200)
        if df.empty:
            st.warning("A tabela F_CON_RETURN_CARRIERS está vazia.")
            col = st.columns(1)[0]
            with col:
                if st.button("🔙 Back to Shipments"):
                    st.session_state["current_page"] = "main"
                    st.rerun()
            return


    
    # Informações organizadas em cards elegantes - consultadas da tabela principal
    main_status = get_current_status_from_main_table(farol_reference) or "-"
    
    # Busca dados da tabela principal F_CON_SALES_BOOKING_DATA em vez do último registro
    main_data = get_main_table_data(farol_reference)
    
    if main_data:
        # Dados da tabela principal - usando as chaves corretas (minúsculas)
        voyage_carrier = str(main_data.get("b_voyage_carrier", "-"))
        
        qty = main_data.get("s_quantity_of_containers", 0)
        try:
            qty = int(qty) if qty is not None and not pd.isna(qty) else 0
        except (ValueError, TypeError):
            qty = 0
        
        ins = main_data.get("row_inserted_date", "-")
        try:
            # Se já é datetime object, formata diretamente
            if isinstance(ins, datetime):
                ins = ins.strftime('%Y-%m-%d %H:%M:%S')
            # Se for epoch ms para datetime legível, se for numérico
            elif isinstance(ins, (int, float)):
                ins = datetime.fromtimestamp(ins/1000.0).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    else:
        # Fallback para valores do último registro se a tabela principal não tiver dados
        voyage_carrier = str(df.iloc[0].get("B_VOYAGE_CARRIER", "-")) if not df.empty else "-"
        qty = 0
        ins = "-"
    
    # Layout em uma linha com 5 colunas
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    
    with col1:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #00843D;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL REFERENCE</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{farol_reference}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #3599B8;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL STATUS</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{main_status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #4AC5BB;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">QUANTITY OF CONTAINERS</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{qty}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #168980;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">VOYAGE CARRIER</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{voyage_carrier}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #28738A;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">INSERTED</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{ins}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Grade principal com colunas relevantes (ADJUSTMENT_ID oculto mas usado internamente)
    # ID removido da visualização - não é mais necessário para o usuário
    display_cols = [
        "ROW_INSERTED_DATE",
        "FAROL_REFERENCE",
        "FAROL_STATUS",
        "B_BOOKING_REFERENCE",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_VOYAGE_CODE",
        "S_QUANTITY_OF_CONTAINERS",
        "S_PLACE_OF_RECEIPT",
        "S_PORT_OF_LOADING_POL",
        "S_PORT_OF_DELIVERY_POD",
        "S_FINAL_DESTINATION",
        "B_TRANSHIPMENT_PORT",
        "B_TERMINAL",
        "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
        "S_REQUESTED_DEADLINE_START_DATE",
        "S_REQUESTED_DEADLINE_END_DATE",
        "B_DATA_DRAFT_DEADLINE",
        "B_DATA_DEADLINE",
        "B_DATA_ESTIMATIVA_SAIDA_ETD",
        "B_DATA_ESTIMATIVA_CHEGADA_ETA",
        "B_DATA_ABERTURA_GATE",
        "B_DATA_CONFIRMACAO_EMBARQUE",
        "B_DATA_ESTIMADA_TRANSBORDO_ETD",
        "B_DATA_TRANSBORDO_ATD",
        "P_PDF_NAME",
        "PDF_BOOKING_EMISSION_DATE",
        "S_SPLITTED_BOOKING_REFERENCE",
        "LINKED_REFERENCE",
        "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "B_DATA_ATRACACAO_ATB",
        "B_DATA_PARTIDA_ATD",
        "B_DATA_CHEGADA_ATA",
        "ADJUSTMENTS_OWNER",
    ]

    # Inclui ADJUSTMENT_ID nos dados para funcionalidade interna
    internal_cols = display_cols + ["ADJUSTMENT_ID"]
    
    df_show = df[[c for c in internal_cols if c in df.columns]].copy()
    
    # Força a ordem correta das colunas baseada na lista display_cols
    ordered_cols = [c for c in internal_cols if c in df_show.columns]
    df_show = df_show[ordered_cols]
    
    # Aplica ordenação por Inserted Date antes de separar em abas
    if "ROW_INSERTED_DATE" in df_show.columns:
        # Ordenação primária por data inserida (mais antigo → mais novo)
        # Critério secundário estável: raiz da Farol Reference e sufixo numérico (.1, .2, ...)
        if "FAROL_REFERENCE" in df_show.columns:
            refs_base = df_show["FAROL_REFERENCE"].astype(str)
            df_show["__ref_root"] = refs_base.str.split(".").str[0]
            df_show["__ref_suffix_num"] = (
                refs_base.str.extract(r"\.(\d+)$")[0].fillna("0").astype(str).astype(int)
            )
            df_show = df_show.sort_values(
                by=["ROW_INSERTED_DATE", "__ref_root", "__ref_suffix_num"],
                ascending=[True, True, True],
                kind="mergesort",
            )
            df_show = df_show.drop(columns=["__ref_root", "__ref_suffix_num"])  # limpeza
        else:
            df_show = df_show.sort_values(by=["ROW_INSERTED_DATE"], ascending=[True], kind="mergesort")
    
    # Cria cópia do DataFrame (coluna Index será adicionada na função display_tab_content)
    df_display = df_show.copy()
    
    # DataFrame unificado - todas as linhas juntas
    df_unified = df_display.copy()
    
    # Remove splits informativos (exceto a referência atual) para contagem de rótulos
    df_other_status = df_display[df_display["FAROL_STATUS"] != "Received from Carrier"].copy()
    
    if not df_other_status.empty:
        # Filtrar linhas que são splits EXCETO a referência atual
        has_ref_col = "FAROL_REFERENCE" in df_other_status.columns
        
        if has_ref_col and farol_reference:
            import re
            # Mantém apenas:
            # 1. A referência atual (seja original ou split)
            # 2. Registros que NÃO são splits (não têm padrão .n)
            current_ref = str(farol_reference).strip()
            
            df_other_status = df_other_status[
                # É a referência atual OU não é um split
                (df_other_status["FAROL_REFERENCE"].astype(str) == current_ref) |
                (~df_other_status["FAROL_REFERENCE"].astype(str).str.match(r'.*\.\d+$', na=False))
            ].copy()
    
    # Separar PDFs "Received from Carrier" da referência atual para aprovação
    df_received_count = df_display[df_display["FAROL_STATUS"] == "Received from Carrier"].copy()
    df_received_for_approval = pd.DataFrame()

    try:
        if not df_received_count.empty and "FAROL_REFERENCE" in df_received_count.columns and farol_reference is not None:
            fr_sel = str(farol_reference).strip().upper()
            df_received_for_approval = df_received_count[
                df_received_count["FAROL_REFERENCE"].astype(str).str.upper() == fr_sel
            ].copy()
    except Exception:
        pass
    
    # Rótulos das abas
    unified_label = f"📋 Request Timeline ({len(df_unified)} records)"
    received_label = f"📨 Returns Awaiting Review ({len(df_received_for_approval)} records)"
    
    # Busca dados de monitoramento relacionados aos navios desta referência
    df_voyage_monitoring = get_voyage_monitoring_for_reference(farol_reference)

    # Contagem de combinações distintas (Navio + Viagem + Terminal)
    try:
        if df_voyage_monitoring is not None and not df_voyage_monitoring.empty:
            df_tmp_count = df_voyage_monitoring.copy()
            df_tmp_count['navio'] = df_tmp_count['navio'].astype(str)
            df_tmp_count['viagem'] = df_tmp_count['viagem'].astype(str)
            # Alguns datasets usam 'terminal' ou 'port_terminal_city'
            terminal_col = 'terminal' if 'terminal' in df_tmp_count.columns else ('port_terminal_city' if 'port_terminal_city' in df_tmp_count.columns else None)
            if terminal_col:
                df_tmp_count[terminal_col] = df_tmp_count[terminal_col].astype(str)
                distinct_count = df_tmp_count.drop_duplicates(subset=['navio', 'viagem', terminal_col]).shape[0]
            else:
                distinct_count = df_tmp_count.drop_duplicates(subset=['navio', 'viagem']).shape[0]
        else:
            distinct_count = 0
    except Exception:
        distinct_count = len(df_voyage_monitoring) if df_voyage_monitoring is not None else 0

    voyages_label = f"📅 Voyage Timeline ({distinct_count} distinct)"

    # Contagem para aba Audit Trail
    try:
        from sqlalchemy import text as _text_audit
        conn_cnt = get_database_connection()
        cnt_query = _text_audit("""
            SELECT COUNT(*)
            FROM LogTransp.V_FAROL_AUDIT_TRAIL
            WHERE FAROL_REFERENCE = :farol_ref
        """)
        audit_count = conn_cnt.execute(cnt_query, {"farol_ref": farol_reference}).scalar() or 0
        conn_cnt.close()
    except Exception:
        audit_count = 0

    # Label da aba Audit Trail
    audit_label = f"🔍 Audit Trail ({audit_count} records)"

    # Controle de "aba" ativa (segmented control) para detectar troca e limpar seleções da outra
    active_tab_key = f"history_active_tab_{farol_reference}"
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    if active_tab_key not in st.session_state:
        st.session_state[active_tab_key] = unified_label
        st.session_state[last_active_tab_key] = unified_label

    active_tab = st.segmented_control(
        "",
        options=[unified_label, voyages_label, audit_label],
        key=active_tab_key
    )

    # Se detectarmos troca de aba, limpamos as seleções das outras abas
    prev_tab = st.session_state.get(last_active_tab_key)
    if prev_tab != active_tab:
        if active_tab == unified_label:
            # Ao entrar na aba unificada, limpar qualquer seleção pendente
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        elif active_tab == audit_label:
            # Limpamos seleção quando entrar na Audit Trail
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        else:  # voyages_label
            # Limpamos seleção ao entrar na aba Voyages
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        # Ao trocar de aba, recolhe a seção de anexos para manter a tela limpa
        st.session_state["history_show_attachments"] = False
        st.session_state[last_active_tab_key] = active_tab

    # Função para calcular largura dinâmica das colunas baseada no conteúdo
    def calculate_column_width(df, column_name):
        """Calcula largura dinâmica baseada no conteúdo e título da coluna"""
        if column_name not in df.columns:
            return "small"
        
        # Largura baseada no título
        title_length = len(column_name)
        
        # Largura baseada no conteúdo (máximo de 10 amostras para performance)
        sample_size = min(10, len(df))
        if sample_size > 0:
            content_lengths = df[column_name].dropna().astype(str).str.len()
            max_content_length = content_lengths.max() if len(content_lengths) > 0 else 0
        else:
            max_content_length = 0
        
        # Calcula largura total necessária
        total_length = max(title_length, max_content_length)
        
        # Define largura baseada no tamanho total (mais conservadora)
        if total_length <= 12:
            return "small"
        elif total_length <= 20:
            return "medium"
        else:
            return "large"  # Apenas para colunas muito longas
    
    # Função para gerar configuração dinâmica de colunas
    def generate_dynamic_column_config(df, hide_status=False, hide_linked_reference=False):
        """Gera configuração de colunas com larguras dinâmicas"""
        config = {
            "ADJUSTMENT_ID": None,  # Sempre oculta
            "Status": None,  # Sempre oculta
            "Index": st.column_config.NumberColumn("Index", help="Índice da linha", width="small", disabled=True, format="%d"),
        }
        
        # Gera configuração para cada coluna
        for col in df.columns:
            if col in config:
                continue

            if col == "ID":
                config[col] = None
                continue
                
            # Oculta Status apenas se solicitado (aba Returns Awaiting Review)
            if col == "Status" and hide_status:
                config[col] = None
                continue
                
            # Oculta Linked Reference apenas se solicitado (aba Returns Awaiting Review)
            if col == "Linked Reference" and hide_linked_reference:
                config[col] = None
                continue
            
            # Larguras específicas para colunas específicas
            # Identifica a última coluna (excluindo colunas ocultas)
            visible_columns = [c for c in df.columns if c not in ["ADJUSTMENT_ID", "Index", "Status"] and not (c == "Linked Reference" and hide_linked_reference)]
            is_last_column = col == visible_columns[-1] if visible_columns else False
            
            if is_last_column:
                width = None  # Largura automática para última coluna
            else:
                width = "medium"  # Todas as outras colunas são medium
            
            # Determina o tipo de coluna baseado no nome
            if any(date_keyword in col.lower() for date_keyword in ["date", "deadline", "etd", "eta", "gate", "atd", "ata", "etb", "atb", "required", "arrival", "expected"]):
                config[col] = st.column_config.DatetimeColumn(col, format="DD/MM/YYYY HH:mm", width=width)
            elif col in ["Quantity of Containers"]:
                config[col] = st.column_config.NumberColumn(col, width=width)
            else:
                config[col] = st.column_config.TextColumn(col, width=width)
                
        return config

    # Função para processar e configurar DataFrame
    def process_dataframe(df_to_process):
        """Processa um DataFrame aplicando aliases e configurações"""
        if df_to_process.empty:
            return df_to_process

        # Aplica aliases iguais aos da grade principal quando disponíveis
        mapping_main = get_column_mapping()
        mapping_upper = {k.upper(): v for k, v in mapping_main.items()}

        def prettify(col: str) -> str:
            # Fallback: transforma COL_NAME -> Col Name e normaliza acrônimos
            label = col.replace("_", " ").title()
            # Normaliza acrônimos comuns
            replaces = {
                "Pol": "POL",
                "Pod": "POD",
                "Etd": "ETD",
                "Eta": "ETA",
                "Pdf": "PDF",
                "Id": "ID",
            }
            for k, v in replaces.items():
                label = label.replace(k, v)
            return label

        custom_overrides = {
            "ID": "ID",
            "FAROL_REFERENCE": "Farol Reference",
            "B_BOOKING_REFERENCE": "Booking",
            "ADJUSTMENT_ID": "ADJUSTMENT_ID",
            "LINKED_REFERENCE": "Linked Reference",
            "FAROL_STATUS": "Farol Status",  # Mantém Farol Status
            "ROW_INSERTED_DATE": "Inserted Date",
            "ADJUSTMENTS_OWNER": "Adjustments Owner",
            "P_PDF_NAME": "PDF Name",
            "S_QUANTITY_OF_CONTAINERS": "Quantity of Containers",
            "S_SPLITTED_BOOKING_REFERENCE": "Splitted Farol Reference",
            "B_VOYAGE_CODE": "Voyage Code",
            "B_VESSEL_NAME": "Vessel Name",
            "B_VOYAGE_CARRIER": "Carrier",
            "B_TRANSHIPMENT_PORT": "Transhipment Port",
            "B_TERMINAL": "Port Terminal",
            "S_PORT_OF_LOADING_POL": "Port of Loading POL",
            "S_PORT_OF_DELIVERY_POD": "Port of Delivery POD",
            "S_PLACE_OF_RECEIPT": "Place of Receipt",
            "S_FINAL_DESTINATION": "Final Destination",
            
            # Mapeamento para colunas padronizadas com data_ prefix
            "data_required_arrival_expected": "Required Arrival Date",
            "data_requested_deadline_start": "Requested Deadline Start",
            "data_requested_deadline_end": "Requested Deadline End",
            "data_draft_deadline": "Draft Deadline",
            "data_deadline": "Deadline",
            "data_estimativa_saida": "ETD",
            "data_estimativa_chegada": "ETA",
            "data_abertura_gate": "Abertura Gate",
            "data_confirmacao_embarque": "Confirmação Embarque",
            "data_estimada_transbordo": "Estimada Transbordo (ETD)",
            "data_transbordo": "Transbordo (ATD)",
            "data_estimativa_atracacao": "Estimativa Atracação (ETB)",
            "data_atracacao": "Atracação (ATB)",
            "data_partida": "Partida (ATD)",
            "data_chegada": "Chegada (ATA)",
            
            # Mapeamento para colunas antigas (compatibilidade)
            "B_DATA_ABERTURA_GATE": "Abertura Gate",
            "B_DATA_CONFIRMACAO_EMBARQUE": "Confirmação Embarque",
            "B_DATA_ESTIMADA_TRANSBORDO_ETD": "Estimada Transbordo (ETD)",
            "B_DATA_TRANSBORDO_ATD": "Transbordo (ATD)",
            "B_DATA_DRAFT_DEADLINE": "Draft Deadline",
            "B_DATA_DEADLINE": "Deadline",
            "S_REQUESTED_DEADLINE_START_DATE": "Requested Deadline Start",
            "S_REQUESTED_DEADLINE_END_DATE": "Requested Deadline End",
            "S_REQUIRED_ARRIVAL_DATE_EXPECTED": "Required Arrival Date",
            "B_DATA_ESTIMATIVA_SAIDA_ETD": "ETD",
            "B_DATA_ESTIMATIVA_CHEGADA_ETA": "ETA",
            "B_DATA_ESTIMATIVA_ATRACACAO_ETB": "Estimativa Atracação (ETB)",
            "B_DATA_ATRACACAO_ATB": "Atracação (ATB)",
            "B_DATA_PARTIDA_ATD": "Partida (ATD)",
            "B_DATA_CHEGADA_ATA": "Chegada (ATA)",
        }

        # Aplica aliases ao DataFrame
        rename_map = {}
        for col in df_to_process.columns:
            rename_map[col] = custom_overrides.get(col, mapping_upper.get(col, prettify(col)))
        
        df_processed = df_to_process.copy()
        df_processed.rename(columns=rename_map, inplace=True)
        
        # Tratamento robusto para valores nulos (None, NaN, NaT)
        
        for col in df_processed.columns:
            
            # Verifica valores únicos antes do tratamento
            unique_before = df_processed[col].unique()
            
            if df_processed[col].dtype == 'datetime64[ns]':
                # Para colunas de data: converte NaT para string vazia diretamente
                df_processed[col] = df_processed[col].astype(str).replace('NaT', '')
            else:
                # Para outras colunas: substitui valores nulos por string vazia
                df_processed[col] = df_processed[col].fillna('')
            
            # Verifica valores únicos depois do tratamento
            unique_after = df_processed[col].unique()
            print("---")
        
        # Debug: verifica valores de data após tratamento
        for col in df_processed.columns:
            if 'Date' in col or 'Deadline' in col or 'ETD' in col or 'ETA' in col:
                unique_vals = df_processed[col].unique()
        
        # Aplica formatação amigável para Linked Reference
        if "Linked Reference" in df_processed.columns:
            df_processed["Linked Reference"] = df_processed.apply(
                lambda row: format_linked_reference_display(
                    row.get("Linked Reference"), 
                    row.get("Farol Reference")
                ), 
                axis=1
            )
        
        # Campo "Status" removido - usando apenas "Farol Status" para exibição
        
        # A ordenação de colunas foi movida para a função display_tab_content para centralizar a lógica.

        # Deriva/Preenche a coluna "Splitted Farol Reference" quando a referência tem sufixo .n
        try:
            if "Splitted Farol Reference" not in df_processed.columns:
                df_processed["Splitted Farol Reference"] = None
            if "Farol Reference" in df_processed.columns:
                refs_series = df_processed["Farol Reference"].astype(str)
                has_suffix = refs_series.str.contains(r"\.\d+$", regex=True)

                def _is_empty_split(val):
                    if val is None:
                        return True
                    if isinstance(val, str):
                        v = val.strip()
                        return v == "" or v.upper() == "NULL"
                    try:
                        return pd.isna(val)
                    except Exception:
                        return False

                mask_empty = df_processed["Splitted Farol Reference"].apply(_is_empty_split)
                fill_mask = has_suffix & mask_empty
                if fill_mask.any():
                    df_processed.loc[fill_mask, "Splitted Farol Reference"] = df_processed.loc[fill_mask, "Farol Reference"]
        except Exception:
            pass
        
        


        
        # Aplica a formatação de ícones no Farol Status
        df_processed = process_farol_status_for_display(df_processed)

        return df_processed

    # Função para exibir grade em uma aba
    def display_tab_content(df_tab, tab_name):
        """Exibe o conteúdo de uma aba com a grade de dados"""
        if df_tab.empty:
            st.info(f"📋 Nenhum registro encontrado para {tab_name}")
            return None
            
        # Processa o DataFrame da aba
        df_processed = process_dataframe(df_tab)
        
        # Converte datas para exibição
        date_cols = [
            "Inserted Date", "Draft Deadline", "Deadline", 
            "Requested Deadline Start", "Requested Deadline End", "Required Arrival Date",
            "ETD", "ETA", "Abertura Gate",
            "Confirmação Embarque", "Partida (ATD)", "Estimada Transbordo (ETD)",
            "Chegada (ATA)", "Transbordo (ATD)", "Estimativa Atracação (ETB)", "Atracação (ATB)",
            "PDF Booking Emission Date"
        ]
        
        for col in date_cols:
            if col in df_processed.columns:
                # Converte para datetime - deixa o Streamlit fazer a formatação
                df_processed[col] = pd.to_datetime(df_processed[col], errors='coerce')

        # Ordena por Inserted Date e, dentro do mesmo dia/hora, por raiz e sufixo da Farol Reference
        if "Inserted Date" in df_processed.columns:
            if "Farol Reference" in df_processed.columns:
                refs_base = df_processed["Farol Reference"].astype(str)
                df_processed["__ref_root"] = refs_base.str.split(".").str[0]
                df_processed["__ref_suffix_num"] = (
                    refs_base.str.extract(r"\.(\d+)$")[0].fillna("0").astype(str).astype(int)
                )
                df_processed = df_processed.sort_values(
                    by=["Inserted Date", "__ref_root", "__ref_suffix_num"],
                    ascending=[True, True, True],
                    kind="mergesort",
                )
                df_processed = df_processed.drop(columns=["__ref_root", "__ref_suffix_num"])  # limpeza
            else:
                df_processed = df_processed.sort_values(by=["Inserted Date"], ascending=[True], kind="mergesort")

        # Caso especial: para a referência atualmente selecionada, garante a marcação da primeira linha Booking Requested
        try:
            if "Farol Reference" in df_processed.columns and "Farol Status" in df_processed.columns and "Inserted Date" in df_processed.columns:
                sel_ref = str(farol_reference) if farol_reference is not None else None
                if sel_ref:
                    mask_sel = (df_processed["Farol Reference"].astype(str) == sel_ref) & (
                        df_processed["Farol Status"].astype(str).str.strip().str.lower() == "booking requested".lower()
                    )
                    if mask_sel.any():
                        first_idx_sel = df_processed.loc[mask_sel].sort_values("Inserted Date").index[0]
                        # Lógica de status removida - usando apenas "Farol Status"
        except Exception:
            pass

        # Marca a primeira linha "Booking Requested" como pedido de booking Cargill por Farol Reference
        # IMPORTANTE: Isso acontece APÓS a renderização de Status para sobrescrever "Split Info" quando necessário
        try:
            required_cols = {"Farol Status", "Inserted Date", "Farol Reference"}
            if required_cols.issubset(set(df_processed.columns)):
                df_req = df_processed[df_processed["Farol Status"] == "Booking Requested"].copy()
                if not df_req.empty:
                    idx_first = df_req.sort_values("Inserted Date").groupby("Farol Reference", as_index=False).head(1).index
                    if "Linked Reference" in df_processed.columns:
                        import pandas as _pd
                        for i in idx_first:
                            linked_val = df_processed.loc[i, "Linked Reference"] if "Linked Reference" in df_processed.columns else None
                            is_empty = (linked_val is None) or (isinstance(linked_val, str) and linked_val.strip() == "") or (str(linked_val).upper() == "NULL") or (hasattr(_pd, 'isna') and _pd.isna(linked_val))
                            if is_empty:
                                # Lógica de status removida - usando apenas "Farol Status"
                                pass
        except Exception:
            pass

        # Força: a PRIMEIRA linha da referência atualmente selecionada recebe "📦 Cargill Booking Request"
        try:
            if "Farol Reference" in df_processed.columns and "Inserted Date" in df_processed.columns and farol_reference is not None:
                sel_ref_str = str(farol_reference)
                mask_same_ref = df_processed["Farol Reference"].astype(str) == sel_ref_str
                if mask_same_ref.any():
                    first_idx_any = df_processed.loc[mask_same_ref].sort_values("Inserted Date").index[0]
                    # Lógica de status removida - usando apenas "Farol Status"
        except Exception:
            pass

        # Reordenar colunas conforme ordem solicitada nas duas abas
        try:
            desired_order = [
                "Index",
                "Farol Status",
                "Inserted Date",
                "Farol Reference",
                "Carrier",
                "Booking",
                "Vessel Name",
                "Voyage Carrier",
                "Voyage Code",
                "Quantity of Containers",
                "Place of Receipt",
                "Port of Loading POL",
                "Port of Delivery POD",
                "Final Destination",
                "Transhipment Port",
                "Port Terminal",
                "Required Arrival Date",
                "Requested Deadline Start",
                "Requested Deadline End",
                "Deadline",
                "Draft Deadline",
                "Abertura Gate",
                "Confirmação Embarque",
                "ETD",
                "ETA",
                "Estimativa Atracação (ETB)",
                "Atracação (ATB)",
                "Partida (ATD)",
                "Estimada Transbordo (ETD)",
                "Chegada (ATA)",
                "Transbordo (ATD)",
                "PDF Name",
                "PDF Booking Emission Date",
                "Splitted Farol Reference",
                "Linked Reference",
            ]
            
            # Helper function to reorder columns safely
            def reorder_columns(df, ordered_list):
                existing_cols = [col for col in ordered_list if col in df.columns]
                # Filtra colunas ocultas das colunas restantes
                hidden_cols = ["ADJUSTMENT_ID", "Status"]
                remaining_cols = [col for col in df.columns if col not in existing_cols and col not in hidden_cols]
                return df[existing_cols + remaining_cols]

            df_processed = reorder_columns(df_processed, desired_order)

        except Exception:
            pass
        
        # Adiciona coluna de índice APÓS a reordenação
        df_processed.insert(0, "Index", range(len(df_processed)))
                
        return df_processed

    def detect_changes_for_new_adjustment(df_processed):
        """
        Detecta alterações em linhas com Status = "New Adjustment" comparando com a linha anterior.
        Retorna dicionário com pares (row_index, column_name) onde há diferença.
        """
        if df_processed is None or df_processed.empty:
            return {}
        
        # Campos editáveis baseados em shipments_split.py (usando aliases corretos)
        editable_fields = [
            "Quantity of Containers",
            "Port of Loading POL",
            "Port of Delivery POD", 
            "Place of Receipt",
            "Final Destination",
            "Transhipment Port",
            "Port Terminal",
            "Carrier",
            "Voyage Code",
            "Booking",
            "Vessel Name",
            "Requested Deadline Start",
            "Requested Deadline End",
            "Required Sail Date",
            "Required Arrival Date"
        ]
        
        changes = {}
        
        # Percorre o DataFrame linha a linha
        for idx in range(len(df_processed)):  # Começa do índice 0 (primeira linha)
            current_row = df_processed.iloc[idx]
            
            # Se é a primeira linha, compara com a segunda linha (índice 1)
            if idx == 0:
                if len(df_processed) > 1:
                    previous_row = df_processed.iloc[1]  # Compara com a segunda linha
                else:
                    continue
            else:
                previous_row = df_processed.iloc[idx - 1]
            
            # Verifica se a linha atual é "New Adjustment"
            status = current_row.get("Farol Status", "")
            if pd.isna(status) or status is None:
                status = ""
            else:
                status = str(status)
            
            if status == "🛠️ New Adjustment":
                # Compara cada campo editável
                for field in editable_fields:
                    if field in df_processed.columns:
                        current_val = current_row[field]
                        previous_val = previous_row[field]
                        
                        # Normaliza valores para comparação
                        def normalize_value(val):
                            if pd.isna(val) or val is None or val == "":
                                return None
                            # Para datas, converte para string para comparação
                            if hasattr(val, 'strftime'):
                                return val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(val, 'hour') else val.strftime('%Y-%m-%d')
                            return str(val)
                        
                        current_normalized = normalize_value(current_val)
                        previous_normalized = normalize_value(previous_val)
                        
                        # Se os valores normalizados são diferentes
                        if current_normalized != previous_normalized:
                            changes[(idx, field)] = {
                                'current': current_val,
                                'previous': previous_val
                            }
        
        return changes

    def apply_highlight_styling(df_processed, changes_dict):
        """
        Aplica estilização usando Pandas Styler para destacar células alteradas e layout zebra.
        
        Args:
            df_processed: DataFrame processado
            changes_dict: Dicionário com pares (row_idx, col_name) -> change_info
        
        Returns:
            DataFrame estilizado com Pandas Styler
        """
        if df_processed is None or df_processed.empty:
            return df_processed
        
        # Cria uma cópia para não modificar o original
        df_styled = df_processed.copy()
        
        # Aplica o mesmo tratamento de valores nulos na cópia
        for col in df_styled.columns:
            if df_styled[col].dtype == 'datetime64[ns]':
                
                # Para colunas de data: converte NaT para string vazia diretamente
                df_styled[col] = df_styled[col].astype(str).replace('NaT', '')
                
            else:
                # Para outras colunas: substitui valores nulos por string vazia
                df_styled[col] = df_styled[col].fillna('')
        
        # Debug: verifica se o tratamento foi aplicado corretamente
        for col in df_styled.columns:
            if 'Date' in col or 'Deadline' in col or 'ETD' in col or 'ETA' in col:
                unique_vals = df_styled[col].unique()
        
        # Debug: verifica valores nulos após tratamento
        for col in df_styled.columns:
            if 'Date' in col or 'Deadline' in col or 'ETD' in col or 'ETA' in col:
                unique_vals = df_styled[col].unique()
        
        # Função para aplicar estilo baseado nas alterações detectadas e layout zebra
        def highlight_changes_and_zebra(row):
            styles = [''] * len(row)
            row_idx = row.name
            
            # Layout zebra - linhas pares mais claras, ímpares mais escuras
            if row_idx % 2 == 0:
                base_bg = 'background-color: #F1F3F4;'  # Cinza mais escuro (5% mais escuro)
            else:
                base_bg = 'background-color: #FFFFFF;'  # Branco
            
            # Aplica cor de fundo base para toda a linha
            for i in range(len(styles)):
                styles[i] = base_bg
            
            # Verifica se esta linha tem alterações e aplica destaque
            for (change_row_idx, col_name), change_info in changes_dict.items():
                if change_row_idx == row_idx and col_name in df_styled.columns:
                    col_idx = df_styled.columns.get_loc(col_name)
                    # Destaque de alteração sobrescreve a cor zebra
                    styles[col_idx] = 'background-color: #FFF9C4; border: 2px solid #FFD54F;'
            
            return styles
        
        # Aplica o estilo usando Pandas Styler
        styled_df = df_styled.style.apply(highlight_changes_and_zebra, axis=1)
        
        return styled_df

    # Conteúdo da aba unificada "Request Timeline"
    df_unified_processed = None
    if active_tab == unified_label:
        df_unified_processed = display_tab_content(df_unified, "Request Timeline")
    edited_df_unified = None
    if df_unified_processed is not None and active_tab == unified_label:
        # Gera configuração dinâmica baseada no conteúdo (Status visível)
        column_config = generate_dynamic_column_config(df_unified_processed, hide_status=False)
        # Detectar e destacar alterações em linhas "New Adjustment"
        # Inverte o DataFrame para que a ordem visual corresponda ao índice
        df_unified_processed_reversed = df_unified_processed.iloc[::-1].reset_index(drop=True)
        changes = detect_changes_for_new_adjustment(df_unified_processed_reversed)
        
        # Detecção de alterações (sem debug visual)
        
        # Aplicar estilização usando Pandas Styler
        if changes:
            styled_df = apply_highlight_styling(df_unified_processed_reversed, changes)
        else:
            # Se não há alterações, usar DataFrame normal
            styled_df = df_unified_processed_reversed
        
        # Aplica tratamento de valores nulos no DataFrame final antes da exibição
        if hasattr(styled_df, 'data'):
            # Se é um Styler, trata o DataFrame subjacente
            df_to_check = styled_df.data.copy()
        else:
            # Se é um DataFrame normal
            df_to_check = styled_df.copy()
        
        # Aplica tratamento de valores nulos no DataFrame final
        for col in df_to_check.columns:
            if df_to_check[col].dtype == 'datetime64[ns]':
                # Para colunas de data: converte NaT para string vazia
                df_to_check[col] = df_to_check[col].astype(str).replace('NaT', '')
            else:
                # Para outras colunas: substitui valores nulos por string vazia
                df_to_check[col] = df_to_check[col].fillna('')
        
        # Debug: verifica colunas de data após tratamento final
        for col in df_to_check.columns:
            if 'Date' in col or 'Deadline' in col or 'ETD' in col or 'ETA' in col:
                unique_vals = df_to_check[col].unique()
        
        # Atualiza o styled_df com o DataFrame tratado
        if hasattr(styled_df, 'data'):
            styled_df.data = df_to_check
        else:
            styled_df = df_to_check
        
        # Configuração básica da coluna Index
        column_config = {
            "Index": st.column_config.NumberColumn(
                "Index", 
                help="Índice da linha", 
                width=50,  # Largura fixa em pixels
                disabled=True,
                format="%d"
            )
        }
        
        # Usar st.dataframe com o DataFrame (estilizado ou normal)
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            key=f"history_unified_{farol_reference}"
        )
        
        # Para compatibilidade com o resto do código, usar o DataFrame original
        edited_df_unified = df_unified_processed
        
        # Informações sobre a timeline
        if not df_received_for_approval.empty:
            st.info("ℹ️ **Request Timeline:** Visualize o histórico completo de alterações. Use o selectbox na seção abaixo para selecionar e avaliar retornos dos armadores.")
        else:
            st.info("ℹ️ **Request Timeline:** Visualize o histórico completo de alterações da referência.")

    # Seção de aprovação para PDFs "Received from Carrier" (abaixo da tabela unificada)
    # Usaremos o DataFrame ORIGINAL (antes da reversão) para buscar o Index correto
    df_for_approval = df_unified_processed.copy() if df_unified_processed is not None else None
    
    if active_tab == unified_label and not df_received_for_approval.empty and df_for_approval is not None:
        st.markdown("---")
        st.markdown("### ⚡ Avaliar Retorno do Armador")
        
        # Criar opções para o selectbox
        approval_options = ["Selecione um PDF para aprovar..."]
        approval_mapping = {}  # Dict para mapear opção -> dados da linha
        
        for idx, row in df_received_for_approval.iterrows():
            inserted_date = row.get('ROW_INSERTED_DATE')
            if inserted_date:
                brazil_time = convert_utc_to_brazil_time(inserted_date)
                if brazil_time and hasattr(brazil_time, 'strftime'):
                    date_str = brazil_time.strftime('%d/%m/%Y %H:%M')
                else:
                    date_str = str(inserted_date)[:16] if inserted_date else 'N/A'
            else:
                date_str = 'N/A'
            
            # Buscar Index da linha no df_for_approval baseado no idx
            # O idx do iterrows() do df_received_for_approval corresponde ao índice original
            # no df_for_approval
            if df_for_approval is not None and idx in df_for_approval.index:
                line_index = df_for_approval.loc[idx, 'Index']
            else:
                line_index = idx
            
            # Formato: Index | Data e hora
            option_text = f"Index {line_index} | {date_str}"
            approval_options.append(option_text)
            approval_mapping[option_text] = row
        
        # Selectbox para escolher PDF
        selected_pdf = st.selectbox(
            "Selecione o retorno do armador para avaliar:",
            options=approval_options,
            key=f"pdf_approval_select_{farol_reference}"
        )
        
        # Se selecionou um PDF, mostrar botões de aprovação
        if selected_pdf != "Selecione um PDF para aprovar...":
            selected_row = approval_mapping[selected_pdf]
            adjustment_id = selected_row['ADJUSTMENT_ID']
            
            # Obter status atual
            selected_row_status = get_return_carrier_status_by_adjustment_id(adjustment_id) or selected_row.get("B_BOOKING_STATUS", "")
            
            st.markdown("#### 🔄 Selecione a Ação:")
            
            # Layout dos botões (mesmo do código atual)
            col1, col2 = st.columns([2, 3])
            
            with col1:
                farol_status = selected_row.get("B_BOOKING_STATUS", "")
                disable_approved = farol_status == "Booking Approved"
                disable_rejected = farol_status == "Booking Rejected"
                disable_cancelled = farol_status == "Booking Cancelled"
                disable_adjustment = farol_status == "Adjustment Requested"
                
                subcol1, subcol2, subcol3, subcol4 = st.columns([1, 1, 1, 1], gap="small")
                
                with subcol1:
                    if st.button("Booking Approved", key=f"status_approved_unified_{farol_reference}", type="secondary", disabled=disable_approved):
                        st.session_state[f"pending_status_change_{farol_reference}"] = "Booking Approved"
                        # Armazenar selected_row no session_state para uso posterior
                        st.session_state[f"selected_row_for_approval_{farol_reference}"] = selected_row
                        st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                        st.rerun()
                
                with subcol2:
                    if st.button("Booking Rejected", key=f"status_rejected_unified_{farol_reference}", type="secondary", disabled=disable_rejected):
                        st.session_state[f"pending_status_change_{farol_reference}"] = "Booking Rejected"
                        st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                        result = update_record_status(adjustment_id, "Booking Rejected")
                        if result:
                            st.session_state["history_flash"] = {"type": "success", "msg": "✅ Status atualizado para 'Booking Rejected'."}
                            st.cache_data.clear()
                            st.rerun()
                
                with subcol3:
                    if st.button("Booking Cancelled", key=f"status_cancelled_unified_{farol_reference}", type="secondary", disabled=disable_cancelled):
                        st.session_state[f"pending_status_change_{farol_reference}"] = "Booking Cancelled"
                        st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                        result = update_record_status(adjustment_id, "Booking Cancelled")
                        if result:
                            st.session_state["history_flash"] = {"type": "success", "msg": "✅ Status atualizado para 'Booking Cancelled'."}
                            st.cache_data.clear()
                            st.rerun()
                
                with subcol4:
                    if st.button("Adjustment Requested", key=f"status_adjustment_unified_{farol_reference}", type="secondary", disabled=disable_adjustment):
                        st.session_state[f"pending_status_change_{farol_reference}"] = "Adjustment Requested"
                        st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                        result = update_record_status(adjustment_id, "Adjustment Requested")
                        if result:
                            st.session_state["history_flash"] = {"type": "success", "msg": "✅ Status atualizado para 'Adjustment Requested'."}
                            st.cache_data.clear()
                            st.rerun()
            
            # Manter seções de voyage manual e seleção de referência da implementação atual
            # (será adicionada nas próximas etapas se necessário)

    # Conteúdo da aba "Histórico de Viagens" 
    if active_tab == voyages_label:
        if df_voyage_monitoring.empty:
            st.info("📋 Nenhum dado de monitoramento encontrado para esta referência.")
        else:
            # Copia dados
            df_monitoring_display = df_voyage_monitoring.copy()

            if not df_monitoring_display.empty:
                # Agrupar por navio/viagem para identificar diferentes viagens
                df_monitoring_display['navio_viagem'] = df_monitoring_display['navio'].astype(str) + " - " + df_monitoring_display['viagem'].astype(str)
                
                # Identificar viagens únicas
                unique_voyages = df_monitoring_display['navio_viagem'].unique()
                
                # Para cada viagem única, mostrar o status atual
                for i, voyage_key in enumerate(unique_voyages):
                    voyage_records = df_monitoring_display[df_monitoring_display['navio_viagem'] == voyage_key]
                    latest_record = voyage_records.iloc[0]  # Mais recente dessa viagem específica
                    
                    # Card para cada viagem - layout mais limpo
                    with st.container():
                        # Função helper para formatar datas
                        def format_date_safe(date_val):
                            if date_val is None:
                                return 'N/A'
                            
                            try:
                                import pandas as pd
                                # Verificar se é NaT (pandas Not a Time)
                                if pd.isna(date_val):
                                    return 'N/A'
                                
                                # Converter UTC para horário do Brasil
                                brazil_time = convert_utc_to_brazil_time(date_val)
                                
                                # Se é um pandas Timestamp válido
                                if hasattr(brazil_time, 'strftime'):
                                    return brazil_time.strftime('%d/%m/%Y %H:%M')
                                
                                # Para outros tipos, converter para string
                                return str(brazil_time)
                            except Exception:
                                return 'N/A'
                        
                        # Função helper para formatar datas já convertidas para horário do Brasil
                        def format_date_safe_brazil(date_val):
                            if date_val is None:
                                return 'N/A'
                            
                            try:
                                import pandas as pd
                                # Verificar se é NaT (pandas Not a Time)
                                if pd.isna(date_val):
                                    return 'N/A'
                                
                                # Se é um pandas Timestamp válido
                                if hasattr(date_val, 'strftime'):
                                    return date_val.strftime('%d/%m/%Y %H:%M')
                                
                                # Para outros tipos, converter para string
                                return str(date_val)
                            except Exception:
                                return 'N/A'
                        
                        # Função helper para formatar origem dos dados
                        def format_source_display(source):
                            if source == 'API':
                                return 'API'
                            elif source == 'MANUAL':
                                return 'Manual'
                            else:
                                return f'{source}'
                        
                        # Layout card expandido mantendo o estilo original
                        st.markdown(f"""
                        <div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; 
                                   padding: 1rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 0.75rem; align-items: center;">
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">✅ Aprovado:</div>
                                    <div style="font-weight: 600; color: #27ae60; font-size: 0.85em;">
                                        {format_date_safe_brazil(latest_record.get('aprovacao_date'))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">✍️ Origem:</div>
                                    <div style="font-weight: 500; color: #34495e; font-size: 0.85em;">
                                        {format_source_display(latest_record.get('DATA_SOURCE', latest_record.get('data_source', 'N/A')))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">🚢 Navio:</div>
                                    <div style="font-weight: 600; color: #2c3e50; font-size: 0.85em;">
                                        {latest_record.get('navio', 'N/A')}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">⚡ Viagem:</div>
                                    <div style="color: #3498db; font-size: 0.85em; font-weight: 500;">
                                        {latest_record.get('viagem', 'N/A')}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">🏗️ Terminal:</div>
                                    <div style="color: #7f8c8d; font-size: 0.85em; font-weight: 500;">
                                        {latest_record.get('terminal', 'N/A')}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">⚓ ETD</div>
                                    <div style="font-weight: 500; color: #34495e; font-size: 0.85em;">
                                        {format_date_safe(latest_record.get('data_estimativa_saida'))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">🛳️ ETA</div>
                                    <div style="font-weight: 500; color: #3498db; font-size: 0.85em;">
                                        {format_date_safe(latest_record.get('data_estimativa_chegada'))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">🚧 Gate</div>
                                    <div style="font-weight: 500; color: #e67e22; font-size: 0.85em;">
                                        {format_date_safe(latest_record.get('data_abertura_gate'))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">📋 Deadline</div>
                                    <div style="font-weight: 500; color: #e74c3c; font-size: 0.85em;">
                                        {format_date_safe(latest_record.get('data_deadline'))}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">📍 Status</div>
                                    <div style="font-weight: 500; color: {'#27ae60' if latest_record.get('data_chegada') else '#f39c12'}; font-size: 0.85em;">
                                        {'🟢 Chegou' if latest_record.get('data_chegada') else '🟡 Em Trânsito'}
                                    </div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.8em; color: #7f8c8d; margin-bottom: 0.1rem; text-transform: uppercase;">🔄 Atualizado</div>
                                    <div style="font-weight: 500; color: #8e44ad; font-size: 0.85em;">
                                        {format_date_safe(latest_record.get('data_atualizacao'))}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Histórico dessa viagem específica em expander
                        voyage_count = len(voyage_records)
                        if voyage_count >= 1:
                            with st.expander(f"📈 Ver histórico ({voyage_count} registros)", expanded=False):
                                st.markdown("#### 🔄 Alterações Detectadas")
                                
                                # Função para detectar alterações
                                def detect_changes(records):
                                    changes = []
                                    # Campos a monitorar
                                    monitored_fields = {
                                        'data_deadline': 'Deadline',
                                        'data_draft_deadline': 'Draft Deadline',
                                        'data_abertura_gate': 'Abertura de Gate',
                                        'data_abertura_gate_reefer': 'Abertura de Gate Reefer', 
                                        'data_estimativa_chegada': 'ETA',
                                        'data_estimativa_saida': 'ETD',
                                        'data_estimativa_atracacao': 'Estimativa Atracação ETB',
                                        'data_atracacao': 'Atracação ATB',
                                        'data_chegada': 'Data de Chegada',
                                        'data_partida': 'Data de Partida'
                                    }
                                    
                                    # Comparar registros consecutivos (do mais novo para o mais antigo)
                                    for i in range(len(records) - 1):
                                        current = records.iloc[i]
                                        previous = records.iloc[i + 1]
                                        
                                        for field, label in monitored_fields.items():
                                            current_val = current.get(field)
                                            previous_val = previous.get(field)
                                            
                                            # Função helper para formatar data
                                            def format_date(val):
                                                import pandas as pd
                                                if val is None or pd.isna(val):
                                                    return "Sem Registro"
                                                
                                                # Converter UTC para horário do Brasil
                                                brazil_time = convert_utc_to_brazil_time(val)
                                                
                                                if hasattr(brazil_time, 'strftime'):
                                                    return brazil_time.strftime('%d/%m/%Y - %H:%M')
                                                return str(brazil_time)
                                            
                                            current_formatted = format_date(current_val)
                                            previous_formatted = format_date(previous_val)
                                            
                                            # Detectar mudança
                                            if current_formatted != previous_formatted:
                                                # Usar horário atual em vez do data_atualizacao do registro
                                                # para mostrar quando a alteração foi detectada
                                                from datetime import datetime
                                                import pytz
                                                
                                                def get_brazil_time():
                                                    brazil_tz = pytz.timezone('America/Sao_Paulo')
                                                    return datetime.now(brazil_tz)
                                                
                                                update_time = get_brazil_time()
                                                
                                                # Função helper para formatar data de atualização
                                                def format_update_time(date_val):
                                                    if date_val is None:
                                                        return 'N/A'
                                                    
                                                    try:
                                                        import pandas as pd
                                                        # Verificar se é NaT (pandas Not a Time)
                                                        if pd.isna(date_val):
                                                            return 'N/A'
                                                        
                                                        # Converter UTC para horário do Brasil
                                                        brazil_time = convert_utc_to_brazil_time(date_val)
                                                        
                                                        # Se é um pandas Timestamp válido
                                                        if hasattr(brazil_time, 'strftime'):
                                                            return brazil_time.strftime('%d/%m/%Y às %H:%M')
                                                        
                                                        # Para outros tipos, converter para string
                                                        return str(brazil_time)
                                                    except Exception:
                                                        return 'N/A'
                                                
                                                update_str = format_update_time(update_time)
                                                
                                                # Obter origem dos dados
                                                current_source = current.get('data_source', current.get('DATA_SOURCE', 'N/A'))
                                                previous_source = previous.get('data_source', previous.get('DATA_SOURCE', 'N/A'))
                                                
                                                # Formatar origem para exibição
                                                def format_source(source):
                                                    if source == 'API':
                                                        return 'API'
                                                    elif source == 'MANUAL':
                                                        return 'Manual'
                                                    else:
                                                        return f'{source}'
                                                
                                                current_source_formatted = format_source(current_source)
                                                previous_source_formatted = format_source(previous_source)
                                                
                                                changes.append({
                                                    'field': label,
                                                    'from': previous_formatted,
                                                    'to': current_formatted,
                                                    'source': current_source_formatted,
                                                    'updated_at': update_str
                                                })
                                    
                                    return changes
                                
                                # Detectar alterações
                                changes = detect_changes(voyage_records)
                                
                                if changes:
                                    for change in changes:
                                        st.markdown(f"""
                                        <div style="padding: 0.5rem; margin: 0.25rem 0; border-left: 3px solid #1f77b4; background-color: #f8f9fa;">
                                            <strong>Alteração de {change['field']}</strong> de <span style="color: #e74c3c; font-weight: 600; background-color: #fdf2f2; padding: 2px 6px; border-radius: 4px;">{change['from']}</span> para <span style="color: #27ae60; font-weight: 600; background-color: #f0f9f0; padding: 2px 6px; border-radius: 4px;">{change['to']}</span><br>
                                            <small>Origem: {change['source']} | Atualizado em {change['updated_at']}</small>
                                        </div>
                                        """, unsafe_allow_html=True)
                                else:
                                    st.info("📝 Nenhuma alteração detectada entre as atualizações")
                                
                                st.markdown("#### 📊 Tabela Completa")
                                # Remover coluna auxiliar antes de exibir
                                voyage_display = voyage_records.drop(columns=['navio_viagem'])
                                # Padroniza rótulos conforme telas principais
                                rename_map_voyage = {
                                    'navio': 'Vessel Name',
                                    'viagem': 'Voyage Code',
                                    'terminal': 'Terminal',
                                    'cnpj_terminal': 'Terminal CNPJ',
                                    'agencia': 'Agência',
                                    'data_source': 'Source',
                                    'data_deadline': 'Deadline',
                                    'data_draft_deadline': 'Draft Deadline',
                                    'data_abertura_gate': 'Abertura Gate',
                                    'data_abertura_gate_reefer': 'Abertura Gate Reefer',
                                    'data_estimativa_saida': 'ETD',
                                    'data_estimativa_chegada': 'ETA',
                                    'data_estimativa_atracacao': 'Estimativa Atracação (ETB)',
                                    'data_atracacao': 'Atracação (ATB)',
                                    'data_partida': 'Partida (ATD)',
                                    'data_chegada': 'Chegada (ATA)',
                                    'data_atualizacao': 'Data Atualização',
                                    'row_inserted_date': 'Inserted Date',
                                }
                                voyage_display = voyage_display.rename(columns=rename_map_voyage)
                                
                                # Formatar coluna Source para exibição
                                if 'Source' in voyage_display.columns:
                                    voyage_display['Source'] = voyage_display['Source'].apply(format_source_display)
                                
                                # Hide ID column
                                id_cols_to_drop = [col for col in voyage_display.columns if col.strip().lower() == 'id']
                                if id_cols_to_drop:
                                    voyage_display = voyage_display.drop(columns=id_cols_to_drop)

                                # Define desired column order, hiding Agência and moving Terminal
                                desired_cols = [
                                    'Source', 'Vessel Name', 'Voyage Code', 'Terminal', 'Deadline', 
                                    'Draft Deadline', 'Abertura Gate', 
                                    'ETD', 'ETA', 
                                    'Estimativa Atracação (ETB)', 'Atracação (ATB)', 'Partida (ATD)', 
                                    'Chegada (ATA)', 'Data Atualização', 'Inserted Date'
                                ]
                                existing_cols = [col for col in desired_cols if col in voyage_display.columns]
                                voyage_display = voyage_display[existing_cols]

                                st.dataframe(voyage_display, use_container_width=True, hide_index=True)
                        
                        # Separador visual entre viagens
                        if i < len(unique_voyages) - 1:
                            st.markdown("---")


    # Conteúdo da aba "Audit Trail"
    if active_tab == audit_label:
        display_audit_trail_tab(farol_reference)

    # Verificar se há PDF selecionado no selectbox
    selected_pdf_option = st.session_state.get(f"pdf_approval_select_{farol_reference}")
    has_pdf_selected = selected_pdf_option and selected_pdf_option != "Selecione um PDF para aprovar..."
    
    # Limpa status pendente quando a seleção muda
    if has_pdf_selected:
        # Obter adjustment_id do PDF selecionado
        current_adjustment_id = st.session_state.get(f"adjustment_id_for_approval_{farol_reference}")
        last_adjustment_id = st.session_state.get(f"last_selected_adjustment_id_{farol_reference}")
        
        if last_adjustment_id is not None and last_adjustment_id != current_adjustment_id:
            # Seleção mudou, limpa status pendente
            if f"pending_status_change_{farol_reference}" in st.session_state:
                del st.session_state[f"pending_status_change_{farol_reference}"]
            # Limpa qualquer gatilho/flag de formulário manual pendente ao trocar a seleção
            if "voyage_manual_entry_required" in st.session_state:
                del st.session_state["voyage_manual_entry_required"]
            # Limpa aviso de sucesso da API
            if "voyage_success_notice" in st.session_state:
                del st.session_state["voyage_success_notice"]
            # Limpa erros de aprovação ou salvamento manual de ações anteriores
            if "approval_error" in st.session_state:
                del st.session_state["approval_error"]
            if "manual_save_error" in st.session_state:
                del st.session_state["manual_save_error"]
            # Limpa possíveis triggers por ajuste anterior
            for k in list(st.session_state.keys()):
                if str(k).startswith("manual_related_ref_value_") or str(k).startswith("manual_trigger_"):
                    try:
                        del st.session_state[k]
                    except Exception:
                        pass
            if "pending_status_change" in st.session_state:
                del st.session_state["pending_status_change"]
            # Ao mudar a seleção, recolhe a seção de anexos
            st.session_state["history_show_attachments"] = False
        
        # Atualiza o ID da seleção atual
        st.session_state[f"last_selected_adjustment_id_{farol_reference}"] = current_adjustment_id
    else:
        # Nenhuma linha selecionada, limpa status e avisos/flags
        if f"pending_status_change_{farol_reference}" in st.session_state:
            del st.session_state[f"pending_status_change_{farol_reference}"]
        if "pending_status_change" in st.session_state:
            del st.session_state["pending_status_change"]
        if f"last_selected_adjustment_id_{farol_reference}" in st.session_state:
            del st.session_state[f"last_selected_adjustment_id_{farol_reference}"]
        if "voyage_manual_entry_required" in st.session_state:
            del st.session_state["voyage_manual_entry_required"]
        if "voyage_success_notice" in st.session_state:
            del st.session_state["voyage_success_notice"]

    # Função para aplicar mudanças de status (declarada antes do uso)
    def apply_status_change(farol_ref, adjustment_id, new_status, selected_row_status=None, related_reference=None, area=None, reason=None, responsibility=None, comment=None):
        try:
            if new_status == "Booking Approved" and selected_row_status == "Received from Carrier":
                # A validação de voyage monitoring agora é feita no botão "Booking Approved"
                # Esta função só executa a aprovação final
                
                # Se chegou até aqui, prosseguir com aprovação normal
                justification = {
                    "area": area,
                    "request_reason": reason,
                    "adjustments_owner": responsibility,
                    "comments": comment
                }
                result = approve_carrier_return(adjustment_id, related_reference, justification)
                if result:
                    st.session_state["history_flash"] = {"type": "success", "msg": "✅ Approval successful!"}
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Falha ao aprovar. Verifique os campos e tente novamente.")
                return
            elif new_status in ["Booking Rejected", "Booking Cancelled", "Adjustment Requested"]:
                result = update_record_status(adjustment_id, new_status)
                if result:
                    st.session_state["history_flash"] = {"type": "success", "msg": f"✅ Status atualizado para '{new_status}'."}
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Não foi possível atualizar o status.")
                return
            else:
                st.warning(f"Status change to '{new_status}' is not handled by this logic yet.")
        except Exception as e:
            st.error(f"❌ Erro inesperado ao aplicar alteração: {str(e)}")
    
    
    # Seção antiga de botões removida - agora integrada na seção do selectbox acima
    # Toda a lógica foi movida para dentro da seção do selectbox na aba unificada

    # Atualizar seção de Export CSV para usar apenas o DataFrame unificado
    if edited_df_unified is not None and not edited_df_unified.empty:
        combined_df = edited_df_unified
    else:
        combined_df = pd.DataFrame()

    # Seção de botões de ação (View Attachments, Export, Back)
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        # Toggle de anexos
        view_open = st.session_state.get("history_show_attachments", False)
        if st.button("📎 View Attachments", key="history_view_attachments"):
            st.session_state["history_show_attachments"] = not view_open
            st.rerun()
    with col2:
        # Export CSV
        if not combined_df.empty:
            st.download_button("⬇️ Export CSV", data=combined_df.to_csv(index=False).encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv")
        else:
            st.download_button("⬇️ Export CSV", data="".encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv", disabled=True)
    with col3:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()

    # Seção de anexos (toggle)
    
    if st.session_state.get("history_show_attachments", False):
        st.markdown("---")
        st.subheader("📎 Attachment Management")
        display_attachments_section(farol_reference)


def display_audit_trail_tab(farol_reference):
    """Exibe a aba Audit Trail com histórico de mudanças"""
    import pandas as pd
    import pytz
    from sqlalchemy import text as _text_audit_tab
    from database import get_database_connection
    
    st.markdown("### 🔍 Audit Trail - Histórico de Mudanças")
    st.markdown(f"**Referência:** `{farol_reference}`")
    st.markdown("---")

    try:
        conn_a = get_database_connection()
        query = _text_audit_tab(
            """
            SELECT 
                EVENT_KIND,
                FAROL_REFERENCE,
                TABLE_NAME,
                COLUMN_NAME,
                OLD_VALUE,
                NEW_VALUE,
                USER_LOGIN,
                CHANGE_SOURCE,
                CHANGE_TYPE,
                ADJUSTMENT_ID,
                RELATED_REFERENCE,
                CHANGE_AT
            FROM LogTransp.V_FAROL_AUDIT_TRAIL
            WHERE FAROL_REFERENCE = :farol_ref
            ORDER BY CHANGE_AT DESC
            """
        )
        df_audit = pd.read_sql(query, conn_a, params={"farol_ref": farol_reference})
        conn_a.close()

        if df_audit.empty:
            st.info("📋 Nenhum registro de auditoria encontrado para esta referência.")
            return

        def _convert_utc_to_brazil_time(ts):
            if ts is None:
                return None
            try:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    utc_dt = ts
                else:
                    utc_dt = pytz.UTC.localize(ts)
                brazil_tz = pytz.timezone('America/Sao_Paulo')
                return utc_dt.astimezone(brazil_tz)
            except Exception:
                return ts

        change_at_col = None
        for c in df_audit.columns:
            if c.upper() == 'CHANGE_AT':
                change_at_col = c
                break
        if change_at_col:
            df_audit[change_at_col] = df_audit[change_at_col].apply(_convert_utc_to_brazil_time)
        else:
            st.error("❌ Coluna CHANGE_AT não encontrada no resultado da query")
            return

        rename_map = {}
        for c in df_audit.columns:
            cu = c.upper()
            if cu == 'EVENT_KIND': rename_map[c] = 'Tipo'
            elif cu == 'FAROL_REFERENCE': rename_map[c] = 'Referência'
            elif cu == 'TABLE_NAME': rename_map[c] = 'Tabela'
            elif cu == 'COLUMN_NAME': rename_map[c] = 'Coluna'
            elif cu == 'OLD_VALUE': rename_map[c] = 'Valor Anterior'
            elif cu == 'NEW_VALUE': rename_map[c] = 'Novo Valor'
            elif cu == 'USER_LOGIN': rename_map[c] = 'Usuário'
            elif cu == 'CHANGE_SOURCE': rename_map[c] = 'Origem'
            elif cu == 'CHANGE_TYPE': rename_map[c] = 'Ação'
            elif cu == 'ADJUSTMENT_ID': rename_map[c] = 'ID Ajuste'
            elif cu == 'RELATED_REFERENCE': rename_map[c] = 'Referência Relacionada'
            elif cu == 'CHANGE_AT': rename_map[c] = 'Data/Hora'

        df_display = df_audit.rename(columns=rename_map)

        def get_friendly_column_name(column_name):
            if not column_name or pd.isna(column_name):
                return column_name
            friendly_mapping = {
                'S_DTHC_PREPAID': 'DTHC',
                'S_REQUESTED_SHIPMENT_WEEK': 'Requested Shipment Week',
                'S_QUANTITY_OF_CONTAINERS': 'Quantity of Containers',
                'S_PORT_OF_LOADING_POL': 'Port of Loading POL',
                'S_TYPE_OF_SHIPMENT': 'Type of Shipment',
                'S_PORT_OF_DELIVERY_POD': 'Port of Delivery POD',
                'S_FINAL_DESTINATION': 'Final Destination',
                'B_DATA_DRAFT_DEADLINE': 'Draft Deadline',
                'B_DATA_DEADLINE': 'Deadline',
                'B_DATA_ESTIMATIVA_SAIDA_ETD': 'ETD',
                'B_DATA_ESTIMATIVA_CHEGADA_ETA': 'ETA',
                'B_DATA_ABERTURA_GATE': 'Abertura Gate',
                'B_DATA_CONFIRMACAO_EMBARQUE': 'Confirmação Embarque',
                'B_DATA_PARTIDA_ATD': 'Partida (ATD)',
                'B_DATA_ESTIMADA_TRANSBORDO_ETD': 'Estimada Transbordo (ETD)',
                'B_DATA_CHEGADA_ATA': 'Chegada (ATA)',
                'B_DATA_TRANSBORDO_ATD': 'Transbordo (ATD)',
                'B_DATA_CHEGADA_DESTINO_ETA': 'Estimativa Chegada Destino (ETA)',
                'B_DATA_CHEGADA_DESTINO_ATA': 'Chegada no Destino (ATA)',
                'B_DATA_ESTIMATIVA_ATRACACAO_ETB': 'Estimativa Atracação (ETB)',
                'B_DATA_ATRACACAO_ATB': 'Atracação (ATB)',
                'B_FREIGHT_RATE_USD': 'Freight Rate USD',
                'B_BOGEY_SALE_PRICE_USD': 'Bogey Sale Price USD',
                'B_FREIGHTPPNL': 'Freight PNL',
                'B_VOYAGE_CARRIER': 'Carrier',
                'B_VESSEL_NAME': 'Vessel Name',
                'B_VOYAGE_CODE': 'Voyage Code',
                'B_TERMINAL': 'Terminal',
                'B_FREIGHT_FORWARDER': 'Freight Forwarder',
                'B_TRANSHIPMENT_PORT': 'Transhipment Port',
                'B_POD_COUNTRY': 'POD Country',
                'B_POD_COUNTRY_ACRONYM': 'POD Country Acronym',
                'B_DESTINATION_TRADE_REGION': 'Destination Trade Region',
                'B_BOOKING_REFERENCE': 'Booking Reference',
                'B_BOOKING_STATUS': 'Booking Status',
                'B_BOOKING_OWNER': 'Booking Owner',
                'S_SALES_ORDER_REFERENCE': 'Sales Order Reference',
                'S_SALES_ORDER_DATE': 'Sales Order Date',
                'S_BUSINESS': 'Business',
                'S_CUSTOMER': 'Customer',
                'S_MODE': 'Mode',
                'S_INCOTERM': 'Incoterm',
                'S_SKU': 'SKU',
                'S_PLANT_OF_ORIGIN': 'Plant of Origin',
                'S_CONTAINER_TYPE': 'Container Type',
                'S_VOLUME_IN_TONS': 'Volume in Tons',
                'S_PARTIAL_ALLOWED': 'Partial Allowed',
                'S_VIP_PNL_RISK': 'VIP PNL Risk',
                'S_PNL_DESTINATION': 'PNL Destination',
                'S_LC_RECEIVED': 'LC Received',
                'S_ALLOCATION_DATE': 'Allocation Date',
                'S_PRODUCER_NOMINATION_DATE': 'Producer Nomination',
                'S_SALES_OWNER': 'Sales Owner',
                'S_COMMENTS': 'Comments Sales',
                'S_PLACE_OF_RECEIPT': 'Place of Receipt',
                'B_COMMENTS': 'Comments Booking',
                'FAROL_STATUS': 'Farol Status',
                'S_CREATION_OF_SHIPMENT': 'Shipment Requested Date',
                'B_CREATION_OF_BOOKING': 'Booking Registered Date',
                'B_BOOKING_REQUEST_DATE': 'Booking Requested Date',
                'B_BOOKING_CONFIRMATION_DATE': 'Booking Confirmation Date',
                'S_REQUESTED_DEADLINES_START_DATE': 'Requested Deadline Start',
                'S_REQUESTED_DEADLINES_END_DATE': 'Requested Deadline End',
                'S_SHIPMENT_PERIOD_START_DATE': 'Shipment Period Start',
                'S_SHIPMENT_PERIOD_END_DATE': 'Shipment Period End',
                'S_REQUIRED_ARRIVAL_DATE_EXPECTED': 'Required Arrival Date',
                'S_AFLOAT': 'Afloat',
                'S_CUSTOMER_PO': 'Customer PO',
                'S_SPLITTED_BOOKING_REFERENCE': 'Splitted Booking Reference',
                'B_QUANTITY_OF_CONTAINERS': 'Booking Quantity of Containers',
                'B_CONTAINER_TYPE': 'Booking Container Type',
                'B_PORT_OF_LOADING_POL': 'Port of Loading POL',
                'B_PORT_OF_DELIVERY_POD': 'Port of Delivery POD',
                'B_FINAL_DESTINATION': 'Final Destination',
                'B_PLACE_OF_RECEIPT': 'Place of Receipt',
                'B_AWARD_STATUS': 'Award Status',
                'ATTACHMENT': 'Anexo'
            }
            return friendly_mapping.get(column_name, column_name)

        if 'Coluna' in df_display.columns:
            df_display['Coluna'] = df_display['Coluna'].apply(get_friendly_column_name)

        if 'Origem' in df_display.columns:
            origin_mapping = {
                'booking_new': 'Tela de Criação de Booking',
                'shipments_new': 'Criação do Shipment',
                'tracking': 'Tela de Tracking',
                'history': 'Tela de Aprovação de PDF',
                'attachments': 'Tela de Anexos (Upload/Exclusão)',
                'shipments': 'Tela Principal de Shipments',
                'shipments_split': 'Tela de Ajustes e Split',
                'Booking Requested': 'Timeline Inicial',
                'Other Request - Company': 'Timeline Inicial',
                'Adjusts Cargill': 'Timeline Inicial'
            }
            df_display['Origem'] = df_display['Origem'].replace(origin_mapping)

        if 'Valor Anterior' in df_display.columns:
            df_display['Valor Anterior'] = df_display['Valor Anterior'].replace('NULL', '')
        if 'Novo Valor' in df_display.columns:
            df_display['Novo Valor'] = df_display['Novo Valor'].replace('NULL', '')

        column_order = [
            'Referência', 'Ação', 'Coluna', 'Valor Anterior', 'Novo Valor',
            'Usuário', 'Origem', 'Data/Hora'
        ]
        available_columns = [c for c in column_order if c in df_display.columns]
        df_display = df_display[available_columns]

        df_display = df_display[
            ~(
                df_display['Origem'].str.contains('Timeline Inicial|Request - Company|Adjusts Cargill', na=False)
            )
        ]

        c1, c2, c3 = st.columns(3)
        with c1:
            origins = ['Todos'] + sorted(df_display['Origem'].dropna().unique().tolist())
            selected_origin = st.selectbox("🔍 Filtrar por Origem", origins)
        with c2:
            actions = ['Todos'] + sorted(df_display['Ação'].dropna().unique().tolist())
            selected_action = st.selectbox("🔍 Filtrar por Ação", actions)
        with c3:
            columns = ['Todas'] + sorted(df_display['Coluna'].dropna().unique().tolist())
            selected_column = st.selectbox("🔍 Filtrar por Coluna", columns)

        df_filtered = df_display.copy()
        if selected_origin != 'Todos':
            df_filtered = df_filtered[df_filtered['Origem'] == selected_origin]
        if selected_action != 'Todos':
            df_filtered = df_filtered[df_filtered['Ação'] == selected_action]
        if selected_column != 'Todas':
            df_filtered = df_filtered[df_filtered['Coluna'] == selected_column]

        df_filtered = df_filtered.sort_values('Data/Hora', ascending=False)

        st.markdown(f"**📊 Total de registros:** {len(df_filtered)} de {len(df_display)}")
        if not df_filtered.empty:
            column_config = {
                'Data/Hora': st.column_config.DatetimeColumn('Data/Hora', format='DD/MM/YYYY HH:mm:ss', width=None),
                'Usuário': st.column_config.TextColumn('Usuário', width=None),
                'Origem': st.column_config.TextColumn('Origem', width='medium'),
                'Ação': st.column_config.TextColumn('Ação', width=None),
                'Coluna': st.column_config.TextColumn('Coluna', width='medium', help='Nome da coluna alterada'),
                'Valor Anterior': st.column_config.TextColumn('Valor Anterior', width=None),
                'Novo Valor': st.column_config.TextColumn('Novo Valor', width=None),
            }
            st.dataframe(
                df_filtered,
                column_config=column_config,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            csv_data = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Exportar CSV",
                data=csv_data,
                file_name=f"audit_trail_{farol_reference}.csv",
                mime="text/csv"
            )
        else:
            st.info("📋 Nenhum registro encontrado com os filtros aplicados.")
    except Exception as e:
        st.error(f"❌ Erro ao carregar audit trail: {str(e)}")
