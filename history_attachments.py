import streamlit as st
import hashlib
import traceback
from io import BytesIO
import zipfile
import pandas as pd

from history_data import (
    save_attachment_to_db, 
    get_attachments_for_farol, 
    delete_attachment, 
    get_attachment_content
)
from history_helpers import get_file_icon, format_file_size, load_custom_css
from pdf_booking_processor import process_pdf_booking, display_pdf_validation_interface, save_pdf_booking_data

def display_attachments_section(farol_reference):
    """
    Exibe a seção de anexos para um Farol Reference específico.
    """
    load_custom_css()

    uploader_version_key = f"uploader_ver_{farol_reference}"
    if uploader_version_key not in st.session_state:
        st.session_state[uploader_version_key] = 0
    current_uploader_version = st.session_state[uploader_version_key]

    expander_key = f"expander_state_{farol_reference}"
    if expander_key not in st.session_state:
        st.session_state[expander_key] = False
    
    if f"processed_pdf_data_{farol_reference}" in st.session_state:
        st.session_state[expander_key] = True

    with st.expander("📤 Add New Attachment", expanded=st.session_state[expander_key]):
        process_booking_pdf = st.checkbox(
            "📄 Processar PDF de Booking recebido por e-mail", 
            key=f"process_booking_checkbox_{farol_reference}",
            help="Marque esta opção se o arquivo é um PDF de booking que precisa ser processado e validado"
        )
        
        if process_booking_pdf:
            st.session_state[expander_key] = True
        else:
            if f"processed_pdf_data_{farol_reference}" in st.session_state:
                del st.session_state[f"processed_pdf_data_{farol_reference}"]
            if f"booking_pdf_file_{farol_reference}" in st.session_state:
                del st.session_state[f"booking_pdf_file_{farol_reference}"]
            st.session_state[f"uploader_booking_{farol_reference}_{current_uploader_version}"] = None
            st.rerun()

        uploaded_file = None
        uploaded_files = []
        if process_booking_pdf:
            uploaded_file = st.file_uploader(
                "Selecione o PDF de Booking", type=['pdf'], 
                key=f"uploader_booking_{farol_reference}_{current_uploader_version}"
            )
        else:
            uploaded_files = st.file_uploader(
                "Drag and drop files here or click to select", accept_multiple_files=True,
                type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'],
                key=f"uploader_regular_{farol_reference}_{current_uploader_version}"
            )
        
        # Processamento de PDF de Booking
        if process_booking_pdf and uploaded_file:
            handle_pdf_processing(uploaded_file, farol_reference)
        
        # Processamento de anexos regulares
        elif not process_booking_pdf and uploaded_files:
            if st.button("💾 Save Attachments", key=f"save_attachments_{farol_reference}", type="primary"):
                handle_regular_attachments(uploaded_files, farol_reference)
        
        # Interface de validação de PDF
        if process_booking_pdf and f"processed_pdf_data_{farol_reference}" in st.session_state:
            handle_pdf_validation(farol_reference)

    # Lista de Anexos Existentes
    st.divider()
    with st.expander("📎 Attachments", expanded=False):
        display_existing_attachments(farol_reference)

def handle_pdf_processing(uploaded_file, farol_reference):
    last_file_key = f"last_processed_file_{farol_reference}"
    uploaded_file.seek(0)
    file_hash = hashlib.md5(uploaded_file.read()).hexdigest()
    uploaded_file.seek(0)
    
    is_new_file = st.session_state.get(last_file_key, "") != file_hash
    
    if is_new_file:
        with st.spinner("🔄 Processando PDF e extraindo dados..."):
            try:
                pdf_content = uploaded_file.read()
                processed_data = process_pdf_booking(pdf_content, farol_reference)
                
                if processed_data:
                    for key in [f"api_dates_{farol_reference}", f"api_consulted_{farol_reference}"]:
                        st.session_state.pop(key, None)
                    
                    st.session_state[f"processed_pdf_data_{farol_reference}"] = processed_data
                    st.session_state[f"booking_pdf_file_{farol_reference}"] = uploaded_file
                    st.session_state[last_file_key] = file_hash
                    st.success("✅ Dados extraídos com sucesso! Valide as informações abaixo:")
                    st.rerun()
                else:
                    st.error("❌ Processamento retornou dados vazios")
            except Exception as e:
                st.error(f"❌ Erro durante o processamento: {str(e)}")
                st.code(traceback.format_exc())

def handle_regular_attachments(uploaded_files, farol_reference):
    progress_bar = st.progress(0, text="Saving attachments...")
    success_count = 0
    for i, file in enumerate(uploaded_files):
        file.seek(0)
        if save_attachment_to_db(farol_reference, file, user_id=st.session_state.get('current_user', 'system')):
            success_count += 1
        progress_bar.progress((i + 1) / len(uploaded_files), text=f"Saving attachment {i+1} of {len(uploaded_files)}...")
    
    progress_bar.empty()
    if success_count == len(uploaded_files):
        st.success(f"✅ {success_count} attachment(s) saved successfully!")
    else:
        st.warning(f"⚠️ {success_count} of {len(uploaded_files)} attachments were saved.")

    st.session_state[f"uploader_ver_{farol_reference}"] += 1
    st.rerun()

def handle_pdf_validation(farol_reference):
    processed_data = st.session_state[f"processed_pdf_data_{farol_reference}"]
    validated_data = display_pdf_validation_interface(processed_data)
    
    if validated_data == "CANCELLED":
        st.session_state.pop(f"processed_pdf_data_{farol_reference}", None)
        st.session_state.pop(f"booking_pdf_file_{farol_reference}", None)
        st.session_state[f"expander_state_{farol_reference}"] = False
        st.rerun()
    elif validated_data:
        if save_pdf_booking_data(validated_data):
            st.session_state.pop(f"processed_pdf_data_{farol_reference}", None)
            st.session_state.pop(f"booking_pdf_file_{farol_reference}", None)
            st.session_state[f"expander_state_{farol_reference}"] = False
            st.balloons()
            st.cache_data.clear()
            st.rerun()

def display_existing_attachments(farol_reference):
    attachments_df = get_attachments_for_farol(farol_reference)
    if attachments_df.empty:
        st.info("📂 No attachments found for this reference.")
        return

    dfv = attachments_df.sort_values('upload_date', ascending=False).reset_index(drop=True)
    
    # Paginação
    page_size = st.selectbox("Items per page", [6, 9, 12], index=1, key=f"att_page_size_{farol_reference}")
    total_items = len(dfv)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    page_key = f"att_page_{farol_reference}"
    current_page = st.session_state.get(page_key, 1)
    current_page = max(1, min(current_page, total_pages))

    # Navegação da Paginação
    nav_prev, nav_info, nav_next = st.columns([1, 2, 1])
    if nav_prev.button("⬅️ Prev", disabled=current_page <= 1, key=f"att_prev_{farol_reference}"):
        st.session_state[page_key] = current_page - 1
        st.rerun()
    nav_info.caption(f"Page {current_page} of {total_pages} • {total_items} item(s)")
    if nav_next.button("Next ➡️", disabled=current_page >= total_pages, key=f"att_next_{farol_reference}"):
        st.session_state[page_key] = current_page + 1
        st.rerun()

    start_idx = (current_page - 1) * page_size
    page_df = dfv.iloc[start_idx:start_idx + page_size]

    # Tabela de Anexos
    h1, h2, h3, h4, h5, h6 = st.columns([5, 2, 2, 2, 1, 1])
    h1.markdown("**File**"); h2.markdown("**Type/Ext**"); h3.markdown("**User**"); h4.markdown("**Date**"); h5.markdown("**Download**"); h6.markdown("**Delete**")

    for _, att in page_df.iterrows():
        row_key = f"{farol_reference}_{att['id']}"
        c1, c2, c3, c4, c5, c6 = st.columns([5, 2, 2, 2, 1, 1])
        c1.write(att.get('full_file_name', att['file_name']))
        c2.write(att.get('mime_type') or (att.get('file_extension') or '').lower() or 'N/A')
        c3.write(att.get('uploaded_by', ''))
        c4.write(att['upload_date'].strftime('%Y-%m-%d %H:%M') if pd.notna(att['upload_date']) else 'N/A')
        
        fc, fn, mt = get_attachment_content(att['id'])
        c5.download_button("⬇️", data=fc or b"", file_name=fn or "file", mime=mt or "application/octet-stream", key=f"dl_{row_key}", use_container_width=True, disabled=fc is None)
        
        confirm_key = f"confirm_del_{row_key}"
        if not st.session_state.get(confirm_key, False):
            if c6.button("🗑️", key=f"del_{row_key}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()
        else:
            wc1, wc2, wc3 = st.columns([6, 1, 1])
            wc1.warning("Are you sure?")
            if wc2.button("✅ Yes", key=f"yes_{row_key}"):
                if delete_attachment(att['id'], deleted_by=st.session_state.get('current_user', 'system')):
                    st.success("Attachment deleted!")
                else:
                    st.error("Error deleting attachment!")
                st.session_state[confirm_key] = False
                st.rerun()
            if wc3.button("❌ No", key=f"no_{row_key}"):
                st.session_state[confirm_key] = False
                st.rerun()

    # Download em lote
    if not dfv.empty:
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for _, att in dfv.iterrows():
                fc, fn, _ = get_attachment_content(att['id'])
                if fc and fn:
                    zf.writestr(fn, fc)
        st.download_button("⬇️ Download all as .zip", data=buf.getvalue(), file_name=f"attachments_{farol_reference}.zip", mime="application/zip", key=f"dl_zip_{farol_reference}")
