##booking_adjustments.py
# 
# ✅ FUNCIONALIDADE: Tela Simplificada de Adjustment Management
# Interface única e direta mostrando os dados da F_CON_SALES_DATA já com os ajustes aplicados,
# simulando como ficaram após os splits/alterações solicitados no shipments_split.py
# 
# Funcionalidades implementadas:
# - Interface simplificada: Grade direta (sem abas) para agilizar aprovações
# - Exibição dos dados ajustados com as mesmas colunas do shipments_split.py
# - Tabela editável (st.data_editor) com coluna "Status" editável diretamente na grade
# - Coluna "Status" posicionada após "Farol Reference" para melhor visibilidade
# - Status padrão "Adjustment Requested" (SEM opção em branco no dropdown)
# - Normalização robusta: Remove opções vazias/None/strings vazias do SelectboxColumn
# - Coluna "Changes Made" com resumo das alterações (📝 campos alterados, 🔧 splits)  
# - Coluna "Comments" exibindo comentários informados na tela shipments_split.py
# - Coluna "Adjustment ID" para rastreabilidade
# - Detecção automática de mudanças no status com confirmação antes de aplicar
# - Opções de status integradas com UDC (SelectboxColumn) sempre com "Adjustment Requested" primeiro
# - Botões "Apply Changes" e "Cancel Changes" para controle das alterações
# - Atualização em lote das tabelas principais (Sales, Booking, Loading)
# - Todas as colunas são read-only exceto "Status" para edição segura
# 
import streamlit as st
import pandas as pd
from database import get_merged_data, get_database_connection, load_df_udc
from sqlalchemy import text
from datetime import datetime, timedelta
import os
import base64
import mimetypes
import uuid

def get_original_sales_data(farol_reference):
    """Busca os dados originais da F_CON_SALES_DATA para um farol reference específico."""
    conn = get_database_connection()
    try:
        query = """
        SELECT 
            s_farol_reference,
            s_quantity_of_containers,
            s_port_of_loading_pol,
            s_port_of_delivery_pod,
            s_place_of_receipt,
            s_final_destination,
            s_carrier,
            s_requested_deadlines_start_date,
            s_requested_deadlines_end_date,
            s_required_arrival_date
        FROM LogTransp.F_CON_SALES_DATA
        WHERE s_farol_reference = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return dict(result) if result else None
    finally:
        conn.close()

def apply_adjustments_to_data(original_data, adjustments_df):
    """Aplica os ajustes aos dados originais e retorna os dados ajustados."""
    if original_data is None:
        return None
    
    # Cria uma cópia dos dados originais
    adjusted_data = original_data.copy()
    
    # Mapeia as colunas do log para as colunas da base de dados
    column_mapping = {
        "Sales Quantity of Containers": "s_quantity_of_containers",
        "Sales Port of Loading POL": "s_port_of_loading_pol", 
        "Sales Port of Delivery POD": "s_port_of_delivery_pod",
        "Sales Place of Receipt": "s_place_of_receipt",
        "Sales Final Destination": "s_final_destination",
        "Carrier": "s_carrier",
        "Requested Cut off Start Date": "s_requested_deadlines_start_date",
        "Requested Cut off End Date": "s_requested_deadlines_end_date",
        "Required Arrival Date": "s_required_arrival_date"
    }
    
    # Aplica cada ajuste
    for _, adjustment in adjustments_df.iterrows():
        column_name = adjustment['column_name']
        new_value = adjustment['new_value']
        
        # Mapeia o nome da coluna do log para o nome na base
        db_column = column_mapping.get(column_name)
        if db_column and db_column in adjusted_data:
            # Converte o valor conforme necessário
            if db_column == "s_quantity_of_containers":
                try:
                    adjusted_data[db_column] = int(new_value) if new_value and new_value != "" else 0
                except (ValueError, TypeError):
                    adjusted_data[db_column] = 0
            elif "date" in db_column.lower():
                # Para campos de data, mantém como string ou tenta converter
                adjusted_data[db_column] = new_value
            else:
                adjusted_data[db_column] = new_value
    
    return adjusted_data

def generate_changes_summary(adjustments_df, farol_ref):
    """
    Gera um resumo das alterações feitas para uma referência específica.
    
    Formato de retorno:
    - Para splits: "🔧 Split: X containers"  
    - Para alterações: "📝 Campo: Valor Anterior → Novo Valor"
    - Múltiplas alterações separadas por " | "
    """
    ref_adjustments = adjustments_df[adjustments_df['farol_reference'] == farol_ref]
    
    changes_list = []
    for _, adj in ref_adjustments.iterrows():
        column_name = adj['column_name']
        previous_value = adj['previous_value']
        new_value = adj['new_value']
        
        # Formata o valor anterior e novo
        prev_val = str(previous_value) if pd.notna(previous_value) and previous_value != "" else "Não informado"
        new_val = str(new_value) if pd.notna(new_value) and new_value != "" else "Não informado"
        
        if column_name == 'Split':
            changes_list.append(f"🔧 Split: {new_val} containers")
        else:
            field_name = format_column_name(column_name)
            changes_list.append(f"📝 {field_name}: {prev_val} → {new_val}")
    
    return " | ".join(changes_list) if changes_list else "Nenhuma alteração detectada"

def get_adjusted_sales_data(farol_references, adjustments_df):
    """Busca dados originais e aplica ajustes para múltiplas referências."""
    adjusted_records = []
    
    for farol_ref in farol_references:
        # Busca dados originais
        original_data = get_original_sales_data(farol_ref)
        
        if original_data:
            # Filtra ajustes para esta referência
            ref_adjustments = adjustments_df[adjustments_df['farol_reference'] == farol_ref]
            
            # Pega o adjustment_id (assume que é o mesmo para toda a referência)
            adjustment_id = ref_adjustments['adjustment_id'].iloc[0] if not ref_adjustments.empty else ""
            
            # Pega os comentários da solicitação
            comments = ref_adjustments['comments'].iloc[0] if not ref_adjustments.empty and 'comments' in ref_adjustments.columns else ""
            comments = comments if pd.notna(comments) and comments != "" else "Nenhum comentário"
            
            # Pega o status atual e normaliza para "Adjustment Requested" por padrão
            if not ref_adjustments.empty:
                current_status = ref_adjustments['status'].iloc[0]
                # Normaliza status vazios, nulos ou "Pending" para "Adjustment Requested"
                if pd.isna(current_status) or current_status == "" or current_status == "Pending":
                    current_status = "Adjustment Requested"
            else:
                current_status = "Adjustment Requested"
            
            # Gera resumo das alterações
            changes_summary = generate_changes_summary(adjustments_df, farol_ref)
            
            # Verifica se há splits (ajustes do tipo "Split")
            split_adjustments = ref_adjustments[ref_adjustments['column_name'] == 'Split']
            regular_adjustments = ref_adjustments[ref_adjustments['column_name'] != 'Split']
            
            # Aplica ajustes regulares primeiro
            adjusted_data = apply_adjustments_to_data(original_data, regular_adjustments)
            
            if adjusted_data:
                # Se há splits, cria registros para cada split
                if not split_adjustments.empty:
                    for _, split_adj in split_adjustments.iterrows():
                        split_record = {
                            "Sales Farol Reference": split_adj['farol_reference'],
                            "Status": current_status,
                            "Sales Quantity of Containers": int(split_adj['new_value']) if split_adj['new_value'] else 0,
                            "Sales Port of Loading POL": adjusted_data["s_port_of_loading_pol"],
                            "Sales Port of Delivery POD": adjusted_data["s_port_of_delivery_pod"], 
                            "Sales Place of Receipt": adjusted_data["s_place_of_receipt"],
                            "Sales Final Destination": adjusted_data["s_final_destination"],
                            "Carrier": adjusted_data["s_carrier"],
                            "Requested Cut off Start Date": adjusted_data["s_requested_deadlines_start_date"],
                            "Requested Cut off End Date": adjusted_data["s_requested_deadlines_end_date"],
                            "Required Arrival Date": adjusted_data["s_required_arrival_date"],
                            "Changes Made": changes_summary,
                            "Comments": comments,
                            "Adjustment ID": adjustment_id
                        }
                        adjusted_records.append(split_record)
                else:
                    # Se não há splits, cria registro normal
                    display_record = {
                        "Sales Farol Reference": adjusted_data["s_farol_reference"],
                        "Status": current_status,
                        "Sales Quantity of Containers": adjusted_data["s_quantity_of_containers"],
                        "Sales Port of Loading POL": adjusted_data["s_port_of_loading_pol"],
                        "Sales Port of Delivery POD": adjusted_data["s_port_of_delivery_pod"], 
                        "Sales Place of Receipt": adjusted_data["s_place_of_receipt"],
                        "Sales Final Destination": adjusted_data["s_final_destination"],
                        "Carrier": adjusted_data["s_carrier"],
                        "Requested Cut off Start Date": adjusted_data["s_requested_deadlines_start_date"],
                        "Requested Cut off End Date": adjusted_data["s_requested_deadlines_end_date"],
                        "Required Arrival Date": adjusted_data["s_required_arrival_date"],
                        "Changes Made": changes_summary,
                        "Comments": comments,
                        "Adjustment ID": adjustment_id
                    }
                    adjusted_records.append(display_record)
    
    return pd.DataFrame(adjusted_records) if adjusted_records else pd.DataFrame()

def format_column_name(col_name):
    """Formata o nome da coluna para um formato mais amigável."""
    column_map = {
        "Sales Quantity of Containers": "Quantidade de Containers",
        "Sales Port of Loading POL": "Porto de Origem (POL)",
        "Sales Port of Delivery POD": "Porto de Destino (POD)",
        "Sales Place of Receipt": "Local de Recebimento",
        "Sales Final Destination": "Destino Final",
        "Split": "Split de Embarque",
        "Carrier": "Transportadora",
        "Requested Cut off Start Date": "Data Inicial de Cut-off",
        "Requested Cut off End Date": "Data Final de Cut-off",
        "Required Arrival Date": "Data de Chegada Requerida"
    }
    return column_map.get(col_name, col_name)

def format_value(value):
    """Formata o valor para exibição mais amigável."""
    if pd.isna(value) or value == "" or value is None:
        return "Não informado"
    return str(value)



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
        file_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        
        # Gera o próximo ID numérico para a tabela
        id_query = text("SELECT NVL(MAX(id), 0) + 1 as next_id FROM LogTransp.F_CON_ANEXOS")
        next_id = conn.execute(id_query).fetchone()[0]
        
        # SQL com estrutura REAL da tabela
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
            "id": next_id,
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

def delete_attachment(attachment_id):
    """
    Exclui um anexo específico do banco de dados.
    
    Args:
        attachment_id: ID numérico do anexo
    
    Returns:
        bool: True se excluído com sucesso, False caso contrário
    """
    try:
        conn = get_database_connection()
        
        query = text("""
            DELETE FROM LogTransp.F_CON_ANEXOS 
            WHERE id = :attachment_id
        """)
        
        result = conn.execute(query, {"attachment_id": attachment_id})
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
    
    Args:
        farol_reference: Referência do Farol
    """
    
    # Seção de Upload com estilo melhorado
    with st.expander("📤 Add New Attachment", expanded=False):
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Drag and drop files here or click to select",
            accept_multiple_files=True,
            type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'],
            key=f"uploader_{farol_reference}",
            help="Supported file types: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, PNG, JPG, JPEG, GIF, ZIP, RAR"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} file(s) selected:")
            for file in uploaded_files:
                st.write(f"📁 **{file.name}** - {format_file_size(len(file.getvalue()))}")
            
            col1, col2 = st.columns([1, 4])
            with col1:
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
                        st.balloons()  # Efeito visual de sucesso
                    else:
                        st.warning(f"⚠️ {success_count} of {len(uploaded_files)} attachments were saved.")
                    
                    # Força atualização da lista
                    st.rerun()

    # Lista de Anexos Existentes
    attachments_df = get_attachments_for_farol(farol_reference)
    
    if not attachments_df.empty:
        st.markdown(f"### 📋 Existing Attachments ({len(attachments_df)})")
        
        # Calcula o número de colunas baseado no número de anexos (máximo 3)
        num_cols = min(3, len(attachments_df))
        cols = st.columns(num_cols)
        
        for idx, attachment in attachments_df.iterrows():
            col_idx = idx % num_cols
            
            with cols[col_idx]:
                # Card do anexo com CSS customizado
                file_icon = get_file_icon(attachment['mime_type'], attachment['file_name'])
                
                # Nome do arquivo truncado para exibição
                display_name = attachment.get('full_file_name', attachment['file_name'])
                if len(display_name) > 25:
                    display_name = display_name[:22] + "..."
                
                st.markdown(
                    f"""
                    <div class="attachment-card">
                        <div class="file-icon">{file_icon}</div>
                        <div class="file-name" title="{attachment.get('full_file_name', attachment['file_name'])}">{display_name}</div>
                        <div class="file-info">
                            <span>📁 .{attachment.get('file_extension', 'N/A').lower()}</span>
                        </div>
                        <div class="file-info">
                            <span>👤 {attachment['uploaded_by']}</span>
                        </div>
                        <div class="file-info">
                            <span>📅 {attachment['upload_date'].strftime('%d/%m/%Y %H:%M') if pd.notna(attachment['upload_date']) else 'N/A'}</span>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Controle de estado de confirmação
                confirm_key = f"confirm_delete_{attachment['id']}"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False
                
                if not st.session_state[confirm_key]:
                    # Botões normais - Download e Excluir
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        # Botão de download direto para todos os tipos de arquivo
                        file_content, file_name, mime_type = get_attachment_content(attachment['id'])
                        if file_content:
                                                    st.download_button(
                            label="⬇️ Download",
                                data=file_content,
                                file_name=file_name,
                                mime=mime_type,
                                key=f"download_btn_{attachment['id']}",
                                use_container_width=True
                            )
                        else:
                            st.button("⬇️ Unavailable", key=f"unavailable_{attachment['id']}", use_container_width=True, disabled=True)
                    
                    with col_btn2:
                        # Botão inicial de excluir
                        if st.button("🗑️ Delete", key=f"delete_{attachment['id']}", use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()
                
                else:
                    # Modo de confirmação - botões horizontais em nova linha
                    st.warning("⚠️ Confirm deletion?")
                    
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("✅ Yes, delete", key=f"confirm_yes_{attachment['id']}", use_container_width=True):
                            if delete_attachment(attachment['id']):
                                st.success("✅ Attachment deleted successfully!")
                                st.session_state[confirm_key] = False
                                st.rerun()
                            else:
                                st.error("❌ Error deleting attachment!")
                                st.session_state[confirm_key] = False
                    
                    with col_confirm2:
                        if st.button("❌ Cancel", key=f"confirm_no_{attachment['id']}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()
        

            
    else:
        st.info("📂 No attachments found for this reference.")
        st.markdown("💡 **Tip:** Use the 'Add New Attachment' section above to upload files related to this Farol Reference.")

def exibir_adjustments():
    st.title("📋 Adjustment Request Management")
    
    # CSS personalizado para cards de anexos e métricas
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
    </style>
    """, unsafe_allow_html=True)

    # Carrega os dados da UDC
    df_udc = load_df_udc()
    farol_status_options = df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()
    
    # Status disponíveis na UDC - Farol Status:
    # ['New request', 'Booking Requested', 'Received from Carrier', 'Booking Under Review', 
    #  'Adjustment Requested', 'Booking Approved', 'Booking Cancelled', 'Booking Rejected']

    # Carrega os dados dos ajustes
    df_original = get_merged_data()

    if df_original.empty:
        st.info("No adjustment requests found.")
        return

    # Trata valores nulos nas colunas de filtro e normaliza status
    df_original['status'] = df_original['status'].fillna("Adjustment Requested")
    # Normaliza qualquer status vazio ou "Pending" para "Adjustment Requested"
    df_original['status'] = df_original['status'].apply(
        lambda x: "Adjustment Requested" if pd.isna(x) or x == "" or x == "Pending" or x is None else x
    )
    df_original['area'] = df_original['area'].fillna("Not Specified")
    df_original['stage'] = df_original['stage'].fillna("Not Specified")

    # Seção de Filtros
    with st.expander("🔍 Search Filters", expanded=True):
        # Primeira linha: Period e Search
        col1, col2 = st.columns(2)
        
        with col1:
            # Filtro por período
            st.subheader("Period")
            periodo_opcoes = {
                "Today": 0,
                "Last 7 days": 7,
                "Last 30 days": 30,
                "All": -1
            }
            periodo_selecionado = st.radio("", list(periodo_opcoes.keys()), horizontal=True)
        
        with col2:
            # Campo de busca
            st.subheader("Search by Farol Reference")
            st.text_input("", key="busca", label_visibility="collapsed")

        # Segunda linha: Status, Area e Stage
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Status")
            status_opcoes = ["All"] + sorted(df_original['status'].unique().tolist())
            status_selecionado = st.selectbox("", status_opcoes, label_visibility="collapsed")
        
        with col2:
            st.subheader("Area")
            area_opcoes = ["All"] + sorted(df_original['area'].unique().tolist())
            area_selecionada = st.selectbox("", area_opcoes, label_visibility="collapsed")
        
        with col3:
            st.subheader("Stage")
            stage_opcoes = ["All"] + sorted(df_original['stage'].unique().tolist())
            stage_selecionado = st.selectbox("", stage_opcoes, label_visibility="collapsed")

    # Aplica os filtros
    if periodo_opcoes[periodo_selecionado] >= 0:
        if periodo_selecionado == "Today":
            hoje = datetime.now().date()
            df_original = df_original[df_original['row_inserted_date'].dt.date == hoje]
        else:
            data_limite = datetime.now() - timedelta(days=periodo_opcoes[periodo_selecionado])
            df_original = df_original[df_original['row_inserted_date'] >= data_limite]
    
    if status_selecionado != "All":
        df_original = df_original[df_original['status'] == status_selecionado]
    
    if area_selecionada != "All":
        df_original = df_original[df_original['area'] == area_selecionada]
    
    if stage_selecionado != "All":
        df_original = df_original[df_original['stage'] == stage_selecionado]
    
    if st.session_state.busca:
        df_original = df_original[df_original['farol_reference'].str.contains(st.session_state.busca, case=False)]

    # Ordena o DataFrame por farol_reference e row_inserted_date
    df_original = df_original.sort_values(['farol_reference', 'row_inserted_date'], ascending=[True, False])
    
    # Agrupa por farol_reference
    unique_farol_refs = df_original['farol_reference'].unique()

    # Mostra contadores em cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Adjustments", len(df_original))
    with col2:
        st.metric("📦 Farol References", len(unique_farol_refs))
    with col3:
        pending_farol_refs = df_original[df_original['status'] == 'Adjustment Requested']['farol_reference'].unique()
        st.metric("⏳ Pending Adjustments", len(pending_farol_refs))

    # Exibe diretamente a grade de dados ajustados
    if not df_original.empty:
        # Gera os dados ajustados
        df_adjusted = get_adjusted_sales_data(unique_farol_refs, df_original)
        
        # Normaliza status vazios no DataFrame final antes de exibir
        if not df_adjusted.empty and 'Status' in df_adjusted.columns:
            df_adjusted['Status'] = df_adjusted['Status'].apply(
                lambda x: "Adjustment Requested" if pd.isna(x) or x == "" or x is None or str(x).strip() == "" else x
            )
        
        if not df_adjusted.empty:
            # Adiciona coluna Attachments com a contagem de anexos por Farol Reference
            def count_attachments(farol_ref):
                conn = get_database_connection()
                try:
                    query = text("""
                        SELECT COUNT(*) as total FROM LogTransp.F_CON_ANEXOS WHERE farol_reference = :ref
                    """)
                    result = conn.execute(query, {"ref": farol_ref}).fetchone()
                    return int(result[0]) if result else 0
                finally:
                    conn.close()
            
            df_adjusted['Attachments'] = df_adjusted['Sales Farol Reference'].apply(count_attachments)
            # Reordena para colocar Attachments antes de Comments
            cols = list(df_adjusted.columns)
            if 'Attachments' in cols and 'Comments' in cols:
                cols.insert(cols.index('Comments'), cols.pop(cols.index('Attachments')))
                df_adjusted = df_adjusted[cols]

            # Obtém as opções de status da UDC
            farol_status_options = df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()
            relevant_status = [
                "Adjustment Requested",  # Status padrão sempre primeiro
                "Booking Approved", 
                "Booking Rejected",
                "Booking Cancelled",
                "Received from Carrier"
            ]
            # Filtra apenas os status que existem na UDC, mantendo a ordem
            available_options = [status for status in relevant_status if status in farol_status_options]
            if not available_options:
                available_options = relevant_status
            
            # Garante que "Adjustment Requested" esteja sempre disponível e seja o primeiro
            if "Adjustment Requested" not in available_options:
                available_options.insert(0, "Adjustment Requested")
            elif available_options[0] != "Adjustment Requested":
                # Move "Adjustment Requested" para o início se não estiver
                available_options.remove("Adjustment Requested")
                available_options.insert(0, "Adjustment Requested")
            
            # Remove qualquer opção vazia ou None que possa estar na lista - MÚLTIPLAS VERIFICAÇÕES
            available_options = [opt for opt in available_options if opt and str(opt).strip() and opt != "" and opt != " " and not pd.isna(opt) and opt is not None]
            
            # Garante que sempre temos pelo menos "Adjustment Requested" se a lista ficar vazia
            if not available_options:
                available_options = ["Adjustment Requested"]
            
            # Adiciona coluna de seleção (checkbox) igual ao shipments.py
            df_adjusted['Selecionar'] = False
            # Reordena colunas para colocar 'Selecionar' no início
            colunas_ordenadas = ['Selecionar'] + [col for col in df_adjusted.columns if col != 'Selecionar']

            # Configuração das colunas, adicionando a coluna de seleção
            column_config = {
                'Selecionar': st.column_config.CheckboxColumn('Select', help='Selecione apenas uma linha'),
                "Sales Farol Reference": st.column_config.TextColumn("Farol Reference", width="medium", disabled=True),
                "Status": st.column_config.SelectboxColumn("Status", width="medium", options=available_options, default="Adjustment Requested"),
                "Sales Quantity of Containers": st.column_config.NumberColumn("Quantity", format="%d", disabled=True),
                "Sales Port of Loading POL": st.column_config.TextColumn("POL", width="medium", disabled=True),
                "Sales Port of Delivery POD": st.column_config.TextColumn("POD", width="medium", disabled=True),
                "Sales Place of Receipt": st.column_config.TextColumn("Place of Receipt", width="medium", disabled=True),
                "Sales Final Destination": st.column_config.TextColumn("Final Destination", width="medium", disabled=True),
                "Carrier": st.column_config.TextColumn("Carrier", width="medium", disabled=True),
                "Requested Cut off Start Date": st.column_config.DateColumn("Cut-off Start", disabled=True),
                "Requested Cut off End Date": st.column_config.DateColumn("Cut-off End", disabled=True),
                "Required Arrival Date": st.column_config.DateColumn("Required Arrival", disabled=True),
                "Changes Made": st.column_config.TextColumn("Changes Made", width="large", disabled=True),
                "Attachments": st.column_config.NumberColumn("Attachments", format="%d", disabled=True),
                "Comments": st.column_config.TextColumn("Comments", width="large", disabled=True),
                "Adjustment ID": st.column_config.TextColumn("Adjustment ID", width="medium", disabled=True)
            }

            # Exibe a tabela editável com a coluna de seleção
            edited_df = st.data_editor(
                df_adjusted[colunas_ordenadas],
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                key="adjusted_data_editor"
            )

            # Permitir selecionar apenas uma linha por vez
            selected_rows = edited_df[edited_df['Selecionar'] == True]
            if len(selected_rows) > 1:
                st.warning("⚠️ Por favor, selecione apenas **uma** linha.")
            selected_farol_ref = selected_rows['Sales Farol Reference'].values[0] if len(selected_rows) == 1 else None
            st.session_state['selected_farol_ref'] = selected_farol_ref
            
            # Detecta mudanças no status e aplica atualizações
            status_changes = []
            for i in range(len(df_adjusted)):
                original_status = df_adjusted.iloc[i]['Status']
                new_status = edited_df.iloc[i]['Status']
                farol_ref = df_adjusted.iloc[i]['Sales Farol Reference']
                
                if original_status != new_status:
                    status_changes.append({
                        'farol_reference': farol_ref,
                        'old_status': original_status,
                        'new_status': new_status
                    })
            
            # Aplica as mudanças de status se houver
            if status_changes:
                st.markdown("---")
                st.markdown("### 🔄 Status Changes Detected")
                
                for change in status_changes:
                    st.info(f"**{change['farol_reference']}**: {change['old_status']} → {change['new_status']}")
                
                # Reorganizar os botões para ficarem lado a lado: Apply, Cancel, View Attachments, Back
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("✅ Apply Changes", key="apply_status_changes"):
                        success_count = 0
                        error_count = 0
                        
                        for change in status_changes:
                            try:
                                conn = get_database_connection()
                                transaction = conn.begin()
                                
                                # Atualiza o status nos ajustes
                                update_log_query = text("""
                                    UPDATE LogTransp.F_CON_Adjustments_Log
                                    SET status = :new_status,
                                        confirmation_date = :confirmation_date
                                    WHERE farol_reference = :farol_reference
                                """)
                                
                                conn.execute(update_log_query, {
                                    "new_status": change['new_status'],
                                    "confirmation_date": datetime.now() if change['new_status'] in ["Booking Approved", "Booking Rejected", "Booking Cancelled"] else None,
                                    "farol_reference": change['farol_reference']
                                })
                                
                                # Determina os stages dos ajustes para esta referência
                                stages_query = text("""
                                    SELECT DISTINCT stage 
                                    FROM LogTransp.F_CON_Adjustments_Log 
                                    WHERE farol_reference = :farol_reference
                                """)
                                stages_result = conn.execute(stages_query, {"farol_reference": change['farol_reference']}).fetchall()
                                stages = [row[0] for row in stages_result]
                                
                                # Atualiza o status nas tabelas principais
                                if "Sales Data" in stages:
                                    update_sales_query = text("""
                                        UPDATE LogTransp.F_CON_SALES_DATA
                                        SET farol_status = :farol_status
                                        WHERE s_farol_reference = :farol_reference
                                    """)
                                    conn.execute(update_sales_query, {
                                        "farol_status": change['new_status'],
                                        "farol_reference": change['farol_reference']
                                    })
                                
                                if "Booking Management" in stages:
                                    update_booking_query = text("""
                                        UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
                                        SET farol_status = :farol_status
                                        WHERE b_farol_reference = :farol_reference
                                    """)
                                    conn.execute(update_booking_query, {
                                        "farol_status": change['new_status'],
                                        "farol_reference": change['farol_reference']
                                    })
                                
                                if "Container Delivery at Port" in stages:
                                    update_loading_query = text("""
                                        UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
                                        SET farol_status = :farol_status
                                        WHERE l_farol_reference = :farol_reference
                                    """)
                                    conn.execute(update_loading_query, {
                                        "farol_status": change['new_status'],
                                        "farol_reference": change['farol_reference']
                                    })
                                
                                transaction.commit()
                                success_count += 1
                                
                            except Exception as e:
                                if 'transaction' in locals():
                                    transaction.rollback()
                                st.error(f"Error updating {change['farol_reference']}: {str(e)}")
                                error_count += 1
                            finally:
                                if 'conn' in locals():
                                    conn.close()
                        
                        if success_count > 0:
                            st.success(f"✅ Successfully updated {success_count} status(es)!")
                            if error_count == 0:
                                st.rerun()
                        if error_count > 0:
                            st.error(f"❌ {error_count} update(s) failed!")
                
                with col2:
                    if st.button("❌ Cancel Changes", key="cancel_status_changes"):
                        st.rerun()
                with col3:
                    if st.button("📎 View Attachments", key="view_attachments_changes", disabled=(selected_farol_ref is None)):
                        st.session_state["show_attachments"] = True
                        st.session_state["attachments_farol_ref"] = selected_farol_ref
                        st.rerun()
                with col4:
                    if st.button("🔙 Back to Shipments", key="back_to_shipments_changes"):
                        st.session_state["navigate_to"] = "Shipments"
                        st.rerun()
            else:
                # Seção de botões quando não há mudanças de status
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("🔙 Back to Shipments"):
                        st.session_state["navigate_to"] = "Shipments"
                        st.rerun()
                with col2:
                    if st.button("📎 View Attachments", key="view_attachments_no_changes", disabled=(selected_farol_ref is None)):
                        st.session_state["show_attachments"] = True
                        st.session_state["attachments_farol_ref"] = selected_farol_ref
                        st.rerun()
                # col3 e col4 ficam vazios
            # Seção de Anexos
            if st.session_state.get("show_attachments", False):
                st.markdown("---")
                st.markdown("### 📎 Attachment Management")
                farol_ref = st.session_state.get("attachments_farol_ref")
                if farol_ref:
                    display_attachments_section(farol_ref)
                else:
                    st.info("Selecione uma linha para visualizar os anexos.")
                if st.button("🔼 Hide Attachments", key="hide_attachments"):
                    st.session_state["show_attachments"] = False
                    st.rerun()
        else:
            st.info("Nenhum dado ajustado encontrado. Verifique se há ajustes registrados para as referências filtradas.")
            # Botões juntos e alinhados
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("🔙 Back to Shipments", key="back_no_adjusted_data"):
                    st.session_state["navigate_to"] = "Shipments"
                    st.rerun()
            with col2:
                if st.button("📎 View Attachments", key="view_attachments_no_adjusted_data", disabled=(selected_farol_ref is None)):
                    st.session_state["show_attachments"] = True
                    st.session_state["attachments_farol_ref"] = selected_farol_ref
                    st.rerun()
            # col3 e col4 ficam vazios
            # Seção de Anexos mesmo sem dados ajustados
            if st.session_state.get("show_attachments", False):
                st.markdown("---")
                st.markdown("### 📎 Attachment Management")
                farol_ref = st.session_state.get("attachments_farol_ref")
                if farol_ref:
                    display_attachments_section(farol_ref)
                else:
                    st.info("Selecione uma linha para visualizar os anexos.")
                if st.button("🔼 Hide Attachments", key="hide_attachments_no_adjusted"):
                    st.session_state["show_attachments"] = False
                    st.rerun()
    else:
        st.info("Nenhum ajuste encontrado. Use os filtros acima para localizar ajustes específicos.")
        # Botões quando não há ajustes
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🔙 Back to Shipments", key="back_no_adjustments"):
                st.session_state["navigate_to"] = "Shipments"
                st.rerun()
        # Removido botão e input manual de anexos para referência manual

if __name__ == "__main__":
    exibir_adjustments()
 