import streamlit as st
import pandas as pd
from database import get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, get_database_connection, update_sales_booking_from_return_carriers, update_return_carrier_status, get_current_status_from_main_table, get_return_carrier_status_by_adjustment_id
from shipments_mapping import get_column_mapping
from sqlalchemy import text
from datetime import datetime
import os
import base64
import mimetypes
import uuid
from pdf_booking_processor import process_pdf_booking, display_pdf_validation_interface, save_pdf_booking_data

def get_next_linked_reference_number():
    """Obtém o próximo número sequencial para Linked_Reference"""
    try:
        conn = get_database_connection()
        query = text("""
            SELECT NVL(MAX(Linked_Reference), 0) + 1 as next_number
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE Linked_Reference IS NOT NULL
        """)
        result = conn.execute(query).scalar()
        conn.close()
        return result if result else 1
    except Exception as e:
        st.error(f"❌ Erro ao obter próximo número sequencial: {str(e)}")
        return 1

def get_available_references_for_relation():
    """Busca referências disponíveis na aba 'Other Status' para relacionamento"""
    try:
        conn = get_database_connection()
        query = text("""
            SELECT ID, FAROL_REFERENCE, B_BOOKING_STATUS, ROW_INSERTED_DATE, Linked_Reference
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE B_BOOKING_STATUS != 'Received from Carrier'
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
    display_cols = [
        "ID",
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
        "B_PORT_TERMINAL_CITY",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_VOYAGE_CODE",
        "B_DOCUMENT_CUT_OFF_DOCCUT",
        "B_PORT_CUT_OFF_PORTCUT",
        "B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
        "B_ESTIMATED_TIME_OF_ARRIVAL_ETA",
        "B_GATE_OPENING",
        "P_STATUS",
        "P_PDF_NAME",
        "ROW_INSERTED_DATE",
        "USER_INSERT",
    ]

    # Inclui ADJUSTMENT_ID nos dados para funcionalidade interna, mas não na exibição
    internal_cols = display_cols + ["ADJUSTMENT_ID"]
    df_show = df[[c for c in internal_cols if c in df.columns]].copy()
    
    # Cria uma cópia para exibição sem ADJUSTMENT_ID
    df_display = df_show.drop(columns=["ADJUSTMENT_ID"], errors="ignore")
    
    # Adiciona coluna de seleção ao df_display
    df_display.insert(0, "Selecionar", False)
    
    # Separa os dados em duas abas baseado no status
    df_other_status = df_display[df_display["B_BOOKING_STATUS"] != "Received from Carrier"].copy()
    df_received_carrier = df_display[df_display["B_BOOKING_STATUS"] == "Received from Carrier"].copy()
    
    # Função para limpar seleções entre abas (não mais usada, mas mantida para compatibilidade)
    def clear_tab_selections():
        """Limpa todas as seleções dos data_editors para evitar conflitos entre abas"""
        # Esta função não é mais usada, mas mantida para compatibilidade
        pass
    
    # Rótulos das "abas"
    other_label = f"📋 Pedidos da Empresa ({len(df_other_status)} records)"
    received_label = f"📨 Retornos do Armador ({len(df_received_carrier)} records)"

    # Controle de "aba" ativa (segmented control) para detectar troca e limpar seleções da outra
    active_tab_key = f"history_active_tab_{farol_reference}"
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    if active_tab_key not in st.session_state:
        st.session_state[active_tab_key] = other_label
        st.session_state[last_active_tab_key] = other_label

    active_tab = st.segmented_control(
        "",
        options=[other_label, received_label],
        key=active_tab_key
    )

    # Se detectarmos troca de aba, acionamos flags para limpar seleções da outra
    prev_tab = st.session_state.get(last_active_tab_key)
    if prev_tab != active_tab:
        if active_tab == other_label:
            # Limpamos seleção da aba Received
            st.session_state[f"clear_received_selection_{farol_reference}"] = True
        else:
            # Limpamos seleção da aba Other
            st.session_state[f"clear_other_selection_{farol_reference}"] = True
        st.session_state[last_active_tab_key] = active_tab

    # Função para processar e configurar DataFrame
    def process_dataframe(df_to_process, df_show_ref):
        """Processa um DataFrame aplicando aliases e configurações"""
        if df_to_process.empty:
            return df_to_process, df_show_ref

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
            "ID": "ID",  # Campo ID visível
            "FAROL_REFERENCE": "Farol Reference",
            "B_BOOKING_REFERENCE": "Booking",  # Nova coluna de Booking Reference
            "ADJUSTMENT_ID": "Adjustment ID",  # Campo oculto
            "LINKED_REFERENCE": "Linked Reference",  # Campo para referência relacionada
            "B_BOOKING_STATUS": "Farol Status",
            "ROW_INSERTED_DATE": "Inserted Date",
            "USER_INSERT": "Inserted By",
            # Remover prefixos B_/P_ dos rótulos solicitados
            "B_GATE_OPENING": "Gate Opening",
            "P_STATUS": "Status",
            "P_PDF_NAME": "PDF Name",
            "S_QUANTITY_OF_CONTAINERS": "Quantity of Containers",
            "S_SPLITTED_BOOKING_REFERENCE": "Splitted Farol Reference",  # Nome corrigido
            # Aliases para campos de data
            "B_DOCUMENT_CUT_OFF_DOCCUT": "Document Cut Off",
            "B_PORT_CUT_OFF_PORTCUT": "Port Cut Off",
            "B_ESTIMATED_TIME_OF_DEPARTURE_ETD": "ETD",
            "B_ESTIMATED_TIME_OF_ARRIVAL_ETA": "ETA",
            # Alias para Voyage Code
            "B_VOYAGE_CODE": "Voyage Code",
        }

        # Aplica aliases ao DataFrame
        rename_map = {}
        for col in df_to_process.columns:
            rename_map[col] = custom_overrides.get(col, mapping_upper.get(col, prettify(col)))

        df_processed = df_to_process.copy()
        df_processed.rename(columns=rename_map, inplace=True)
        
        return df_processed, df_show_ref

    # Função para exibir grade em uma aba
    def display_tab_content(df_tab, tab_name):
        """Exibe o conteúdo de uma aba com a grade de dados"""
        if df_tab.empty:
            st.info(f"📋 Nenhum registro encontrado para {tab_name}")
            return None
            
        # Processa o DataFrame da aba
        df_processed, df_show_ref = process_dataframe(df_tab, df_show)
        
        # Converte epoch (ms) para datetime para exibição correta na grade (APÓS os aliases)
        if "Inserted Date" in df_processed.columns:
            try:
                df_processed["Inserted Date"] = pd.to_datetime(df_processed["Inserted Date"], unit="ms", errors="coerce")
            except Exception:
                pass
        
        # Converte campos de data específicos de epoch (ms) para datetime (APÓS os aliases)
        date_fields_mapped = {
            "Document Cut Off": "B_DOCUMENT_CUT_OFF_DOCCUT",
            "Port Cut Off": "B_PORT_CUT_OFF_PORTCUT", 
            "ETD": "B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
            "ETA": "B_ESTIMATED_TIME_OF_ARRIVAL_ETA"
        }
        
        for mapped_name, original_name in date_fields_mapped.items():
            if mapped_name in df_processed.columns:
                try:
                    # Busca o valor original antes do rename
                    original_values = df_show_ref[original_name]
                    df_processed[mapped_name] = pd.to_datetime(original_values, unit="ms", errors="coerce")
                except Exception:
                    pass

        # Move "Inserted Date" para a primeira coluna e ordena de forma crescente
        if "Inserted Date" in df_processed.columns:
            # Ordena pela data (crescente)
            try:
                df_processed = df_processed.sort_values("Inserted Date", ascending=True)
            except Exception:
                pass
                
        return df_processed



    # Conteúdo da "aba" Pedidos da Empresa
    st.info("💼 **Esta aba contém os pedidos de alteração realizados pela empresa. Após o registro, aguarde o retorno do armador.**") if active_tab == other_label else None
    df_other_processed = display_tab_content(df_other_status, "Pedidos da Empresa")
    edited_df_other = None
    if df_other_processed is not None and active_tab == other_label:
        # Configuração das colunas
        column_config = {
            "Farol Status": st.column_config.TextColumn(
                "Farol Status", disabled=True
            )
        }
        column_config["Selecionar"] = st.column_config.CheckboxColumn(
            "Select", help="Selecione apenas uma linha para aplicar mudanças", pinned="left"
        )
        column_config["ID"] = st.column_config.NumberColumn("ID", format="%d", disabled=True)
        column_config["Linked Reference"] = st.column_config.NumberColumn("Linked Reference", format="%d", disabled=True)

        # Reordena colunas - mantém "Selecionar" como primeira coluna
        if "Inserted Date" in df_other_processed.columns:
            other_cols = [c for c in df_other_processed.columns if c not in ["Selecionar", "ID", "Farol Reference", "Booking", "Linked Reference", "Inserted Date"]]
            ordered_cols = ["Selecionar", "ID", "Farol Reference", "Booking", "Linked Reference", "Inserted Date"] + other_cols
            existing_cols = [c for c in ordered_cols if c in df_other_processed.columns]
            df_other_processed = df_other_processed[existing_cols]

        # Configura colunas para exibição
        for col in df_other_processed.columns:
            if col == "Farol Status":
                continue
            if col == "Selecionar":
                continue
            if col == "Inserted Date":
                column_config[col] = st.column_config.DatetimeColumn(
                    "Inserted Date", format="YYYY-MM-DD HH:mm", disabled=True
                )
            elif col in ["Document Cut Off", "Port Cut Off", "ETD", "ETA"]:
                column_config[col] = st.column_config.DatetimeColumn(
                    col, format="YYYY-MM-DD HH:mm", disabled=True
                )
            else:
                column_config[col] = st.column_config.TextColumn(col, disabled=True)

        # Verifica se precisa limpar seleções desta aba
        clear_other_key = f"clear_other_selection_{farol_reference}"
        clear_other_multiple_key = f"clear_other_multiple_{farol_reference}"
        if clear_other_key in st.session_state or clear_other_multiple_key in st.session_state:
            df_other_processed = df_other_processed.copy()
            df_other_processed["Selecionar"] = False
            if clear_other_key in st.session_state:
                del st.session_state[clear_other_key]
            if clear_other_multiple_key in st.session_state:
                del st.session_state[clear_other_multiple_key]

        edited_df_other = st.data_editor(
            df_other_processed,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=False,
            key=f"history_other_status_editor_{farol_reference}"
        )

    # Conteúdo da "aba" Retornos do Armador
    st.info("📨 **Esta aba contém os retornos do armador com status 'Received from Carrier'. Para aprovar, será necessário informar a referência relacionada da aba 'Pedidos da Empresa'.**") if active_tab == received_label else None
    df_received_processed = display_tab_content(df_received_carrier, "Retornos do Armador")
    edited_df_received = None
    if df_received_processed is not None and active_tab == received_label:
        # Configuração das colunas
        column_config = {
            "Farol Status": st.column_config.TextColumn(
                "Farol Status", disabled=True
            )
        }
        column_config["Selecionar"] = st.column_config.CheckboxColumn(
            "Select", help="Selecione apenas uma linha para aplicar mudanças", pinned="left"
        )

        # Reordena colunas - mantém "Selecionar" como primeira coluna (ID e Linked Reference ocultos na aba Retornos do Armador)
        if "Inserted Date" in df_received_processed.columns:
            other_cols = [c for c in df_received_processed.columns if c not in ["Selecionar", "ID", "Farol Reference", "Booking", "Linked Reference", "Inserted Date"]]
            ordered_cols = ["Selecionar", "Farol Reference", "Booking", "Inserted Date"] + other_cols
            existing_cols = [c for c in ordered_cols if c in df_received_processed.columns]
            df_received_processed = df_received_processed[existing_cols]

        # Configura colunas para exibição
        for col in df_received_processed.columns:
            if col == "Farol Status":
                continue
            if col == "Selecionar":
                continue
            if col == "Inserted Date":
                column_config[col] = st.column_config.DatetimeColumn(
                    "Inserted Date", format="YYYY-MM-DD HH:mm", disabled=True
                )
            elif col in ["Document Cut Off", "Port Cut Off", "ETD", "ETA"]:
                column_config[col] = st.column_config.DatetimeColumn(
                    col, format="YYYY-MM-DD HH:mm", disabled=True
                )
            else:
                column_config[col] = st.column_config.TextColumn(col, disabled=True)

        # Verifica se precisa limpar seleções desta aba
        clear_received_key = f"clear_received_selection_{farol_reference}"
        clear_received_multiple_key = f"clear_received_multiple_{farol_reference}"
        if clear_received_key in st.session_state or clear_received_multiple_key in st.session_state:
            df_received_processed = df_received_processed.copy()
            df_received_processed["Selecionar"] = False
            if clear_received_key in st.session_state:
                del st.session_state[clear_received_key]
            if clear_received_multiple_key in st.session_state:
                del st.session_state[clear_received_multiple_key]

        edited_df_received = st.data_editor(
            df_received_processed,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=False,
            key=f"history_received_carrier_editor_{farol_reference}"
        )

    # Determina qual DataFrame usar baseado na aba ativa
    # Por padrão, usa o primeiro DataFrame disponível
    if edited_df_other is not None:
        edited_df = edited_df_other
    elif edited_df_received is not None:
        edited_df = edited_df_received
    else:
        # Fallback para DataFrame vazio
        edited_df = pd.DataFrame()

    # Função para aplicar mudanças de status (declarada antes do uso)
    def apply_status_change(farol_ref, adjustment_id, new_status, selected_row_status=None, related_reference=None):
        try:
            conn = get_database_connection()
            tx = conn.begin()
            
            # Resolve ADJUSTMENT_ID (usa o passado ou busca por fallback)
            adj_id = (str(adjustment_id).strip() if adjustment_id is not None else None)
            if not adj_id or adj_id.lower() in ("none", "nan", "null", ""):
                # Fallback: tenta pelo FAROL_REFERENCE e, se informado, pelo status da linha selecionada
                try:
                    if selected_row_status:
                        sql_adj = text("""
                            SELECT ADJUSTMENT_ID
                              FROM LogTransp.F_CON_RETURN_CARRIERS
                             WHERE FAROL_REFERENCE = :farol_reference
                               AND B_BOOKING_STATUS = :status_atual
                          ORDER BY ROW_INSERTED_DATE DESC
                          FETCH FIRST 1 ROWS ONLY
                        """)
                        adj_id = conn.execute(sql_adj, {"farol_reference": farol_ref, "status_atual": selected_row_status}).scalar()
                    if not adj_id:
                        sql_adj_any = text("""
                            SELECT ADJUSTMENT_ID
                              FROM LogTransp.F_CON_RETURN_CARRIERS
                             WHERE FAROL_REFERENCE = :farol_reference
                          ORDER BY ROW_INSERTED_DATE DESC
                          FETCH FIRST 1 ROWS ONLY
                        """)
                        adj_id = conn.execute(sql_adj_any, {"farol_reference": farol_ref}).scalar()
                    if adj_id:
                        adj_id = str(adj_id).strip()
                        st.caption(f"DEBUG: ADJUSTMENT_ID usado={adj_id}")
                except Exception:
                    pass
            
            # Se o status foi alterado para "Booking Approved", executa a lógica de aprovação
            if new_status == "Booking Approved" and adj_id:
                # Validação especial para itens "Received from Carrier"
                if selected_row_status == "Received from Carrier" and related_reference:
                    if related_reference == "New Adjustment":
                        # Caso especial: New Adjustment - não precisa validar referência
                        st.success("✅ New Adjustment selecionado - ajuste do carrier sem referência prévia!")
                        # Atualiza o Linked_Reference com "New Adjustment"
                        conn.execute(text("""
                            UPDATE LogTransp.F_CON_RETURN_CARRIERS
                            SET Linked_Reference = :linked_ref,
                                USER_UPDATE = :user_update,
                                DATE_UPDATE = SYSDATE
                            WHERE ADJUSTMENT_ID = :adjustment_id
                        """), {
                            "linked_ref": "New Adjustment",
                            "user_update": "System",
                            "adjustment_id": adj_id
                        })
                        st.success("✅ Linked_Reference atualizado para 'New Adjustment'")
                    else:
                        # Valida se o ID relacionado existe na aba 'Other Status'
                        related_exists = conn.execute(text("""
                            SELECT COUNT(*) FROM LogTransp.F_CON_RETURN_CARRIERS
                            WHERE ID = :related_id
                            AND B_BOOKING_STATUS != 'Received from Carrier'
                        """), {"related_id": related_reference}).scalar()
                        
                        if related_exists > 0:
                            st.success(f"✅ ID relacionado '{related_reference}' validado com sucesso!")
                            # Atualiza o Linked_Reference na linha atual
                            conn.execute(text("""
                                UPDATE LogTransp.F_CON_RETURN_CARRIERS
                                SET Linked_Reference = :linked_ref,
                                    USER_UPDATE = :user_update,
                                    DATE_UPDATE = SYSDATE
                                WHERE ADJUSTMENT_ID = :adjustment_id
                            """), {
                                "linked_ref": related_reference,
                                "user_update": "System",
                                "adjustment_id": adj_id
                            })
                            st.success(f"✅ Linked_Reference atualizado para ID {related_reference}")
                        else:
                            st.error(f"❌ ID relacionado '{related_reference}' não encontrado na aba 'Other Status'")
                            tx.rollback()
                            conn.close()
                            return
                
                # Atualiza a tabela F_CON_SALES_BOOKING_DATA com os dados da linha aprovada
                if update_sales_booking_from_return_carriers(adj_id):
                    st.success(f"✅ Dados atualizados na tabela F_CON_SALES_BOOKING_DATA para {farol_ref}")
                else:
                    st.warning(f"⚠️ Nenhum dado foi atualizado para {farol_ref} (todos os campos estavam vazios)")

            # Atualiza o status na tabela F_CON_RETURN_CARRIERS SEMPRE (na mesma transação)
            # Sanity check: existe linha com esse ADJUSTMENT_ID?
            try:
                exists_cnt = conn.execute(text("""
                    SELECT COUNT(*) FROM LogTransp.F_CON_RETURN_CARRIERS WHERE ADJUSTMENT_ID = :adjustment_id
                """), {"adjustment_id": adj_id}).scalar()
                st.caption(f"DEBUG: adjustment_id={adj_id}, rows_encontradas={exists_cnt}")
            except Exception:
                exists_cnt = None

            res_rc = conn.execute(text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS
                   SET B_BOOKING_STATUS = :new_status,
                       USER_UPDATE = :user_update,
                       DATE_UPDATE = SYSDATE
                 WHERE ADJUSTMENT_ID = :adjustment_id
            """), {
                "new_status": new_status,
                "user_update": "System",
                "adjustment_id": adj_id,
            })
            if getattr(res_rc, "rowcount", 0) > 0:
                st.success(f"✅ Status atualizado em F_CON_RETURN_CARRIERS para {farol_ref}")
            else:
                st.warning("⚠️ Nenhuma linha foi atualizada em F_CON_RETURN_CARRIERS (verifique o ADJUSTMENT_ID)")

            # Regras específicas por status
            if new_status in ["Booking Rejected", "Booking Cancelled", "Adjustment Requested"]:
                # Atualiza SOMENTE a coluna FAROL_STATUS na tabela principal
                conn.execute(text("""
                    UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                       SET FAROL_STATUS = :farol_status
                     WHERE FAROL_REFERENCE = :farol_reference
                """), {"farol_status": new_status, "farol_reference": farol_ref})
                st.success(f"✅ FAROL_STATUS atualizado em F_CON_SALES_BOOKING_DATA para {farol_ref}")
            else:
                # Demais status (Approved)
                conn.execute(text("""
                    UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                       SET FAROL_STATUS = :farol_status
                     WHERE FAROL_REFERENCE = :farol_reference
                """), {"farol_status": new_status, "farol_reference": farol_ref})

            # Verificação pós-aprovação: comparar campos entre as duas tabelas
            if new_status == "Booking Approved":
                try:
                    fields = [
                        "S_SPLITTED_BOOKING_REFERENCE","S_PLACE_OF_RECEIPT","S_QUANTITY_OF_CONTAINERS",
                        "S_PORT_OF_LOADING_POL","S_PORT_OF_DELIVERY_POD","S_FINAL_DESTINATION",
                        "B_TRANSHIPMENT_PORT","B_PORT_TERMINAL_CITY","B_VESSEL_NAME","B_VOYAGE_CARRIER",
                        "B_DOCUMENT_CUT_OFF_DOCCUT","B_PORT_CUT_OFF_PORTCUT","B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
                        "B_ESTIMATED_TIME_OF_ARRIVAL_ETA","B_GATE_OPENING"
                    ]
                    cols = ", ".join(fields)
                    # Retorno: pela linha aprovada
                    rc_row = conn.execute(text(f"""
                        SELECT {cols}
                          FROM LogTransp.F_CON_RETURN_CARRIERS
                         WHERE ADJUSTMENT_ID = :adj
                    """), {"adj": adj_id}).mappings().fetchone()
                    # Principal: pela referência
                    sb_row = conn.execute(text(f"""
                        SELECT {cols}
                          FROM LogTransp.F_CON_SALES_BOOKING_DATA
                         WHERE FAROL_REFERENCE = :ref
                    """), {"ref": farol_ref}).mappings().fetchone()
                    if rc_row and sb_row:
                        st.markdown("#### 🔎 Pós-aprovação (comparação de campos)")
                        for f in fields:
                            st.caption(f"{f}: RC='{rc_row.get(f)}' → SB='{sb_row.get(f)}'")
                except Exception as _:
                    pass

            tx.commit()
            st.success(f"✅ Status atualizado com sucesso para {farol_ref}!")
            st.rerun()
            
        except Exception as e:
            if 'tx' in locals():
                tx.rollback()
            st.error(f"❌ Erro ao atualizar status: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    # Interface de botões de status para linha selecionada
    # Verifica seleções em ambas as abas
    selected_other = edited_df_other[edited_df_other["Selecionar"] == True] if edited_df_other is not None else pd.DataFrame()
    selected_received = edited_df_received[edited_df_received["Selecionar"] == True] if edited_df_received is not None else pd.DataFrame()
    
    # Se há seleções em ambas as abas, limpa automaticamente a seleção da aba "other" (prioriza "received")
    if len(selected_other) > 0 and len(selected_received) > 0:
        # Limpa a seleção da aba "other" automaticamente usando uma chave de controle
        clear_other_key = f"clear_other_selection_{farol_reference}"
        if clear_other_key not in st.session_state:
            st.session_state[clear_other_key] = True
            st.rerun()
    
    # Verificação adicional: se há múltiplas seleções na mesma aba, limpa todas
    if len(selected_other) > 1:
        clear_other_multiple_key = f"clear_other_multiple_{farol_reference}"
        if clear_other_multiple_key not in st.session_state:
            st.session_state[clear_other_multiple_key] = True
            st.rerun()
    
    if len(selected_received) > 1:
        clear_received_multiple_key = f"clear_received_multiple_{farol_reference}"
        if clear_received_multiple_key not in st.session_state:
            st.session_state[clear_received_multiple_key] = True
            st.rerun()
    
    # Determina qual seleção usar (prioriza "received" se ambas tiverem seleção)
    if len(selected_other) > 0 and len(selected_received) > 0:
        selected = selected_received
        selected_df = edited_df_received
    else:
        selected = selected_other if not selected_other.empty else selected_received
        selected_df = edited_df_other if not selected_other.empty else edited_df_received
    
    if len(selected) > 1:
        st.warning("⚠️ Selecione apenas uma linha para aplicar mudanças.")
    
    # Interface de botões de status para linha selecionada
    if len(selected) == 1:
        st.markdown("---")

        
        # Obtém informações da linha selecionada (usar diretamente a série selecionada para evitar divergência de índice)
        selected_row = selected.iloc[0]
        farol_ref = selected_row.get("Farol Reference") or selected_row.get("FAROL_REFERENCE")
        adjustment_id = selected_row.get("Adjustment ID")
        
        # Obtém o status da linha selecionada na tabela F_CON_RETURN_CARRIERS (prioriza leitura por UUID)
        selected_row_status = get_return_carrier_status_by_adjustment_id(adjustment_id) or selected_row.get("Farol Status", "")
        
        # Obtém o status atual da tabela principal F_CON_SALES_BOOKING_DATA
        current_status = get_current_status_from_main_table(farol_ref)
        

        
        # Verifica se o status da linha selecionada é "Booking Requested" - se for, não permite alterações
        if selected_row_status == "Booking Requested":
            st.warning("⚠️ **Esta etapa não pode ser alterada pelo usuário**")
            st.info(f"📋 O status '{selected_row_status}' é uma etapa protegida do sistema")
        else:
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
                        if current_status != "Booking Approved":
                            st.session_state["pending_status_change"] = "Booking Approved"
                        st.rerun()
                
                with subcol2:
                    if st.button("Booking Rejected", 
                                key="status_booking_rejected",
                                type="secondary"):
                        if current_status != "Booking Rejected":
                            st.session_state["pending_status_change"] = "Booking Rejected"
                        st.rerun()

                with subcol3:
                    if st.button("Booking Cancelled", 
                                key="status_booking_cancelled",
                                type="secondary"):
                        if current_status != "Booking Cancelled":
                            st.session_state["pending_status_change"] = "Booking Cancelled"
                        st.rerun()
                
                with subcol4:
                    if st.button("Adjustment Requested", 
                                key="status_adjustment_requested",
                                type="secondary"):
                        if current_status != "Adjustment Requested":
                            st.session_state["pending_status_change"] = "Adjustment Requested"
                        st.rerun()
            
            # Confirmação quando há status pendente
            pending_status = st.session_state.get("pending_status_change")
            if pending_status:
                # Se o status pendente é igual ao status atual, limpa automaticamente
                if pending_status == current_status:
                    st.session_state.pop("pending_status_change", None)
                    st.rerun()
                else:
                    st.markdown("---")
                    st.warning(f"**Confirmar alteração para:** {pending_status}")
                    
                    # Validação especial para itens "Received from Carrier" sendo aprovados
                    related_reference = None
                    if selected_row_status == "Received from Carrier" and pending_status == "Booking Approved":
                        st.info("📋 **Este item é um retorno do armador. Antes de aprovar, informe a referência da aba relacionada:**")
                        
                        # Busca referências disponíveis na aba 'Other Status'
                        available_refs = get_available_references_for_relation()
                        
                        if available_refs:
                            # Cria opções para o selectbox
                            ref_options = [f"ID: {ref['ID']} | {ref['FAROL_REFERENCE']} | {ref['B_BOOKING_STATUS']}" for ref in available_refs]
                            ref_options.insert(0, "Selecione uma referência...")
                            ref_options.append("New Adjustment")  # Opção para ajuste sem referência prévia
                            
                            selected_ref = st.selectbox(
                                "Selecione a linha relacionada da aba 'Other Status' ou 'New Adjustment':",
                                options=ref_options,
                                key="related_reference_select"
                            )
                            
                            if selected_ref and selected_ref != "Selecione uma referência...":
                                if selected_ref == "New Adjustment":
                                    related_reference = "New Adjustment"
                                    st.info("🆕 **New Adjustment selecionado:** Este é um ajuste do carrier sem referência prévia da empresa.")
                                else:
                                    # Extrai o ID da opção selecionada
                                    related_reference = selected_ref.split(" | ")[0].replace("ID: ", "")
                                
                                    # Mostra detalhes da linha selecionada
                                    selected_ref_data = next((ref for ref in available_refs if str(ref['ID']) == related_reference), None)
                                    if selected_ref_data:
                                        st.info(f"📋 **Linha selecionada:** ID {selected_ref_data['ID']} | {selected_ref_data['FAROL_REFERENCE']} | {selected_ref_data['B_BOOKING_STATUS']}")
                        else:
                            st.warning("⚠️ Nenhuma referência disponível encontrada na aba 'Other Status'")
                            related_reference = st.text_input("Digite o ID da referência relacionada:", key="manual_related_reference")
                    
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        subcol1, subcol2 = st.columns(2, gap="small")
                        with subcol1:
                            # Desabilita o botão se for "Received from Carrier" e não tiver referência
                            can_confirm = True
                            if selected_row_status == "Received from Carrier" and pending_status == "Booking Approved":
                                can_confirm = related_reference is not None and str(related_reference).strip() != ""
                            
                            if st.button("✅ Confirmar", 
                                        key="confirm_status_change",
                                        type="primary",
                                        disabled=not can_confirm):
                                # Executa a mudança de status
                                apply_status_change(farol_ref, adjustment_id, pending_status, selected_row_status, related_reference)
                                # Limpa o status pendente
                                st.session_state.pop("pending_status_change", None)
                                st.rerun()
                        
                        with subcol2:
                            if st.button("❌ Cancelar", 
                                        key="cancel_status_change",
                                        type="secondary"):
                                # Limpa o status pendente
                                st.session_state.pop("pending_status_change", None)
                                st.rerun()
            

    else:
        # Mensagem quando nenhuma linha está selecionada
        st.markdown("---")
        st.info("📋 **Selecione uma linha na grade acima para gerenciar o status**")
        st.markdown("💡 **Dica:** Marque o checkbox de uma linha para ver as opções de status disponíveis")
    
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