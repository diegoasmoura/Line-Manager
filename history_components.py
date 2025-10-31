import streamlit as st
import pandas as pd
from shipments_mapping import get_column_mapping, process_farol_status_for_display
from history_helpers import format_linked_reference_display, convert_utc_to_brazil_time
from database import (
    approve_carrier_return, update_record_status,
    get_return_carrier_status_by_adjustment_id,
    history_get_available_references_for_relation,
    load_df_udc
)

# Este módulo consolidará as seções de UI da tela History sem alterar o layout.
# Etapas seguintes migrarão gradualmente o código de history.py para cá.


def render_metrics_header(*, farol_reference: str, main_status: str, qty: int, voyage_carrier: str, inserted: str) -> None:
    """Renderiza os 5 cards superiores de métricas, preservando o layout atual."""
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")

    with col1:
        st.markdown(f"""
        <div style="
            background: white; padding: 1rem; border-radius: 12px; border-left: 4px solid #00843D;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL REFERENCE</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{farol_reference}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="
            background: white; padding: 1rem; border-radius: 12px; border-left: 4px solid #3599B8;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL STATUS</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{main_status}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="
            background: white; padding: 1rem; border-radius: 12px; border-left: 4px solid #4AC5BB;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">QUANTITY OF CONTAINERS</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{qty}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="
            background: white; padding: 1rem; border-radius: 12px; border-left: 4px solid #168980;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">VOYAGE CARRIER</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{voyage_carrier}</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div style="
            background: white; padding: 1rem; border-radius: 12px; border-left: 4px solid #28738A;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center;">
            <div style="color: #03441F; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">INSERTED</div>
            <div style="color: #001A33; font-size: 1rem; font-weight: 600;">{inserted}</div>
        </div>
        """, unsafe_allow_html=True)


def render_divider():
    st.markdown("---")


def render_action_buttons(farol_reference: str, combined_df: pd.DataFrame) -> None:
    """
    Renderiza a seção de botões de ação (View Attachments, Export CSV, Back to Shipments).
    
    Args:
        farol_reference: Referência Farol atual
        combined_df: DataFrame unificado para exportação CSV
    """
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
            st.download_button(
                "⬇️ Export CSV",
                data=combined_df.to_csv(index=False).encode("utf-8"),
                file_name=f"return_carriers_{farol_reference}.csv",
                mime="text/csv"
            )
        else:
            st.download_button(
                "⬇️ Export CSV",
                data="".encode("utf-8"),
                file_name=f"return_carriers_{farol_reference}.csv",
                mime="text/csv",
                disabled=True
            )
    
    with col3:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()


# As seções abaixo serão migradas nas próximas etapas sem alterar o layout ou keys.

from pdf_booking_processor import (
    process_pdf_booking,
    display_pdf_validation_interface,
    save_pdf_booking_data,
)
from database import (
    history_save_attachment,
    history_get_attachments,
    history_delete_attachment,
    history_get_attachment_content,
)


def display_attachments_section(farol_reference: str) -> None:
    """Exibe a seção de anexos para um Farol Reference específico (layout preservado)."""
    st.markdown(
        """
    <style>
    .attachment-card { border: 1px solid #e0e0e0; border-radius: 12px; padding: 18px; margin: 15px 0; background: linear-gradient(145deg, #ffffff, #f8f9fa); box-shadow: 0 3px 10px rgba(0,0,0,0.08); transition: all 0.3s ease; text-align: center; border-left: 4px solid #1f77b4; }
    .attachment-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.12); border-left-color: #0d47a1; }
    .file-icon { font-size: 3em; margin-bottom: 15px; display: block; }
    .file-name { font-weight: bold; font-size: 16px; margin-bottom: 10px; color: #333; word-wrap: break-word; }
    .file-info { font-size: 13px; color: #666; margin: 5px 0; display: flex; align-items: center; justify-content: center; gap: 8px; }
    .metric-card { background: linear-gradient(145deg, #f0f8ff, #e6f3ff); border-radius: 10px; padding: 15px; margin: 10px 0; border: 1px solid #b3d9ff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .attachment-section { background-color: #fafafa; border-radius: 10px; padding: 20px; margin: 20px 0; border: 1px solid #e0e0e0; }
    .upload-area { background-color: #f8f9fa; border: 2px dashed #dee2e6; border-radius: 8px; padding: 20px; margin: 15px 0; text-align: center; }
    .stTabs [data-baseweb="tab-list"] { gap: 0px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; color: #262730; padding: 10px 16px; font-weight: 400; border: none; transition: none; }
    .stTabs [aria-selected="true"] { background-color: #ffffff; color: #262730; border-bottom: 2px solid #00acb5; font-weight: 600; }
    .stExpander { transition: none; }
    .stButton > button { transition: none; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    uploader_version_key = f"uploader_ver_{farol_reference}"
    if uploader_version_key not in st.session_state:
        st.session_state[uploader_version_key] = 0
    current_uploader_version = st.session_state[uploader_version_key]

    cache_key = f"attachment_cache_{farol_reference}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = {"last_update": 0}

    expander_key = f"expander_state_{farol_reference}"
    if expander_key not in st.session_state:
        st.session_state[expander_key] = False

    processed_data_key = f"processed_pdf_data_{farol_reference}"
    if processed_data_key in st.session_state:
        st.session_state[expander_key] = True

    with st.expander("📤 Add New Attachment", expanded=st.session_state[expander_key]):
        process_booking_pdf = st.checkbox(
            "📄 Processar PDF de Booking recebido por e-mail",
            key=f"process_booking_checkbox_{farol_reference}",
            help="Marque esta opção se o arquivo é um PDF de booking que precisa ser processado e validado",
        )

        if process_booking_pdf:
            st.session_state[expander_key] = True
        else:
            if processed_data_key in st.session_state:
                del st.session_state[processed_data_key]
            if f"booking_pdf_file_{farol_reference}" in st.session_state:
                del st.session_state[f"booking_pdf_file_{farol_reference}"]
            st.session_state[f"uploader_booking_{farol_reference}_{current_uploader_version}"] = None
            st.rerun()

        if process_booking_pdf:
            uploaded_file = st.file_uploader(
                "Selecione o PDF de Booking",
                accept_multiple_files=False,
                type=["pdf"],
                key=f"uploader_booking_{farol_reference}_{current_uploader_version}",
                help="Selecione apenas PDFs de booking recebidos por e-mail • Limit 200MB per file • PDF",
            )
        else:
            uploaded_files = st.file_uploader(
                "Drag and drop files here or click to select",
                accept_multiple_files=True,
                type=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "ppt",
                    "pptx",
                    "txt",
                    "csv",
                    "png",
                    "jpg",
                    "jpeg",
                    "gif",
                    "zip",
                    "rar",
                ],
                key=f"uploader_regular_{farol_reference}_{current_uploader_version}",
                help="Supported file types: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, PNG, JPG, JPEG, GIF, ZIP, RAR",
            )

        if process_booking_pdf and uploaded_file:
            import hashlib

            last_file_key = f"last_processed_file_{farol_reference}"
            uploaded_file.seek(0)
            file_hash = hashlib.md5(uploaded_file.read()).hexdigest()
            uploaded_file.seek(0)
            is_new_file = st.session_state.get(last_file_key, "") != file_hash

            if is_new_file:
                with st.spinner("🔄 Processando PDF e extraindo dados..."):
                    try:
                        uploaded_file.seek(0)
                        pdf_content = uploaded_file.read()
                        processed_data = process_pdf_booking(pdf_content, farol_reference)
                        if processed_data:
                            api_dates_key = f"api_dates_{farol_reference}"
                            if api_dates_key in st.session_state:
                                del st.session_state[api_dates_key]
                            api_consulted_key = f"api_consulted_{farol_reference}"
                            if api_consulted_key in st.session_state:
                                del st.session_state[api_consulted_key]

                            st.session_state[f"processed_pdf_data_{farol_reference}"] = processed_data
                            st.session_state[f"booking_pdf_file_{farol_reference}"] = uploaded_file
                            st.session_state[last_file_key] = file_hash

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
                    file.seek(0)
                    if history_save_attachment(farol_reference, file):
                        success_count += 1
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress, text=f"Saving attachment {i+1} of {len(uploaded_files)}...")
                progress_bar.empty()
                if success_count == len(uploaded_files):
                    st.success(f"✅ {success_count} attachment(s) saved successfully!")
                else:
                    st.warning(f"⚠️ {success_count} of {len(uploaded_files)} attachments were saved.")
                st.session_state[uploader_version_key] += 1
                if cache_key in st.session_state:
                    st.session_state[cache_key]["last_update"] = st.session_state[uploader_version_key]
                st.rerun()

        if process_booking_pdf:
            if processed_data_key in st.session_state:
                processed_data = st.session_state[processed_data_key]
                validated_data = display_pdf_validation_interface(processed_data)
                if validated_data == "CANCELLED":
                    del st.session_state[processed_data_key]
                    if f"booking_pdf_file_{farol_reference}" in st.session_state:
                        del st.session_state[f"booking_pdf_file_{farol_reference}"]
                    st.session_state[expander_key] = False
                    st.rerun()
                elif validated_data:
                    if save_pdf_booking_data(validated_data):
                        del st.session_state[processed_data_key]
                        if f"booking_pdf_file_{farol_reference}" in st.session_state:
                            del st.session_state[f"booking_pdf_file_{farol_reference}"]
                        st.session_state[expander_key] = False
                        st.balloons()
                        st.cache_data.clear()
                        st.rerun()

    attachments_df = history_get_attachments(farol_reference)
    st.divider()
    with st.expander("📎 Attachments", expanded=False):
        if not attachments_df.empty:
            dfv = attachments_df.sort_values("upload_date", ascending=False).reset_index(drop=True)
            page_size = st.selectbox(
                "Items per page",
                options=[6, 9, 12],
                index=1,
                key=f"att_page_size_{farol_reference}",
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
                    st.write(att.get("full_file_name", att["file_name"]))
                with c2:
                    ext = (att.get("file_extension") or "").lower()
                    st.write(att.get("mime_type") or ext or "N/A")
                with c3:
                    st.write(att.get("uploaded_by", ""))
                with c4:
                    st.write(
                        att["upload_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(att["upload_date"]) else "N/A"
                    )
                with c5:
                    fc, fn, mt = history_get_attachment_content(att["id"])
                    st.download_button(
                        "⬇️",
                        data=fc or b"",
                        file_name=fn or "file",
                        mime=mt or "application/octet-stream",
                        key=f"dl_flat_{row_key}",
                        use_container_width=True,
                        disabled=fc is None,
                    )
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
                            if history_delete_attachment(
                                att["id"], deleted_by=st.session_state.get("current_user", "system")
                            ):
                                st.success("✅ Attachment deleted successfully!")
                            else:
                                st.error("❌ Error deleting attachment!")
                            st.session_state[confirm_key] = False
                            st.rerun()
                    with wc3:
                        if st.button("❌ No", key=f"no_flat_{row_key}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()

            from io import BytesIO
            import zipfile

            fc_total = []
            for _, att in dfv.iterrows():
                fc, fn, mt = history_get_attachment_content(att["id"])
                if fc and fn:
                    fc_total.append((fn, fc))
            if fc_total:
                buf = BytesIO()
                with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for fn, fc in fc_total:
                        zf.writestr(fn, fc)
                st.download_button(
                    "⬇️ Download all as .zip",
                    data=buf.getvalue(),
                    file_name="attachments.zip",
                    mime="application/zip",
                    key=f"dl_zip_all_{farol_reference}",
                )
        else:
            st.info("📂 No attachments found for this reference.")
            st.markdown(
                "💡 **Tip:** Use the 'Add New Attachment' section above to upload files related to this Farol Reference."
            )


def display_audit_trail_tab(farol_reference: str) -> None:  # será migrada do history.py
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


# ========== Request Timeline Functions ==========

def _calculate_column_width(df, column_name):
    """Calcula largura dinâmica baseada no conteúdo e título da coluna"""
    if column_name not in df.columns:
        return "small"
    title_length = len(column_name)
    sample_size = min(10, len(df))
    if sample_size > 0:
        content_lengths = df[column_name].dropna().astype(str).str.len()
        max_content_length = content_lengths.max() if len(content_lengths) > 0 else 0
    else:
        max_content_length = 0
    total_length = max(title_length, max_content_length)
    if total_length <= 12:
        return "small"
    elif total_length <= 20:
        return "medium"
    else:
        return "large"


def _generate_dynamic_column_config(df, hide_status=False, hide_linked_reference=False):
    """Gera configuração de colunas com larguras dinâmicas"""
    config = {
        "ADJUSTMENT_ID": None,
        "Status": None,
        "Index": st.column_config.NumberColumn("Index", help="Índice da linha", width="small", disabled=True, format="%d"),
    }
    for col in df.columns:
        if col in config:
            continue
        if col == "ID":
            config[col] = None
            continue
        if col == "Status" and hide_status:
            config[col] = None
            continue
        if col == "Linked Reference" and hide_linked_reference:
            config[col] = None
            continue
        
        # Definir larguras específicas por coluna
        if col == "Linked Reference":
            width = "large"  # Largura grande para evitar corte de texto
        elif col in ["Quantity of Containers"]:
            width = "medium"
        else:
            # Todas as outras colunas usam largura "medium" como padrão
            width = "medium"
        
        # Todas as colunas (incluindo datas) são tratadas como TextColumn
        # Isso evita problemas de conversão do Streamlit que exibem "None" em campos vazios
        # Como a tabela é somente leitura, não há necessidade de DatetimeColumn
        if col in ["Quantity of Containers"]:
            config[col] = st.column_config.NumberColumn(col, width=width)
        else:
            config[col] = st.column_config.TextColumn(col, width=width)
    return config


def _process_dataframe(df_to_process, farol_reference):
    """Processa um DataFrame aplicando aliases e configurações"""
    if df_to_process.empty:
        return df_to_process

    mapping_main = get_column_mapping()
    mapping_upper = {k.upper(): v for k, v in mapping_main.items()}

    def prettify(col: str) -> str:
        label = col.replace("_", " ").title()
        replaces = {
            "Pol": "POL", "Pod": "POD", "Etd": "ETD", "Eta": "ETA", "Pdf": "PDF", "Id": "ID",
        }
        for k, v in replaces.items():
            label = label.replace(k, v)
        return label

    custom_overrides = {
        "ID": "ID", "FAROL_REFERENCE": "Farol Reference", "B_BOOKING_REFERENCE": "Booking",
        "ADJUSTMENT_ID": "ADJUSTMENT_ID", "LINKED_REFERENCE": "Linked Reference",
        "FAROL_STATUS": "Farol Status", "ROW_INSERTED_DATE": "Inserted Date",
        "ADJUSTMENTS_OWNER": "Adjustments Owner", "P_PDF_NAME": "PDF Name",
        "PDF_BOOKING_EMISSION_DATE": "PDF Booking Emission Date", "S_QUANTITY_OF_CONTAINERS": "Quantity of Containers",
        "B_VOYAGE_CODE": "Voyage Code", "B_VESSEL_NAME": "Vessel Name", "B_VOYAGE_CARRIER": "Carrier",
        "B_TRANSHIPMENT_PORT": "Transhipment Port", "B_TERMINAL": "Port Terminal",
        "S_PORT_OF_LOADING_POL": "Port of Loading POL", "S_PORT_OF_DELIVERY_POD": "Port of Delivery POD",
        "S_PLACE_OF_RECEIPT": "Place of Receipt", "S_FINAL_DESTINATION": "Final Destination",
        "data_required_arrival_expected": "Required Arrival Date",
        "data_requested_deadline_start": "Requested Deadline Start",
        "data_requested_deadline_end": "Requested Deadline End",
        "data_draft_deadline": "Draft Deadline", "data_deadline": "Deadline",
        "data_estimativa_saida": "ETD", "data_estimativa_chegada": "ETA",
        "data_abertura_gate": "Abertura Gate", "data_confirmacao_embarque": "Confirmação Embarque",
        "data_estimada_transbordo": "Estimada Transbordo (ETD)", "data_transbordo": "Transbordo (ATD)",
        "data_estimativa_atracacao": "Estimativa Atracação (ETB)", "data_atracacao": "Atracação (ATB)",
        "data_partida": "Partida (ATD)", "data_chegada": "Chegada (ATA)",
        "B_DATA_ABERTURA_GATE": "Abertura Gate", "B_DATA_CONFIRMACAO_EMBARQUE": "Confirmação Embarque",
        "B_DATA_ESTIMADA_TRANSBORDO_ETD": "Estimada Transbordo (ETD)", "B_DATA_TRANSBORDO_ATD": "Transbordo (ATD)",
        "B_DATA_DRAFT_DEADLINE": "Draft Deadline", "B_DATA_DEADLINE": "Deadline",
        "S_REQUESTED_DEADLINE_START_DATE": "Requested Deadline Start",
        "S_REQUESTED_DEADLINE_END_DATE": "Requested Deadline End",
        "S_REQUIRED_ARRIVAL_DATE_EXPECTED": "Required Arrival Date",
        "B_DATA_ESTIMATIVA_SAIDA_ETD": "ETD", "B_DATA_ESTIMATIVA_CHEGADA_ETA": "ETA",
        "B_DATA_ESTIMATIVA_ATRACACAO_ETB": "Estimativa Atracação (ETB)",
        "B_DATA_ATRACACAO_ATB": "Atracação (ATB)", "B_DATA_PARTIDA_ATD": "Partida (ATD)",
        "B_DATA_CHEGADA_ATA": "Chegada (ATA)",
    }

    rename_map = {col: custom_overrides.get(col, mapping_upper.get(col, prettify(col))) for col in df_to_process.columns}
    df_processed = df_to_process.copy()
    df_processed.rename(columns=rename_map, inplace=True)
    
    for col in df_processed.columns:
        if df_processed[col].dtype == 'datetime64[ns]':
            # Converter para string e tratar todos os casos possíveis
            df_processed[col] = df_processed[col].astype(str).replace('NaT', '').replace('None', '').replace('nan', '').replace('<NA>', '')
        else:
            # Tratar None, NaN, e outros valores nulos
            df_processed[col] = df_processed[col].fillna('').astype(str).replace('None', '').replace('nan', '').replace('<NA>', '')
    
    if "Linked Reference" in df_processed.columns:
        df_processed["Linked Reference"] = df_processed.apply(
            lambda row: format_linked_reference_display(row.get("Linked Reference"), row.get("Farol Reference")), axis=1
        )
    
    df_processed = process_farol_status_for_display(df_processed)
    return df_processed


def _detect_changes_for_new_adjustment(df_processed):
    """Detecta alterações em linhas com Status = 'New Adjustment' comparando com a linha anterior."""
    if df_processed is None or df_processed.empty:
        return {}
    
    editable_fields = [
        "Quantity of Containers", "Port of Loading POL", "Port of Delivery POD", "Place of Receipt",
        "Final Destination", "Transhipment Port", "Port Terminal", "Carrier", "Voyage Code",
        "Booking", "Vessel Name", "Requested Deadline Start", "Requested Deadline End",
        "Required Sail Date", "Required Arrival Date", "Draft Deadline", "Deadline", "Abertura Gate",
        "Confirmação Embarque", "ETD", "ETA", "Estimativa Atracação (ETB)", "Atracação (ATB)",
        "Partida (ATD)", "Estimada Transbordo (ETD)", "Chegada (ATA)", "Transbordo (ATD)",
    ]
    
    changes = {}
    for idx in range(len(df_processed)):
        current_row = df_processed.iloc[idx]
        if idx == 0:
            if len(df_processed) > 1:
                previous_row = df_processed.iloc[1]
            else:
                continue
        else:
            previous_row = df_processed.iloc[idx - 1]
        
        status = current_row.get("Farol Status", "")
        if pd.isna(status) or status is None:
            status = ""
        else:
            status = str(status)
        
        if status == "🛠️ New Adjustment":
            for field in editable_fields:
                if field in df_processed.columns:
                    current_val = current_row[field]
                    previous_val = previous_row[field]
                    
                    def normalize_value(val):
                        if pd.isna(val) or val is None or val == "":
                            return None
                        if hasattr(val, 'strftime'):
                            return val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(val, 'hour') else val.strftime('%Y-%m-%d')
                        return str(val)
                    
                    current_normalized = normalize_value(current_val)
                    previous_normalized = normalize_value(previous_val)
                    
                    if current_normalized != previous_normalized:
                        changes[(idx, field)] = {'current': current_val, 'previous': previous_val}
    
    return changes


def _detect_changes_for_carrier_return(df_processed):
    """Detecta alterações em linhas de retornos do carrier comparando com a linha anterior."""
    if df_processed is None or df_processed.empty:
        return {}
    
    editable_fields = [
        "Quantity of Containers", "Port of Loading POL", "Port of Delivery POD", "Place of Receipt",
        "Final Destination", "Transhipment Port", "Port Terminal", "Carrier", "Voyage Code",
        "Booking", "Vessel Name", "Requested Deadline Start", "Requested Deadline End",
        "Required Sail Date", "Required Arrival Date", "Draft Deadline", "Deadline", "Abertura Gate",
        "Confirmação Embarque", "ETD", "ETA", "Estimativa Atracação (ETB)", "Atracação (ATB)",
        "Partida (ATD)", "Estimada Transbordo (ETD)", "Chegada (ATA)", "Transbordo (ATD)",
    ]
    
    changes = {}
    for idx in range(len(df_processed)):
        current_row = df_processed.iloc[idx]
        if idx == 0:
            if len(df_processed) > 1:
                previous_row = df_processed.iloc[1]
            else:
                continue
        else:
            previous_row = df_processed.iloc[idx - 1]
        
        pdf_date = current_row.get("PDF Booking Emission Date", None)
        if pdf_date is None:
            pdf_date = current_row.get("Pdf Booking Emission Date", None)
        is_pdf_filled = pdf_date is not None and not pd.isna(pdf_date) and str(pdf_date).strip() != ""
        
        status = current_row.get("Farol Status", "")
        if pd.isna(status) or status is None:
            status = ""
        else:
            status = str(status)
        is_received_status = status == "📨 Received from Carrier"
        
        is_carrier_return = is_pdf_filled or is_received_status
        
        if is_carrier_return:
            for field in editable_fields:
                if field in df_processed.columns:
                    current_val = current_row[field]
                    previous_val = previous_row[field]
                    
                    def normalize_value(val):
                        if pd.isna(val) or val is None or val == "":
                            return None
                        if hasattr(val, 'strftime'):
                            return val.strftime('%Y-%m-%d %H:%M:%S') if hasattr(val, 'hour') else val.strftime('%Y-%m-%d')
                        return str(val)
                    
                    current_normalized = normalize_value(current_val)
                    previous_normalized = normalize_value(previous_val)
                    
                    if current_normalized != previous_normalized:
                        changes[(idx, field)] = {'current': current_val, 'previous': previous_val}
    
    return changes


def _apply_highlight_styling_combined(df_processed, combined_changes_dict):
    """Aplica estilização usando Pandas Styler com suporte para múltiplos tipos de destaque."""
    if df_processed is None or df_processed.empty:
        return df_processed
    
    df_styled = df_processed.copy()
    
    for col in df_styled.columns:
        if df_styled[col].dtype == 'datetime64[ns]':
            # Converter para string e tratar todos os casos possíveis
            df_styled[col] = df_styled[col].astype(str).replace('NaT', '').replace('None', '').replace('nan', '').replace('<NA>', '')
        else:
            # Tratar None, NaN, e outros valores nulos
            df_styled[col] = df_styled[col].fillna('').astype(str).replace('None', '').replace('nan', '').replace('<NA>', '')
    
    def highlight_changes_and_zebra(row):
        styles = [''] * len(row)
        row_idx = row.name
        
        if row_idx % 2 == 0:
            base_bg = 'background-color: #E8E8E8;'
        else:
            base_bg = 'background-color: #FFFFFF;'
        
        for i in range(len(styles)):
            col_name = df_styled.columns[i]
            # Aplicar apenas background-color na coluna Index (sem width/border que possam sobrescrever CSS)
            if col_name == "Index":
                styles[i] = base_bg
            else:
                styles[i] = base_bg
        
        for (change_row_idx, col_name), change_info in combined_changes_dict.items():
            if change_row_idx == row_idx and col_name in df_styled.columns:
                col_idx = df_styled.columns.get_loc(col_name)
                # Não aplicar destaque na coluna Index para evitar estilos inline que sobrescrevam CSS
                if col_name == "Index":
                    continue
                if change_info.get('highlight_blue', False):
                    styles[col_idx] = 'background-color: #FFE0B2; border: 2px solid #FF9800;'
                else:
                    styles[col_idx] = 'background-color: #C8E6C9; border: 2px solid #4CAF50;'
        
        return styles
    
    styled_df = df_styled.style.apply(highlight_changes_and_zebra, axis=1)
    return styled_df


def _display_tab_content(df_tab, tab_name, farol_reference):
    """Exibe o conteúdo de uma aba com a grade de dados"""
    if df_tab.empty:
        st.info(f"📋 Nenhum registro encontrado para {tab_name}")
        return None
        
    df_processed = _process_dataframe(df_tab, farol_reference)
    
    date_cols = [
        "Inserted Date", "Draft Deadline", "Deadline", 
        "Requested Deadline Start", "Requested Deadline End", "Required Arrival Date",
        "ETD", "ETA", "Abertura Gate",
        "Confirmação Embarque", "Partida (ATD)", "Estimada Transbordo (ETD)",
        "Chegada (ATA)", "Transbordo (ATD)", "Estimativa Atracação (ETB)", "Atracação (ATB)",
        "PDF Booking Emission Date"
    ]
    
    # Converter colunas de data para datetime para ordenação (manter como datetime temporariamente)
    for col in date_cols:
        if col in df_processed.columns:
            df_processed[col] = pd.to_datetime(df_processed[col], errors='coerce')

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
            df_processed = df_processed.drop(columns=["__ref_root", "__ref_suffix_num"])
        else:
            df_processed = df_processed.sort_values(by=["Inserted Date"], ascending=[True], kind="mergesort")

    desired_order = [
        "Index", "Farol Status", "Inserted Date", "Farol Reference", "Carrier", "Booking",
        "Vessel Name", "Voyage Carrier", "Voyage Code", "Quantity of Containers",
        "Place of Receipt", "Port of Loading POL", "Port of Delivery POD", "Final Destination",
        "Transhipment Port", "Port Terminal", "Required Arrival Date",
        "Requested Deadline Start", "Requested Deadline End", "Deadline", "Draft Deadline",
        "Abertura Gate", "Confirmação Embarque", "ETD", "ETA",
        "Estimativa Atracação (ETB)", "Atracação (ATB)", "Partida (ATD)",
        "Estimada Transbordo (ETD)", "Chegada (ATA)", "Transbordo (ATD)",
        "PDF Name", "PDF Booking Emission Date", "Linked Reference",
        # Colunas de justificativa no final
        "Area", "Request Reason", "Adjustments Owner", "Comments",
    ]
    
    def reorder_columns(df, ordered_list):
        existing_cols = [col for col in ordered_list if col in df.columns]
        hidden_cols = ["ADJUSTMENT_ID", "Status"]
        remaining_cols = [col for col in df.columns if col not in existing_cols and col not in hidden_cols]
        return df[existing_cols + remaining_cols]

    try:
        df_processed = reorder_columns(df_processed, desired_order)
    except Exception as e:
        pass
    
    # Converter datas para string após ordenação, substituindo NaT/None por string vazia
    for col in date_cols:
        if col in df_processed.columns:
            df_processed[col] = df_processed[col].where(pd.notna(df_processed[col]), '')
            df_processed[col] = df_processed[col].astype(str).replace('NaT', '').replace('None', '').replace('nan', '').replace('<NA>', '')
    
    df_processed.insert(0, "Index", range(len(df_processed)))
    return df_processed


def render_request_timeline(df_unified, farol_reference, df_received_for_approval):
    """
    Renderiza a aba Request Timeline com todas as funcionalidades preservadas.
    
    Args:
        df_unified: DataFrame unificado com todos os registros
        farol_reference: Referência Farol atual
        df_received_for_approval: DataFrame com registros aguardando aprovação
    """
    df_unified_processed = None
    if df_unified is not None and not df_unified.empty:
        df_unified_processed = _display_tab_content(df_unified, "Request Timeline", farol_reference)
    
    edited_df_unified = None
    # Sempre retornar df_unified_processed se foi processado, mesmo que vazio após processamento
    if df_unified_processed is not None:
        column_config = _generate_dynamic_column_config(df_unified_processed, hide_status=False)
        changes_new_adj = _detect_changes_for_new_adjustment(df_unified_processed)
        changes_carrier = _detect_changes_for_carrier_return(df_unified_processed)
        
        df_unified_processed_reversed = df_unified_processed.iloc[::-1].reset_index(drop=True)
        
        def adjust_indices(changes_dict, original_len):
            adjusted = {}
            for (idx, field), value in changes_dict.items():
                new_idx = original_len - 1 - idx
                adjusted[(new_idx, field)] = value
            return adjusted
        
        changes_new_adj_adjusted = adjust_indices(changes_new_adj, len(df_unified_processed))
        changes_carrier_adjusted = adjust_indices(changes_carrier, len(df_unified_processed))
        
        combined_changes = {}
        for key, value in changes_carrier_adjusted.items():
            combined_changes[key] = {'highlight_blue': True, 'value': value}
        for key, value in changes_new_adj_adjusted.items():
            combined_changes[key] = {'highlight_blue': False, 'value': value}
        
        styled_df = _apply_highlight_styling_combined(df_unified_processed_reversed, combined_changes)
        
        if hasattr(styled_df, 'data'):
            df_to_check = styled_df.data.copy()
        else:
            df_to_check = styled_df.copy()
        
        # Simplificar: todas as colunas (incluindo datas) são tratadas como texto
        # Isso evita problemas de conversão do Streamlit que exibem "None" em campos vazios
        for col in df_to_check.columns:
            if df_to_check[col].dtype == 'datetime64[ns]':
                # Converter para string e tratar NaT/None
                df_to_check[col] = df_to_check[col].astype(str).replace('NaT', '').replace('None', '').replace('nan', '').replace('<NA>', '')
            else:
                # Para colunas não-datetime, tratar None explícito
                df_to_check[col] = df_to_check[col].fillna('').astype(str).replace('None', '').replace('nan', '').replace('<NA>', '')
        
        if hasattr(styled_df, 'data'):
            styled_df.data = df_to_check
        else:
            styled_df = df_to_check
        
        column_config["Index"] = st.column_config.NumberColumn(
            "Index", 
            help="Índice da linha", 
            width="small",
            disabled=True,
            format="%d"
        )
        
        # Calcular posição da coluna Index no DataFrame final (considerando colunas visíveis)
        # Colunas ocultas (config=None) não são renderizadas, então não contam no nth-child
        visible_columns = [col for col in df_unified_processed_reversed.columns if col in column_config and column_config[col] is not None]
        if "Index" in visible_columns:
            index_position = visible_columns.index("Index") + 1  # nth-child é 1-based
        else:
            # Fallback: se Index não estiver na lista, assume posição 1
            index_position = 1
        
        # CSS para reduzir largura da coluna Index usando nth-child com índice calculado
        # Usa o mesmo padrão do shipments.py para garantir aplicação correta
        index_css = f"""
        <style>
        /* Reduzir largura da coluna Index (posição {index_position}) - seletores específicos para forçar aplicação */
        div[data-testid="stDataFrame"] table thead th:nth-child({index_position}) {{
            width: 35px !important;
            min-width: 35px !important;
            max-width: 35px !important;
            text-align: center !important;
            padding: 8px 4px !important;
        }}
        div[data-testid="stDataFrame"] table tbody td:nth-child({index_position}) {{
            width: 35px !important;
            min-width: 35px !important;
            max-width: 35px !important;
            text-align: center !important;
            padding: 8px 4px !important;
        }}
        /* Seletores adicionais com maior especificidade para garantir aplicação */
        div[data-testid="stDataFrame"] th:nth-of-type({index_position}),
        div[data-testid="stDataFrame"] td:nth-of-type({index_position}) {{
            width: 35px !important;
            min-width: 35px !important;
            max-width: 35px !important;
            text-align: center !important;
        }}
        /* Fallback para garantir aplicação mesmo com estilos inline do Pandas Styler */
        table[data-testid*="stDataFrame"] th:nth-child({index_position}),
        table[data-testid*="stDataFrame"] td:nth-child({index_position}) {{
            width: 35px !important;
            min-width: 35px !important;
            max-width: 35px !important;
        }}
        </style>
        """
        st.markdown(index_css, unsafe_allow_html=True)
        
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            key=f"history_unified_{farol_reference}"
        )
        
        # Reaplicar CSS após renderização do dataframe para garantir aplicação
        # Usa JavaScript para aplicar estilo após o DOM estar completo
        st.markdown(f"""
        <script>
        (function() {{
            function applyIndexWidth() {{
                const tables = document.querySelectorAll('[data-testid="stDataFrame"] table');
                tables.forEach(table => {{
                    const th = table.querySelector('thead th:nth-child({index_position})');
                    const tds = table.querySelectorAll('tbody td:nth-child({index_position})');
                    if (th) {{
                        th.style.width = '35px';
                        th.style.minWidth = '35px';
                        th.style.maxWidth = '35px';
                        th.style.textAlign = 'center';
                    }}
                    tds.forEach(td => {{
                        td.style.width = '35px';
                        td.style.minWidth = '35px';
                        td.style.maxWidth = '35px';
                        td.style.textAlign = 'center';
                    }});
                }});
            }}
            // Aplicar imediatamente
            applyIndexWidth();
            // Aplicar após pequeno delay para garantir renderização completa
            setTimeout(applyIndexWidth, 100);
            // Aplicar quando o DOM mudar (Streamlit pode re-renderizar)
            const observer = new MutationObserver(applyIndexWidth);
            observer.observe(document.body, {{ childList: true, subtree: true }});
        }})();
        </script>
        """, unsafe_allow_html=True)
        
        edited_df_unified = df_unified_processed
        
        if not df_received_for_approval.empty:
            st.info("ℹ️ **Request Timeline:** Visualize o histórico completo de alterações. Use o selectbox na seção abaixo para selecionar e avaliar retornos dos armadores.")
        else:
            st.info("ℹ️ **Request Timeline:** Visualize o histórico completo de alterações da referência.")
    else:
        # Se df_unified_processed é None, ainda pode haver df_received_for_approval
        # Retornar um DataFrame vazio ao invés de None para evitar problemas
        edited_df_unified = pd.DataFrame()
    
    return edited_df_unified


def render_voyages_timeline(df_voyage_monitoring):
    """
    Renderiza a aba Voyage Timeline com cards de viagens e histórico de alterações.
    
    Args:
        df_voyage_monitoring: DataFrame com dados de monitoramento de viagens
    """
    if df_voyage_monitoring.empty:
        st.info("📋 Nenhum dado de monitoramento encontrado para esta referência.")
        return
    
    df_monitoring_display = df_voyage_monitoring.copy()
    
    if not df_monitoring_display.empty:
        df_monitoring_display['aprovacao_date'] = pd.to_datetime(df_monitoring_display.get('aprovacao_date'), errors='coerce')
        df_monitoring_display['navio_viagem'] = df_monitoring_display['navio'].astype(str) + " - " + df_monitoring_display['viagem'].astype(str)
        latest_approvals = df_monitoring_display.groupby('navio_viagem')['aprovacao_date'].max()
        unique_voyages_sorted = latest_approvals.sort_values(ascending=False).index.tolist()
        
        def format_date_safe(date_val):
            if date_val is None:
                return 'N/A'
            try:
                if pd.isna(date_val):
                    return 'N/A'
                brazil_time = convert_utc_to_brazil_time(date_val)
                if hasattr(brazil_time, 'strftime'):
                    return brazil_time.strftime('%d/%m/%Y %H:%M')
                return str(brazil_time)
            except Exception:
                return 'N/A'
        
        def format_date_safe_brazil(date_val):
            if date_val is None:
                return 'N/A'
            try:
                if pd.isna(date_val):
                    return 'N/A'
                if hasattr(date_val, 'strftime'):
                    return date_val.strftime('%d/%m/%Y %H:%M')
                return str(date_val)
            except Exception:
                return 'N/A'
        
        def format_source_display(source):
            if source == 'API':
                return 'API'
            elif source == 'MANUAL':
                return 'Manual'
            else:
                return f'{source}'
        
        for i, voyage_key in enumerate(unique_voyages_sorted):
            voyage_records = df_monitoring_display[df_monitoring_display['navio_viagem'] == voyage_key]
            latest_record = voyage_records.iloc[0]
            
            with st.container():
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
                
                voyage_count = len(voyage_records)
                if voyage_count >= 1:
                    with st.expander(f"📈 Ver histórico ({voyage_count} registros)", expanded=False):
                        st.markdown("#### 🔄 Alterações Detectadas")
                        
                        def detect_changes(records):
                            changes = []
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
                            
                            for j in range(len(records) - 1):
                                current = records.iloc[j]
                                previous = records.iloc[j + 1]
                                
                                for field, label in monitored_fields.items():
                                    current_val = current.get(field)
                                    previous_val = previous.get(field)
                                    
                                    def format_date(val):
                                        if val is None or pd.isna(val):
                                            return "Sem Registro"
                                        brazil_time = convert_utc_to_brazil_time(val)
                                        if hasattr(brazil_time, 'strftime'):
                                            return brazil_time.strftime('%d/%m/%Y - %H:%M')
                                        return str(brazil_time)
                                    
                                    current_formatted = format_date(current_val)
                                    previous_formatted = format_date(previous_val)
                                    
                                    if current_formatted != previous_formatted:
                                        from datetime import datetime
                                        import pytz
                                        
                                        def get_brazil_time():
                                            brazil_tz = pytz.timezone('America/Sao_Paulo')
                                            return datetime.now(brazil_tz)
                                        
                                        update_time = get_brazil_time()
                                        
                                        def format_update_time(date_val):
                                            if date_val is None:
                                                return 'N/A'
                                            try:
                                                if pd.isna(date_val):
                                                    return 'N/A'
                                                brazil_time = convert_utc_to_brazil_time(date_val)
                                                if hasattr(brazil_time, 'strftime'):
                                                    return brazil_time.strftime('%d/%m/%Y às %H:%M')
                                                return str(brazil_time)
                                            except Exception:
                                                return 'N/A'
                                        
                                        update_str = format_update_time(update_time)
                                        current_source = current.get('data_source', current.get('DATA_SOURCE', 'N/A'))
                                        
                                        changes.append({
                                            'field': label,
                                            'from': previous_formatted,
                                            'to': current_formatted,
                                            'source': format_source_display(current_source),
                                            'updated_at': update_str
                                        })
                            
                            return changes
                        
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
                        voyage_display = voyage_records.drop(columns=['navio_viagem'])
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
                        
                        if 'Source' in voyage_display.columns:
                            voyage_display['Source'] = voyage_display['Source'].apply(format_source_display)
                        
                        id_cols_to_drop = [col for col in voyage_display.columns if col.strip().lower() == 'id']
                        if id_cols_to_drop:
                            voyage_display = voyage_display.drop(columns=id_cols_to_drop)

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
                
                if i < len(unique_voyages_sorted) - 1:
                    st.markdown("---")


def render_pdf_processing_panel(*args, **kwargs):  # placeholder para manter API mental
    pass


def render_approval_panel(df_received_for_approval, df_for_approval, farol_reference, active_tab, unified_label):
    """
    Renderiza o painel de aprovação para PDFs "Received from Carrier" abaixo da tabela unificada.
    
    Args:
        df_received_for_approval: DataFrame com registros "Received from Carrier" da referência atual
        df_for_approval: DataFrame unificado processado (para buscar Index correto)
        farol_reference: Referência Farol atual
        active_tab: Aba ativa no momento
        unified_label: Label da aba unificada
    """
    # Carrega dados da UDC para justificativas (carregar apenas uma vez, cache pode ser adicionado depois)
    df_udc = load_df_udc()
    Booking_adj_reason_car = df_udc[df_udc["grupo"] == "Booking Adj Request Reason Car"]["dado"].dropna().unique().tolist()
    Booking_adj_responsibility_car = df_udc[df_udc["grupo"] == "Booking Adj Responsibility Car"]["dado"].dropna().unique().tolist()
    
    if active_tab == unified_label and not df_received_for_approval.empty and df_for_approval is not None:
        st.markdown("---")
        st.markdown("### ⚡ Evaluate Carrier Return")
        
        # Create options for the selectbox
        approval_options = ["Select a PDF to approve..."]
        approval_mapping = {}  # Dict to map option -> row data
        
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
            
            # Get the line Index from df_for_approval based on idx
            if df_for_approval is not None and idx in df_for_approval.index:
                line_index = df_for_approval.loc[idx, 'Index']
            else:
                line_index = idx
            
            # Format: Index | Date and time
            option_text = f"Index {line_index} | {date_str}"
            approval_options.append(option_text)
            approval_mapping[option_text] = row
        
        selected_pdf = st.selectbox(
            "Select the carrier return to evaluate:",
            options=approval_options,
            key=f"pdf_approval_select_{farol_reference}"
        )

        # If the selected PDF changes, reset the approval step
        last_pdf_key = f"last_selected_pdf_{farol_reference}"
        if last_pdf_key not in st.session_state:
            st.session_state[last_pdf_key] = selected_pdf

        if st.session_state[last_pdf_key] != selected_pdf:
            if f"approval_step_{farol_reference}" in st.session_state:
                del st.session_state[f"approval_step_{farol_reference}"]
            st.session_state[last_pdf_key] = selected_pdf
        
        # If a PDF is selected, show approval buttons
        if selected_pdf != "Select a PDF to approve...":
            with st.container(border=True):
                selected_row = approval_mapping[selected_pdf]
                adjustment_id = selected_row['ADJUSTMENT_ID']
                
                # Get current status
                selected_row_status = get_return_carrier_status_by_adjustment_id(adjustment_id) or selected_row.get("B_BOOKING_STATUS", "")
                
                st.markdown("<h4 style='text-align: left;'>🔄 Select Action:</h4>", unsafe_allow_html=True)
                
                # Button layout
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
                            confirm_status_key = f"confirm_status_change_{farol_reference}"
                            if confirm_status_key in st.session_state:
                                del st.session_state[confirm_status_key]
                            st.session_state[f"approval_step_{farol_reference}"] = "select_adjustment_type"
                            st.session_state[f"selected_row_for_approval_{farol_reference}"] = selected_row
                            st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                            st.rerun()
                    
                    with subcol2:
                        if st.button("Booking Rejected", key=f"status_rejected_unified_{farol_reference}", type="secondary", disabled=disable_rejected):
                            if f"approval_step_{farol_reference}" in st.session_state:
                                del st.session_state[f"approval_step_{farol_reference}"]
                            st.session_state[f"confirm_status_change_{farol_reference}"] = "Booking Rejected"
                            st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                            st.rerun()
                    
                    with subcol3:
                        if st.button("Booking Cancelled", key=f"status_cancelled_unified_{farol_reference}", type="secondary", disabled=disable_cancelled):
                            if f"approval_step_{farol_reference}" in st.session_state:
                                del st.session_state[f"approval_step_{farol_reference}"]
                            st.session_state[f"confirm_status_change_{farol_reference}"] = "Booking Cancelled"
                            st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                            st.rerun()
                    
                    with subcol4:
                        if st.button("Adjustment Requested", key=f"status_adjustment_unified_{farol_reference}", type="secondary", disabled=disable_adjustment):
                            if f"approval_step_{farol_reference}" in st.session_state:
                                del st.session_state[f"approval_step_{farol_reference}"]
                            st.session_state[f"confirm_status_change_{farol_reference}"] = "Adjustment Requested"
                            st.session_state[f"adjustment_id_for_approval_{farol_reference}"] = adjustment_id
                            st.rerun()

            confirm_status_key = f"confirm_status_change_{farol_reference}"
            if confirm_status_key in st.session_state:
                new_status = st.session_state[confirm_status_key]
                st.warning(f"Are you sure you want to change the status to '{new_status}'?")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Confirm", key=f"confirm_status_change_yes_{farol_reference}"):
                        adjustment_id = st.session_state[f"adjustment_id_for_approval_{farol_reference}"]
                        result = update_record_status(adjustment_id, new_status)
                        if result:
                            st.session_state["history_flash"] = {"type": "success", "msg": f"✅ Status updated to '{new_status}'."}
                            del st.session_state[confirm_status_key]
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("❌ Failed to update status.")
                with col2:
                    if st.button("Cancel", key=f"confirm_status_change_no_{farol_reference}"):
                        del st.session_state[confirm_status_key]
                        st.rerun()

            # Verificação do approval_step para exibir seções de aprovação
            if st.session_state.get(f"approval_step_{farol_reference}") == "select_adjustment_type":
                st.markdown("<h4 style='text-align: left;'>Adjustment Type</h4>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: left;'>This carrier return, documented in the PDF, refers to:</p>", unsafe_allow_html=True)
                
                adjustment_type = st.radio(
                    "Select one of the options below:",
                    ("An adjustment request made by our company.", "A new/external adjustment initiated by the carrier itself."),
                    key=f"adjustment_type_{farol_reference}",
                    label_visibility="collapsed"
                )

                if st.button("Continue", key=f"continue_adjustment_type_{farol_reference}"):
                    if adjustment_type == "An adjustment request made by our company.":
                        st.session_state[f"approval_step_{farol_reference}"] = "select_internal_reference"
                    else: # "A new/external adjustment initiated by the carrier itself."
                        st.session_state[f"approval_step_{farol_reference}"] = "external_adjustment_form"
                    st.rerun()

            elif st.session_state.get(f"approval_step_{farol_reference}") == "select_internal_reference":
                st.markdown("<h4 style='text-align: left;'>Related Reference</h4>", unsafe_allow_html=True)
                
                # Get available references for relation
                available_refs = history_get_available_references_for_relation(farol_reference)
                
                ref_options = ["Select a reference..."]
                
                # Adicionar opção especial "New Adjustment" sempre disponível
                ref_options.append("🆕 New Adjustment")
                
                # Adicionar registros disponíveis (Booking Requested ou New Adjustment sem LINKED_REFERENCE)
                if available_refs:
                    for ref in available_refs:
                        b_status = str(ref.get('FAROL_STATUS', '') or '').strip()
                        linked = ref.get('LINKED_REFERENCE')
                        
                        # Check if the reference is valid for selection
                        # Aceita Booking Requested ou New Adjustment sem Linked Reference
                        is_booking_requested = (b_status == 'Booking Requested')
                        is_new_adjustment = (b_status == 'New Adjustment')
                        has_no_linked = (linked is None or str(linked).strip() == '')
                        
                        if (is_booking_requested and has_no_linked) or \
                           (is_new_adjustment and has_no_linked):
                            
                            inserted_date = ref.get('ROW_INSERTED_DATE')
                            brazil_time = convert_utc_to_brazil_time(inserted_date) if inserted_date else None
                            date_str = brazil_time.strftime('%d/%m/%Y %H:%M') if brazil_time else 'N/A'
                            
                            status_display = ref.get('FAROL_STATUS', 'Status')
                            option_text = f"{ref['FAROL_REFERENCE']} | {status_display} | {date_str}"
                            ref_options.append(option_text)

                selected_ref = st.selectbox("Select the internal reference:", options=ref_options, key=f"internal_ref_select_{farol_reference}")

                # Formulário condicional para "New Adjustment"
                justification = {}
                if selected_ref == "🆕 New Adjustment":
                    st.markdown("#### New Adjustment Justification")
                    reason = st.selectbox(
                        "Booking Adjustment Request Reason *", 
                        options=[""] + Booking_adj_reason_car,
                        key=f"new_adj_reason_{farol_reference}"
                    )
                    
                    # Para ajuste interno via New Adjustment, sempre usar "Armador"
                    responsibility_options = [""] + Booking_adj_responsibility_car
                    default_responsibility = "Armador"
                    default_index = 0
                    if "Armador" in responsibility_options:
                        default_index = responsibility_options.index("Armador")
                    else:
                        # Buscar case-insensitive
                        for i, opt in enumerate(responsibility_options):
                            if str(opt).strip().upper() == "ARMADOR":
                                default_index = i
                                default_responsibility = opt
                                break
                    
                    responsibility = st.selectbox(
                        "Booking Adjustment Responsibility",
                        options=responsibility_options,
                        index=default_index,
                        disabled=True,
                        help="Responsabilidade fixa em 'Armador' para ajustes do armador",
                        key=f"new_adj_responsibility_{farol_reference}"
                    )
                    
                    # Garantir que sempre use "Armador"
                    if responsibility == "":
                        responsibility = default_responsibility
                    
                    comment = st.text_area(
                        "Comments",
                        key=f"new_adj_comments_{farol_reference}"
                    )
                    
                    # Preparar justification dict
                    justification = {
                        "area": "Booking",  # Valor padrão necessário pela função
                        "request_reason": reason if reason else "",
                        "adjustments_owner": responsibility,
                        "comments": comment if comment else ""
                    }

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Confirm Approval", key=f"confirm_internal_approval_{farol_reference}"):
                        if selected_ref != "Select a reference...":
                            # Tratar opção especial "New Adjustment"
                            if selected_ref == "🆕 New Adjustment":
                                # Validar campos obrigatórios
                                if not justification.get("request_reason"):
                                    st.error("The 'Booking Adjustment Request Reason' field is mandatory for New Adjustment.")
                                else:
                                    related_reference = "New Adjustment"
                                    # Call approval function com justification
                                    result = approve_carrier_return(adjustment_id, related_reference, justification)
                                    if result:
                                        st.session_state["history_flash"] = {"type": "success", "msg": "✅ Approval completed successfully!"}
                                        st.session_state.pop(f"approval_step_{farol_reference}", None)
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to approve.")
                            else:
                                # Montar formato: "Index X | 29-10-2025"
                                # 1. Extrair Index do carrier return selecionado
                                selected_pdf = st.session_state.get(f"pdf_approval_select_{farol_reference}", "")
                                index_part = ""
                                if selected_pdf and "|" in selected_pdf:
                                    # selected_pdf formato: "Index 3 | 29/10/2025 14:59"
                                    pdf_parts = selected_pdf.split("|")
                                    if len(pdf_parts) > 0:
                                        index_part = pdf_parts[0].strip()  # "Index 3"
                                
                                # 2. Extrair data da referência interna (pode estar na posição 2 ou 3 dependendo do formato)
                                date_part = ""
                                if "|" in selected_ref:
                                    ref_parts = [p.strip() for p in selected_ref.split("|")]
                                    # A data pode estar na última posição ou na terceira
                                    if len(ref_parts) >= 3:
                                        # Extrair data e formatar com hífen (remover hora se houver)
                                        date_str = ref_parts[2]  # "29/10/2025 15:43" ou "29/10/2025"
                                        date_part = date_str.split()[0].replace("/", "-")  # "29-10-2025"
                                    elif len(ref_parts) >= 2:
                                        # Se não houver terceira parte, tenta a segunda
                                        date_str = ref_parts[1]
                                        # Verifica se é uma data (contém / ou -)
                                        if "/" in date_str or "-" in date_str:
                                            date_part = date_str.split()[0].replace("/", "-")
                                
                                # 3. Montar related_reference no formato desejado (sem status)
                                if index_part and date_part:
                                    related_reference = f"{index_part} | {date_part}"
                                else:
                                    # Fallback: usar selected_ref completo se não conseguir montar
                                    related_reference = selected_ref
                                
                                # Call approval function sem justification (apenas para referências vinculadas)
                                result = approve_carrier_return(adjustment_id, related_reference, {})
                                if result:
                                    st.session_state["history_flash"] = {"type": "success", "msg": "✅ Approval completed successfully!"}
                                    st.session_state.pop(f"approval_step_{farol_reference}", None)
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to approve.")
                        else:
                            st.warning("Please select a reference.")
                with col2:
                    if st.button("Back", key=f"back_to_adjustment_type_{farol_reference}"):
                        st.session_state[f"approval_step_{farol_reference}"] = "select_adjustment_type"
                        st.rerun()

            elif st.session_state.get(f"approval_step_{farol_reference}") == "external_adjustment_form":
                st.markdown("<h4 style='text-align: left;'>New External Adjustment</h4>", unsafe_allow_html=True)
                with st.form(key=f"external_adjustment_form_{farol_reference}"):
                    st.info("This is a carrier adjustment without a prior request from the company.")
                    reason = st.selectbox("Booking Adjustment Request Reason", options=[""] + Booking_adj_reason_car)
                    
                    # Para ajuste externo, sempre usar "Armador" e desabilitar
                    responsibility_options = [""] + Booking_adj_responsibility_car
                    # Tentar encontrar "Armador" na lista (case-insensitive)
                    default_responsibility = "Armador"
                    default_index = 0  # Se não encontrar, usa o primeiro (vazio)
                    if "Armador" in responsibility_options:
                        default_index = responsibility_options.index("Armador")
                    else:
                        # Buscar case-insensitive
                        for i, opt in enumerate(responsibility_options):
                            if str(opt).strip().upper() == "ARMADOR":
                                default_index = i
                                default_responsibility = opt
                                break
                    
                    responsibility = st.selectbox(
                        "Booking Adjustment Responsibility",
                        options=responsibility_options,
                        index=default_index,
                        disabled=True,
                        help="Responsabilidade fixa em 'Armador' para ajustes externos do armador"
                    )
                    
                    # Garantir que sempre use "Armador" (ou o valor encontrado)
                    if responsibility == "":
                        responsibility = default_responsibility
                    
                    comment = st.text_area("Comments")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("Confirm Approval")
                    with col2:
                        back_clicked = st.form_submit_button("Back")

                    if back_clicked:
                        st.session_state[f"approval_step_{farol_reference}"] = "select_adjustment_type"
                        st.rerun()

                    if submitted:
                        if not reason:
                            st.error("The 'Booking Adjustment Request Reason' field is mandatory.")
                        else:
                            justification = {
                                "area": "Booking",
                                "request_reason": reason,
                                "adjustments_owner": responsibility,
                                "comments": comment
                            }
                            result = approve_carrier_return(adjustment_id, "New Adjustment", justification)
                            if result:
                                st.session_state["history_flash"] = {"type": "success", "msg": "✅ External adjustment approval completed successfully!"}
                                st.session_state.pop(f"approval_step_{farol_reference}", None)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to approve the external adjustment.")


