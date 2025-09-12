import streamlit as st
import pandas as pd
from database import (
    get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, 
    get_database_connection, get_current_status_from_main_table, 
    get_return_carrier_status_by_adjustment_id, get_terminal_monitorings,
    approve_carrier_return, update_record_status
)
from shipments_mapping import get_column_mapping
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

def format_linked_reference_display(linked_ref, farol_ref=None):
    """
    Formata Linked Reference para exibição amigável na UI.
    Exemplos:
    - "FR_25.09_0001-R01" -> "Request #01 (FR_25.09_0001)"
    - "New Adjustment" -> "New Adjustment"
    - "123" -> "Global Request #123"
    - None/NULL -> "🔄 Pending Assignment" (para registros antigos)
    """
    if not linked_ref or str(linked_ref).strip() == "" or str(linked_ref).upper() == "NULL":
        # Para registros antigos sem Linked Reference, oferece opção de auto-assignment
        if farol_ref:
            return f"🔄 Auto-assign Next ({farol_ref})"
        return "🔄 Pending Assignment"
    
    linked_ref_str = str(linked_ref)
    
    if linked_ref_str == "New Adjustment":
        return "🆕 New Adjustment"
    
    # Formato hierárquico: FR_25.09_0001-R01
    if "-R" in linked_ref_str:
        parts = linked_ref_str.split("-R")
        if len(parts) == 2:
            farol_part = parts[0]
            request_num = parts[1]
            return f"📋 Request #{request_num} ({farol_part})"
    
    # Formato numérico simples (legacy)
    if linked_ref_str.isdigit():
        return f"📋 Global Request #{linked_ref_str}"
    
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
        # Usa UPPER para busca case-insensitive
        placeholders = ", ".join([f":vessel_{i}" for i in range(len(vessel_names))])
        monitoring_query = text(f"""
            SELECT *
            FROM F_ELLOX_TERMINAL_MONITORINGS
            WHERE UPPER(NAVIO) IN ({placeholders})
            ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
        """)
        
        # Prepara parâmetros com nomes em maiúsculas para busca
        params = {f"vessel_{i}": vessel_name.upper() for i, vessel_name in enumerate(vessel_names)}
        
        result = conn.execute(monitoring_query, params).mappings().fetchall()
        conn.close()
        
        df = pd.DataFrame([dict(r) for r in result]) if result else pd.DataFrame()
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        return pd.DataFrame()


def get_available_references_for_relation():
    """Busca referências originais (não-split) na aba 'Other Status' para relacionamento"""
    try:
        conn = get_database_connection()
        query = text("""
            SELECT ID, FAROL_REFERENCE, B_BOOKING_STATUS, ROW_INSERTED_DATE, Linked_Reference
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE B_BOOKING_STATUS != 'Received from Carrier'
              AND NVL(S_SPLITTED_BOOKING_REFERENCE, '##NULL##') = '##NULL##' -- apenas originais
              AND NOT REGEXP_LIKE(FAROL_REFERENCE, '\\.\\d+$')             -- exclui refs com sufixo .n
            ORDER BY ROW_INSERTED_DATE DESC
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
            if st.button("🔍 Process Booking PDF", key=f"process_booking_{farol_reference}", type="primary"):
                with st.spinner("🔄 Processando PDF e extraindo dados..."):
                    try:
                        # Reseta o ponteiro do arquivo
                        uploaded_file.seek(0)
                        pdf_content = uploaded_file.read()
                        
                        # Processa o PDF
                        processed_data = process_pdf_booking(pdf_content, farol_reference)
                        
                        if processed_data:
                            # Armazena os dados processados no session_state para validação
                            st.session_state[f"processed_pdf_data_{farol_reference}"] = processed_data
                            st.session_state[f"booking_pdf_file_{farol_reference}"] = uploaded_file
                            
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
    st.subheader("Attachments")

    if not attachments_df.empty:
        # Ordena por data/hora (mais recente primeiro)
        dfv = attachments_df.sort_values('upload_date', ascending=False).reset_index(drop=True)

        # Cabeçalho
        h1, h2, h3, h4, h5, h6 = st.columns([5, 2, 2, 2, 1, 1])
        h1.markdown("**File**")
        h2.markdown("**Type/Ext**")
        h3.markdown("**User**")
        h4.markdown("**Date**")
        h5.markdown("**Download**")
        h6.markdown("**Delete**")

        # Linhas
        for row_index, (_, att) in enumerate(dfv.iterrows()):
            row_key = f"{farol_reference}_{att['id']}_{row_index}"
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

            # Barra de confirmação em linha separada e largura total
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
    st.header("📜 Return Carriers History")
    
    # Botão para atualizar registros antigos sem Linked Reference
    col_update, col_spacer = st.columns([3, 7])
    with col_update:
        if st.button("🔄 Update Missing Linked References", help="Atualiza registros antigos que não têm Linked Reference definido"):
            with st.spinner("Atualizando registros..."):
                updated_count = update_missing_linked_references()
                if updated_count > 0:
                    st.success(f"✅ {updated_count} registros atualizados com sucesso!")
                    st.rerun()
                else:
                    st.info("ℹ️ Todos os registros já possuem Linked Reference definido.")
    
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
    def get_main_table_data(farol_ref):
        """Busca dados específicos da tabela principal F_CON_SALES_BOOKING_DATA"""
        try:
            conn = get_database_connection()
            # Usando os mesmos nomes de coluna das outras funções que funcionam
            query = text("""
                SELECT 
                    S_QUANTITY_OF_CONTAINERS,
                    B_VOYAGE_CARRIER,
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
    
    main_data = get_main_table_data(farol_reference)
    
    if main_data:
        # Dados da tabela principal - usando as chaves corretas (minúsculas)
        voyage_carrier = str(main_data.get("b_voyage_carrier", "-"))
        
        qty = main_data.get("s_quantity_of_containers", 0)
        try:
            qty = int(qty) if qty is not None and pd.notna(qty) else 0
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
        "FAROL_REFERENCE",
        "B_BOOKING_REFERENCE",
        "LINKED_REFERENCE",
        "B_BOOKING_STATUS",
        "S_SPLITTED_BOOKING_REFERENCE",
        "S_PLACE_OF_RECEIPT",
        "S_QUANTITY_OF_CONTAINERS",
        "S_PORT_OF_LOADING_POL",
        "S_PORT_OF_DELIVERY_POD",
        "S_FINAL_DESTINATION",
        "B_TRANSHIPMENT_PORT",
        "B_TERMINAL",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_VOYAGE_CODE",
        "B_DATA_DRAFT_DEADLINE",
        "B_DATA_DEADLINE",
        "B_DATA_ESTIMATIVA_SAIDA_ETD",
        "B_DATA_ESTIMATIVA_CHEGADA_ETA",
        "B_DATA_ABERTURA_GATE",
        "B_DATA_PARTIDA_ATD",
        "B_DATA_CHEGADA_ATA",
        "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "B_DATA_ATRACACAO_ATB",
        "P_STATUS",
        "P_PDF_NAME",
        "PDF_BOOKING_EMISSION_DATE",
        "ROW_INSERTED_DATE",
        "ADJUSTMENTS_OWNER",
    ]

    # Inclui ADJUSTMENT_ID nos dados para funcionalidade interna
    internal_cols = display_cols + ["ADJUSTMENT_ID"]
    df_show = df[[c for c in internal_cols if c in df.columns]].copy()
    
    # Aplica ordenação por Inserted Date antes de separar em abas
    if "ROW_INSERTED_DATE" in df_show.columns:
        # Ordenação primária por data inserida (mais antigo → mais novo)
        # Critério secundário estável: raiz da Farol Reference e sufixo numérico (.1, .2, ...)
        if "FAROL_REFERENCE" in df_show.columns:
            refs_base = df_show["FAROL_REFERENCE"].astype(str)
            df_show["__ref_root"] = refs_base.str.split(".").str[0]
            df_show["__ref_suffix_num"] = (
                refs_base.str.extract(r"\.(\d+)$")[0].fillna(0).astype(int)
            )
            df_show = df_show.sort_values(
                by=["ROW_INSERTED_DATE", "__ref_root", "__ref_suffix_num"],
                ascending=[True, True, True],
                kind="mergesort",
            )
            df_show = df_show.drop(columns=["__ref_root", "__ref_suffix_num"])  # limpeza
        else:
            df_show = df_show.sort_values(by=["ROW_INSERTED_DATE"], ascending=[True], kind="mergesort")
    
    # Adiciona coluna de seleção ao df_display
    df_display = df_show.copy()
    df_display.insert(0, "Selecionar", False)
    
    # Separa os dados em duas abas baseado no status
    df_other_status = df_display[df_display["B_BOOKING_STATUS"] != "Received from Carrier"].copy()
    df_received_carrier = df_display[df_display["B_BOOKING_STATUS"] == "Received from Carrier"].copy()
    
    # Rótulos das "abas"
    other_label = f"📋 Request Timeline ({len(df_other_status)} records)"
    received_label = f"📨 Returns Awaiting Review ({len(df_received_carrier)} records)"
    
    # Busca dados de monitoramento relacionados aos navios desta referência
    df_voyage_monitoring = get_voyage_monitoring_for_reference(farol_reference)

    # Diagnóstico rápido da API Voyage Timeline para a referência atual
    with st.expander("🛠️ Diagnóstico - API Voyage Timeline", expanded=False):
        # Último registro em F_CON_RETURN_CARRIERS
        try:
            latest_rc = df.sort_values("ROW_INSERTED_DATE", ascending=False).iloc[0]
        except Exception:
            latest_rc = None

        if latest_rc is not None:
            vname = str(latest_rc.get("B_VESSEL_NAME", "")).strip()
            vcode = str(latest_rc.get("B_VOYAGE_CODE", "")).strip()
            terminal_name = str(latest_rc.get("B_TERMINAL", "")).strip()
            st.markdown("**Último registro em F_CON_RETURN_CARRIERS (resumo):**")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text(f"Vessel Name: {vname or '-'}")
                st.text(f"Voyage Code: {vcode or '-'}")
            with c2:
                st.text(f"Port Terminal City: {terminal_name or '-'}")
                st.text(f"Status: {latest_rc.get('B_BOOKING_STATUS', '-')}")
            with c3:
                st.text(f"Inserted: {latest_rc.get('ROW_INSERTED_DATE', '-')}")

            # Contagem atual em F_ELLOX_TERMINAL_MONITORINGS
            try:
                conn = get_database_connection()
                cnt = conn.execute(text("""
                    SELECT COUNT(*) FROM F_ELLOX_TERMINAL_MONITORINGS 
                    WHERE UPPER(NAVIO) = UPPER(:vname)
                """), {"vname": vname}).scalar() or 0
                conn.close()
            except Exception:
                cnt = 0

            st.info(f"Registros em F_ELLOX_TERMINAL_MONITORINGS para NAVIO='{vname}': {cnt}")

            # Botão para coletar/atualizar monitoramento agora
            col_a, col_b = st.columns([1, 3])
            with col_a:
                if st.button("🔄 Coletar/Atualizar Voyage Monitoring agora", key=f"collect_vm_{farol_reference}"):
                    try:
                        from pdf_booking_processor import collect_voyage_monitoring_data
                        collect_voyage_monitoring_data(vname, terminal_name, vcode)
                        st.success("✅ Solicitação de coleta enviada. Reabra este diagnóstico em alguns segundos.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Falha ao acionar coleta: {str(e)}")
        else:
            st.info("Nenhum registro em F_CON_RETURN_CARRIERS para diagnóstico.")
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

    # Controle de "aba" ativa (segmented control) para detectar troca e limpar seleções da outra
    active_tab_key = f"history_active_tab_{farol_reference}"
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    if active_tab_key not in st.session_state:
        st.session_state[active_tab_key] = other_label
        st.session_state[last_active_tab_key] = other_label

    active_tab = st.segmented_control(
        "",
        options=[other_label, received_label, voyages_label],
        key=active_tab_key
    )

    # Se detectarmos troca de aba, acionamos flags para limpar seleções da outra
    prev_tab = st.session_state.get(last_active_tab_key)
    if prev_tab != active_tab:
        if active_tab == other_label:
            # Limpamos seleção das outras abas
            st.session_state[f"clear_received_selection_{farol_reference}"] = True
            st.session_state[f"clear_voyages_selection_{farol_reference}"] = True
        elif active_tab == received_label:
            # Limpamos seleção das outras abas
            st.session_state[f"clear_other_selection_{farol_reference}"] = True
            st.session_state[f"clear_voyages_selection_{farol_reference}"] = True
        else:  # voyages_label
            # Limpamos seleção das outras abas
            st.session_state[f"clear_other_selection_{farol_reference}"] = True
            st.session_state[f"clear_received_selection_{farol_reference}"] = True
        st.session_state[last_active_tab_key] = active_tab

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
            "B_BOOKING_STATUS": "Farol Status",
            "ROW_INSERTED_DATE": "Inserted Date",
            "ADJUSTMENTS_OWNER": "Adjustments Owner",
            "B_DATA_ABERTURA_GATE": "Data Abertura Gate",
            "P_STATUS": "Status",
            "P_PDF_NAME": "PDF Name",
            "S_QUANTITY_OF_CONTAINERS": "Quantity of Containers",
            "S_SPLITTED_BOOKING_REFERENCE": "Splitted Farol Reference",
            "B_DATA_DRAFT_DEADLINE": "Data Draft Deadline",
            "B_DATA_DEADLINE": "Data Deadline",
            "B_DATA_ESTIMATIVA_SAIDA_ETD": "Data Estimativa Saída ETD",
            "B_DATA_ESTIMATIVA_CHEGADA_ETA": "Data Estimativa Chegada ETA",
            "B_VOYAGE_CODE": "Voyage Code",
            "B_VESSEL_NAME": "Vessel Name",
            "B_VOYAGE_CARRIER": "Voyage Carrier",
            "B_TRANSHIPMENT_PORT": "Transhipment Port",
            "B_TERMINAL": "Port Terminal City",
            "S_PORT_OF_LOADING_POL": "Port of Loading POL",
            "S_PORT_OF_DELIVERY_POD": "Port of Delivery POD",
        }

        # Aplica aliases ao DataFrame
        rename_map = {}
        for col in df_to_process.columns:
            rename_map[col] = custom_overrides.get(col, mapping_upper.get(col, prettify(col)))
        
        df_processed = df_to_process.copy()
        df_processed.rename(columns=rename_map, inplace=True)

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
        
        # Adiciona ícones na coluna de Status (origem do ajuste), com prioridade:
        # 1) Linhas de Split → "📄 Split"
        # 2) Linked Reference presente → "🚢 Carrier Return (Linked|New Adjustment)"
        # 3) P_STATUS categorizado → "🛠️ Adjusts (Cargill)" / "🚢 Adjusts Carrier" / fallback
        try:
            has_status = "Status" in df_processed.columns
            has_linked = "Linked Reference" in df_processed.columns
            has_splitcol = "Splitted Farol Reference" in df_processed.columns
            if has_status:
                def _render_status_row(row):
                    # Se for split, mostrar informação reduzida (via coluna explícita ou pelo padrão .n)
                    if has_splitcol:
                        split_val = row.get("Splitted Farol Reference")
                        if split_val is not None:
                            split_str = str(split_val).strip()
                            if split_str and split_str.upper() != "NULL":
                                return "📄 Split Info"
                    fr_val = row.get("Farol Reference")
                    if fr_val is not None:
                        fr_str = str(fr_val).strip()
                        if "." in fr_str:
                            last_part = fr_str.split(".")[-1]
                            if last_part.isdigit():
                                return "📄 Split"
                    # Se há Linked Reference, indicar retorno do carrier
                    if has_linked:
                        linked = row.get("Linked Reference")
                        if linked is not None:
                            linked_str = str(linked).strip()
                            if linked_str and linked_str.upper() != "NULL":
                                if linked_str == "New Adjustment":
                                    return "🚢 Carrier Return (New Adjustment)"
                                return "🚢 Carrier Return (Linked)"
                    # Caso contrário, usar origem padrão
                    val = row.get("Status")
                    try:
                        txt = str(val).strip() if val is not None else ""
                    except Exception:
                        txt = ""
                    if not txt:
                        return "⚙️"
                    low = txt.lower()
                    if low == "adjusts cargill":
                        return "🛠️ Adjusts (Cargill)"
                    if low == "adjusts carrier":
                        return "🚢 Adjusts Carrier"
                    return f"⚙️ {txt}"
                df_processed["Status"] = df_processed.apply(_render_status_row, axis=1)
        except Exception:
            pass
        
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
            "Inserted Date", "Data Draft Deadline", "Data Deadline", 
            "Data Estimativa Saída ETD", "Data Estimativa Chegada ETA", "PDF Booking Emission Date"
        ]
        for col in date_cols:
            if col in df_processed.columns:
                df_processed[col] = pd.to_datetime(df_processed[col], errors='coerce')

        # Ordena por Inserted Date e, dentro do mesmo dia/hora, por raiz e sufixo da Farol Reference
        if "Inserted Date" in df_processed.columns:
            if "Farol Reference" in df_processed.columns:
                refs_base = df_processed["Farol Reference"].astype(str)
                df_processed["__ref_root"] = refs_base.str.split(".").str[0]
                df_processed["__ref_suffix_num"] = (
                    refs_base.str.extract(r"\.(\d+)$")[0].fillna(0).astype(int)
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
                        df_processed.loc[first_idx_sel, "Status"] = "📦 Cargill Booking Request"
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
                                # SOBRESCREVE qualquer Status anterior (incluindo "Split Info")
                                df_processed.loc[i, "Status"] = "📦 Cargill Booking Request"
                    else:
                        # SOBRESCREVE qualquer Status anterior (incluindo "Split Info")
                        df_processed.loc[idx_first, "Status"] = "📦 Cargill Booking Request"
        except Exception:
            pass

        # Força: a PRIMEIRA linha da referência atualmente selecionada recebe "📦 Cargill Booking Request"
        try:
            if "Farol Reference" in df_processed.columns and "Inserted Date" in df_processed.columns and farol_reference is not None:
                sel_ref_str = str(farol_reference)
                mask_same_ref = df_processed["Farol Reference"].astype(str) == sel_ref_str
                if mask_same_ref.any():
                    first_idx_any = df_processed.loc[mask_same_ref].sort_values("Inserted Date").index[0]
                    df_processed.loc[first_idx_any, "Status"] = "📦 Cargill Booking Request"
        except Exception:
            pass
                
        return df_processed

    # Conteúdo da "aba" Pedidos da Empresa
    df_other_processed = display_tab_content(df_other_status, "Pedidos da Empresa")
    edited_df_other = None
    if df_other_processed is not None and active_tab == other_label:
        column_config = {
            "ADJUSTMENT_ID": None, # Oculta a coluna
            "Selecionar": st.column_config.CheckboxColumn("Select", help="Selecione apenas uma linha para aplicar mudanças", pinned="left"),
        }
        edited_df_other = st.data_editor(
            df_other_processed,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=df_other_processed.columns.drop(["Selecionar"]),
            key=f"history_other_status_editor_{farol_reference}"
        )

    # Conteúdo da "aba" Retornos do Armador
    df_received_processed = display_tab_content(df_received_carrier, "Retornos do Armador")
    edited_df_received = None
    if df_received_processed is not None and active_tab == received_label:
        column_config = {
            "ADJUSTMENT_ID": None, # Oculta a coluna
            "Selecionar": st.column_config.CheckboxColumn("Select", help="Selecione apenas uma linha para aplicar mudanças", pinned="left"),
        }
        edited_df_received = st.data_editor(
            df_received_processed,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=df_received_processed.columns.drop(["Selecionar"]),
            key=f"history_received_carrier_editor_{farol_reference}"
        )

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
                            if date_val and hasattr(date_val, 'strftime'):
                                return date_val.strftime('%d/%m/%Y %H:%M')
                            elif date_val:
                                return str(date_val)
                            return 'N/A'
                        
                        # Layout card expandido mantendo o estilo original
                        st.markdown(f"""
                        <div style="background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; 
                                   padding: 1rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr; gap: 0.75rem; align-items: center;">
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
                        if voyage_count > 1:
                            with st.expander(f"📈 Ver histórico ({voyage_count} registros)", expanded=False):
                                st.markdown("#### 🔄 Alterações Detectadas")
                                
                                # Função para detectar alterações
                                def detect_changes(records):
                                    changes = []
                                    # Campos a monitorar
                                    monitored_fields = {
                                        'data_deadline': 'Deadline',
                                        'data_abertura_gate': 'Abertura de Gate',
                                        'data_abertura_gate_reefer': 'Abertura de Gate Reefer', 
                                        'data_estimativa_chegada': 'ETA',
                                        'data_estimativa_saida': 'ETD',
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
                                                if hasattr(val, 'strftime'):
                                                    return val.strftime('%d/%m/%Y - %H:%M')
                                                return str(val)
                                            
                                            current_formatted = format_date(current_val)
                                            previous_formatted = format_date(previous_val)
                                            
                                            # Detectar mudança
                                            if current_formatted != previous_formatted:
                                                update_time = current.get('data_atualizacao')
                                                if hasattr(update_time, 'strftime'):
                                                    update_str = update_time.strftime('%d/%m/%Y às %H:%M')
                                                else:
                                                    update_str = str(update_time)
                                                
                                                changes.append({
                                                    'field': label,
                                                    'from': previous_formatted,
                                                    'to': current_formatted,
                                                    'updated_at': update_str
                                                })
                                    
                                    return changes
                                
                                # Detectar alterações
                                changes = detect_changes(voyage_records)
                                
                                if changes:
                                    for change in changes:
                                        st.markdown(f"""
                                        <div style="padding: 0.5rem; margin: 0.25rem 0; border-left: 3px solid #1f77b4; background-color: #f8f9fa;">
                                            <strong>Alteração de {change['field']}</strong> de <em>{change['from']}</em> para <em>{change['to']}</em><br>
                                            <small>Atualizado em {change['updated_at']}</small>
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
                                    'data_deadline': 'Data Deadline',
                                    'data_draft_deadline': 'Data Draft Deadline',
                                    'data_abertura_gate': 'Data Abertura Gate',
                                    'data_abertura_gate_reefer': 'Data Abertura Gate Reefer',
                                    'data_estimativa_saida': 'Data Estimativa Saída ETD',
                                    'data_estimativa_chegada': 'Data Estimativa Chegada ETA',
                                    'data_estimativa_atracacao': 'Data Estimativa Atracação ETB',
                                    'data_atracacao': 'Data Atracação ATB',
                                    'data_partida': 'Data Partida ATD',
                                    'data_chegada': 'Data Chegada ATA',
                                    'data_atualizacao': 'Data Atualização',
                                    'row_inserted_date': 'Inserted Date',
                                }
                                voyage_display = voyage_display.rename(columns=rename_map_voyage)
                                st.dataframe(voyage_display, use_container_width=True, hide_index=True)
                        
                        # Separador visual entre viagens
                        if i < len(unique_voyages) - 1:
                            st.markdown("---")


    # Determina qual DataFrame usar baseado na aba ativa
    if edited_df_other is not None and not edited_df_other.empty:
        selected = edited_df_other[edited_df_other["Selecionar"] == True]
    elif edited_df_received is not None and not edited_df_received.empty:
        selected = edited_df_received[edited_df_received["Selecionar"] == True]
    else:
        selected = pd.DataFrame()

    # Função para aplicar mudanças de status (declarada antes do uso)
    def apply_status_change(farol_ref, adjustment_id, new_status, selected_row_status=None, related_reference=None, area=None, reason=None, responsibility=None, comment=None):
        if new_status == "Booking Approved" and selected_row_status == "Received from Carrier":
            justification = {
                            "area": area,
                            "request_reason": reason,
                            "adjustments_owner": responsibility,
                "comments": comment
            }
            if approve_carrier_return(adjustment_id, related_reference, justification):
                st.success("✅ Approval successful!")
            st.cache_data.clear()
            st.rerun()
        elif new_status in ["Booking Rejected", "Booking Cancelled", "Adjustment Requested"]:
            if update_record_status(adjustment_id, new_status):
                st.cache_data.clear()
            st.rerun()
        else:
            st.warning(f"Status change to '{new_status}' is not handled by this logic yet.")
    
    
    # Interface de botões de status para linha selecionada
    if len(selected) == 1:
        st.markdown("---")

        # Obtém informações da linha selecionada
        selected_row = selected.iloc[0]
        farol_ref = selected_row.get("Farol Reference")
        adjustment_id = selected_row["ADJUSTMENT_ID"]
        
        # Obtém o status da linha selecionada na tabela F_CON_RETURN_CARRIERS (prioriza leitura por UUID)
        selected_row_status = get_return_carrier_status_by_adjustment_id(adjustment_id) or selected_row.get("Farol Status", "")
        
        # Botões de status com layout elegante
        st.markdown("#### 🔄 Select New Status:")
        
        # Botões de status alinhados à esquerda
        col1, col2 = st.columns([2, 3])
        
        with col1:
            # Botões de status com espaçamento reduzido
            subcol1, subcol2, subcol3, subcol4 = st.columns([1, 1, 1, 1], gap="small")
            
            with subcol1:
                if st.button("Booking Approved", 
                            key="status_booking_approved",
                            type="secondary"):
                    st.session_state["pending_status_change"] = "Booking Approved"
                    st.rerun()
            
            with subcol2:
                if st.button("Booking Rejected", 
                            key="status_booking_rejected",
                            type="secondary"):
                    st.session_state["pending_status_change"] = "Booking Rejected"
                    st.rerun()

            with subcol3:
                if st.button("Booking Cancelled", 
                            key="status_booking_cancelled",
                            type="secondary"):
                    st.session_state["pending_status_change"] = "Booking Cancelled"
                    st.rerun()
            
            with subcol4:
                if st.button("Adjustment Requested", 
                            key="status_adjustment_requested",
                            type="secondary"):
                    st.session_state["pending_status_change"] = "Adjustment Requested"
                    st.rerun()
            
        # Confirmação quando há status pendente
        pending_status = st.session_state.get("pending_status_change")
        if pending_status:
            st.markdown("---")
            st.warning(f"**Confirmar alteração para:** {pending_status}")
            
            # Validação especial para itens "Received from Carrier" sendo aprovados
            related_reference = None
            if selected_row_status == "Received from Carrier" and pending_status == "Booking Approved":
                st.info("📋 **Este item é um retorno do armador. Antes de aprovar, informe a referência da aba relacionada:**")
                
                # Busca referências disponíveis na aba 'Other Status'
                available_refs = get_available_references_for_relation()
                
                if available_refs:
                    # Cria opções para o selectbox com formato limpo
                    ref_options = []
                    for ref in available_refs:
                        # Formata a data de inserção com hora e minuto
                        inserted_date = ref.get('ROW_INSERTED_DATE', '')
                        if inserted_date and hasattr(inserted_date, 'strftime'):
                            date_str = inserted_date.strftime('%d/%m/%Y %H:%M')
                        else:
                            # Para strings, tenta extrair data e hora
                            date_str_raw = str(inserted_date) if inserted_date else ''
                            if len(date_str_raw) >= 16:  # YYYY-MM-DD HH:MM:SS ou similar
                                try:
                                    # Converte formato YYYY-MM-DD HH:MM:SS para DD/MM/YYYY HH:MM
                                    parts = date_str_raw[:16].replace(' ', 'T').split('T')
                                    if len(parts) == 2:
                                        date_part = parts[0].split('-')
                                        time_part = parts[1][:5]  # HH:MM
                                        if len(date_part) == 3:
                                            date_str = f"{date_part[2]}/{date_part[1]}/{date_part[0]} {time_part}"
                                        else:
                                            date_str = date_str_raw[:16]
                                    else:
                                        date_str = date_str_raw[:16]
                                except:
                                    date_str = date_str_raw[:16] if len(date_str_raw) >= 16 else 'N/A'
                            else:
                                date_str = 'N/A'
                        
                        option_text = f"{ref['FAROL_REFERENCE']} | {ref['B_BOOKING_STATUS']} | {date_str}"
                        ref_options.append(option_text)
                    
                    ref_options.insert(0, "Selecione uma referência...")
                    ref_options.append("🆕 New Adjustment")  # Opção para ajuste sem referência prévia
                    
                    selected_ref = st.selectbox(
                        "Selecione a linha relacionada da aba 'Other Status' ou 'New Adjustment':",
                        options=ref_options,
                        key="related_reference_select"
                    )
                    
                    if selected_ref and selected_ref != "Selecione uma referência...":
                        if selected_ref == "🆕 New Adjustment":
                            related_reference = "New Adjustment"
                            st.info("🆕 **New Adjustment selecionado:** Este é um ajuste do carrier sem referência prévia da empresa.")
                            
                            # Campos de justificativa obrigatórios para New Adjustment
                            st.markdown("#### 📋 Justificativas do New Adjustment")
                            col_a, col_b, col_c = st.columns([1, 1, 1])
                            with col_a:
                                area_new_adj = st.selectbox("Booking Adjustment Area", [""].extend(Booking_adj_area), key="area_new_adjustment")
                            with col_b:
                                reason_new_adj = st.selectbox("Booking Adjustment Request Reason", [""].extend(Booking_adj_reason), key="reason_new_adjustment")
                            with col_c:
                                responsibility_new_adj = st.selectbox("Booking Adjustment Responsibility", [""].extend(Booking_adj_responsibility), key="responsibility_new_adjustment")
                            
                            comment_new_adj = st.text_area("Comentários", key="comment_new_adjustment")
                            
                            # Armazena os valores no session_state para usar na confirmação
                            st.session_state["new_adjustment_area"] = area_new_adj
                            st.session_state["new_adjustment_reason"] = reason_new_adj
                            st.session_state["new_adjustment_responsibility"] = responsibility_new_adj
                            st.session_state["new_adjustment_comment"] = comment_new_adj
                        else:
                            # Extrai a Farol Reference da opção selecionada (formato limpo)
                            # Formato: "FR_25.09_0001 | Booking Requested | 12/09/2025"
                            farol_ref_from_selection = selected_ref.split(" | ")[0]
                            
                            # Busca o registro correspondente pela Farol Reference
                            selected_ref_data = next((ref for ref in available_refs if ref['FAROL_REFERENCE'] == farol_ref_from_selection), None)
                            if selected_ref_data:
                                # Salva a string completa como Linked Reference
                                related_reference = selected_ref
                                
                                # Formata a data para exibição com hora e minuto
                                inserted_date = selected_ref_data.get('ROW_INSERTED_DATE', '')
                                if inserted_date and hasattr(inserted_date, 'strftime'):
                                    date_str = inserted_date.strftime('%d/%m/%Y %H:%M')
                                else:
                                    # Para strings, tenta extrair data e hora
                                    date_str_raw = str(inserted_date) if inserted_date else ''
                                    if len(date_str_raw) >= 16:  # YYYY-MM-DD HH:MM:SS ou similar
                                        try:
                                            # Converte formato YYYY-MM-DD HH:MM:SS para DD/MM/YYYY HH:MM
                                            parts = date_str_raw[:16].replace(' ', 'T').split('T')
                                            if len(parts) == 2:
                                                date_part = parts[0].split('-')
                                                time_part = parts[1][:5]  # HH:MM
                                                if len(date_part) == 3:
                                                    date_str = f"{date_part[2]}/{date_part[1]}/{date_part[0]} {time_part}"
                                                else:
                                                    date_str = date_str_raw[:16]
                                            else:
                                                date_str = date_str_raw[:16]
                                        except:
                                            date_str = date_str_raw[:16] if len(date_str_raw) >= 16 else 'N/A'
                                    else:
                                        date_str = 'N/A'
                                
                                st.info(f"📋 **Linha selecionada:** {selected_ref_data['FAROL_REFERENCE']} | {selected_ref_data['B_BOOKING_STATUS']} | {date_str}")
                            else:
                                st.error("❌ Erro ao encontrar a referência selecionada")
                else:
                    st.warning("⚠️ Nenhuma referência disponível encontrada na aba 'Other Status'")
                    related_reference = st.text_input("Digite o ID da referência relacionada:", key="manual_related_reference")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                subcol1, subcol2 = st.columns(2, gap="small")
                with subcol1:
                    # Desabilita o botão se for "Received from Carrier" e não tiver referência
                    can_confirm = True
                    validation_message = ""
                    if selected_row_status == "Received from Carrier" and pending_status == "Booking Approved":
                        can_confirm = related_reference is not None and str(related_reference).strip() != ""
                        
                        # Validação adicional para New Adjustment
                        if related_reference == "New Adjustment":
                            area_val = st.session_state.get("new_adjustment_area", "")
                            reason_val = st.session_state.get("new_adjustment_reason", "")
                            responsibility_val = st.session_state.get("new_adjustment_responsibility", "")
                            
                            if not area_val or not reason_val or not responsibility_val:
                                can_confirm = False
                                validation_message = "⚠️ Preencha todos os campos de justificativa (Area, Reason e Responsibility) antes de confirmar."
                    
                    # Exibe mensagem de validação se houver
                    if validation_message:
                        st.warning(validation_message)
                    
                    if st.button("✅ Confirmar", 
                                key="confirm_status_change",
                                type="primary",
                                disabled=not can_confirm):
                        # Prepara os parâmetros de justificativa para New Adjustment
                        area_param = None
                        reason_param = None
                        responsibility_param = None
                        comment_param = None
                        
                        if related_reference == "New Adjustment":
                            area_param = st.session_state.get("new_adjustment_area")
                            reason_param = st.session_state.get("new_adjustment_reason")
                            responsibility_param = st.session_state.get("new_adjustment_responsibility")
                            comment_param = st.session_state.get("new_adjustment_comment")
                        
                        # Executa a mudança de status
                        apply_status_change(farol_ref, adjustment_id, pending_status, selected_row_status, related_reference, area_param, reason_param, responsibility_param, comment_param)
                        
                        # Limpa o status pendente e dados de New Adjustment
                        st.session_state.pop("pending_status_change", None)
                        if related_reference == "New Adjustment":
                            st.session_state.pop("new_adjustment_area", None)
                            st.session_state.pop("new_adjustment_reason", None)
                            st.session_state.pop("new_adjustment_responsibility", None)
                            st.session_state.pop("new_adjustment_comment", None)
                    # Não precisamos de st.rerun() aqui, pois a função apply_status_change já faz isso
                
                with subcol2:
                    if st.button("❌ Cancelar", 
                                key="cancel_status_change",
                                type="secondary"):
                        # Limpa o status pendente e dados de New Adjustment
                        st.session_state.pop("pending_status_change", None)
                        st.session_state.pop("new_adjustment_area", None)
                        st.session_state.pop("new_adjustment_reason", None)
                        st.session_state.pop("new_adjustment_responsibility", None)
                        st.session_state.pop("new_adjustment_comment", None)
                        st.rerun()
            

    else:
        # Mensagem quando nenhuma linha está selecionada
        st.markdown("---")
        st.markdown("💡 **Dica:** Marque o checkbox de uma linha para ver as opções de status disponíveis e use 'View Attachments' para adicionar novos arquivos, fazer download individual ou em .zip e excluir anexos do registro selecionado.")
    
    # Função para aplicar mudanças de status (versão antiga removida; definida acima)


    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        # Toggle de anexos
        view_open = st.session_state.get("history_show_attachments", False)
        if st.button("📎 View Attachments", key="history_view_attachments"):
            st.session_state["history_show_attachments"] = not view_open
            st.rerun()
    with col2:
        # Export CSV - combina dados de ambas as abas
        if edited_df_other is not None and edited_df_received is not None:
            # Combina ambos os DataFrames
            combined_df = pd.concat([edited_df_other, edited_df_received], ignore_index=True)
        elif edited_df_other is not None:
            combined_df = edited_df_other
        elif edited_df_received is not None:
            combined_df = edited_df_received
        else:
            combined_df = pd.DataFrame()
            
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
