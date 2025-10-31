import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

from history_data import get_referenced_line_data
from shipments_mapping import get_column_mapping, process_farol_status_for_display

def load_custom_css():
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
    """, unsafe_allow_html=True)

def format_linked_reference_display(linked_ref, farol_ref=None):
    if not linked_ref or str(linked_ref).strip() == "" or str(linked_ref).upper() == "NULL": return ""
    linked_ref_str = str(linked_ref)
    if linked_ref_str == "New Adjustment": return "🆕 New Adjustment"
    if linked_ref_str.isdigit():
        line_data = get_referenced_line_data(linked_ref_str)
        if line_data:
            inserted_date = line_data.get('inserted_date')
            date_str = pd.to_datetime(inserted_date).strftime('%Y-%m-%d %H:%M:%S') if inserted_date else "N/A"
            return f"Line {line_data['id']} | {date_str}"
        return f"📋 Global Request #{linked_ref_str}"
    if "-R" in linked_ref_str:
        parts = linked_ref_str.split("-R")
        if len(parts) == 2: return f"📋 Request #{parts[1]} ({parts[0]})"
    return str(linked_ref)

def get_file_type(uploaded_file):
    ext = uploaded_file.name.split('.')[-1].lower()
    mapping = {'pdf': 'PDF', 'doc': 'Word', 'docx': 'Word', 'xls': 'Excel', 'xlsx': 'Excel', 'ppt': 'PowerPoint', 'pptx': 'PowerPoint', 'txt': 'Texto', 'csv': 'CSV', 'png': 'Imagem', 'jpg': 'Imagem', 'jpeg': 'Imagem', 'gif': 'Imagem', 'zip': 'Compactado', 'rar': 'Compactado'}
    return mapping.get(ext, 'Outro')

def format_file_size(size_bytes):
    if size_bytes == 0: return "0 B"
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    return f"{round(size_bytes / p, 2)} {["B", "KB", "MB", "GB"][i]}"

def get_file_icon(mime_type, file_name):
    if not mime_type: return "📄"
    if mime_type.startswith('image/'): return "🖼️"
    if mime_type in ['application/pdf']: return "📕"
    return "📎"

def convert_utc_to_brazil_time(utc_timestamp):
    if utc_timestamp is None: return None
    try:
        brazil_tz = pytz.timezone('America/Sao_Paulo')
        if hasattr(utc_timestamp, 'tzinfo') and utc_timestamp.tzinfo is not None:
            return utc_timestamp.astimezone(brazil_tz) if str(utc_timestamp.tzinfo) in ['UTC', 'tzutc()'] else utc_timestamp
        else:
            return brazil_tz.localize(utc_timestamp)
    except: return utc_timestamp

def process_dataframe(df_to_process, farol_reference):
    if df_to_process.empty: return df_to_process
    df_processed = df_to_process.copy()

    # Renomear colunas
    mapping_main = get_column_mapping()
    mapping_upper = {k.upper(): v for k, v in mapping_main.items()}
    def prettify(col: str) -> str:
        label = col.replace("_", " ").title()
        replaces = {"Pol": "POL", "Pod": "POD", "Etd": "ETD", "Eta": "ETA", "Pdf": "PDF", "Id": "ID"}
        for k, v in replaces.items(): label = label.replace(k, v)
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
        "B_DATA_ABERTURA_GATE": "Abertura Gate", "B_DATA_CONFIRMACAO_EMBARQUE": "Confirmação Embarque",
        "B_DATA_ESTIMADA_TRANSBORDO_ETD": "Estimada Transbordo (ETD)", "B_DATA_TRANSBORDO_ATD": "Transbordo (ATD)",
        "B_DATA_DRAFT_DEADLINE": "Draft Deadline", "B_DATA_DEADLINE": "Deadline",
        "S_REQUESTED_DEADLINE_START_DATE": "Requested Deadline Start", "S_REQUESTED_DEADLINE_END_DATE": "Requested Deadline End",
        "S_REQUIRED_ARRIVAL_DATE_EXPECTED": "Required Arrival Date", "B_DATA_ESTIMATIVA_SAIDA_ETD": "ETD",
        "B_DATA_ESTIMATIVA_CHEGADA_ETA": "ETA", "B_DATA_ESTIMATIVA_ATRACACAO_ETB": "Estimativa Atracação (ETB)",
        "B_DATA_ATRACACAO_ATB": "Atracação (ATB)", "B_DATA_PARTIDA_ATD": "Partida (ATD)", "B_DATA_CHEGADA_ATA": "Chegada (ATA)",
    }
    rename_map = {col: custom_overrides.get(col, mapping_upper.get(col, prettify(col))) for col in df_processed.columns}
    df_processed.rename(columns=rename_map, inplace=True)

    # Tratamento de nulos e formatação
    for col in df_processed.columns:
        if pd.api.types.is_datetime64_any_dtype(df_processed[col]):
            # Converter para string e tratar todos os casos possíveis
            df_processed[col] = df_processed[col].astype(str).replace('NaT', '').replace('None', '').replace('nan', '').replace('<NA>', '')
        else:
            # Tratar None, NaN, e outros valores nulos
            df_processed[col] = df_processed[col].fillna('').astype(str).replace('None', '').replace('nan', '').replace('<NA>', '')

    if "Linked Reference" in df_processed.columns:
        df_processed["Linked Reference"] = df_processed.apply(lambda row: format_linked_reference_display(row.get("Linked Reference"), row.get("Farol Reference")), axis=1)

    df_processed = process_farol_status_for_display(df_processed)
    
    # Lógica de status que estava em display_tab_content
    try:
        if "Farol Reference" in df_processed.columns and "Farol Status" in df_processed.columns and "Inserted Date" in df_processed.columns and farol_reference:
            sel_ref = str(farol_reference)
            mask_sel = (df_processed["Farol Reference"].astype(str) == sel_ref) & (df_processed["Farol Status"].str.contains("Booking Requested", case=False, na=False))
            if mask_sel.any():
                first_idx_sel = df_processed.loc[mask_sel].sort_values("Inserted Date").index[0]

        required_cols = {"Farol Status", "Inserted Date", "Farol Reference"}
        if required_cols.issubset(set(df_processed.columns)):
            df_req = df_processed[df_processed["Farol Status"].str.contains("Booking Requested", na=False)].copy()
            if not df_req.empty:
                idx_first = df_req.sort_values("Inserted Date").groupby("Farol Reference", as_index=False).head(1).index
                if "Linked Reference" in df_processed.columns:
                    for i in idx_first:
                        if pd.isna(df_processed.loc[i, "Linked Reference"]) or df_processed.loc[i, "Linked Reference"] == "":
                            pass # Lógica de status removida
    except Exception: pass

    return df_processed

def get_editable_fields():
    return [
        "Quantity of Containers", "Port of Loading POL", "Port of Delivery POD", "Place of Receipt",
        "Final Destination", "Transhipment Port", "Port Terminal", "Carrier", "Voyage Code",
        "Booking", "Vessel Name", "Requested Deadline Start", "Requested Deadline End",
        "Required Sail Date", "Required Arrival Date", "Draft Deadline", "Deadline", "Abertura Gate",
        "Confirmação Embarque", "ETD", "ETA", "Estimativa Atracação (ETB)", "Atracação (ATB)",
        "Partida (ATD)", "Estimada Transbordo (ETD)", "Chegada (ATA)", "Transbordo (ATD)",
    ]

def detect_changes(df_processed, status_to_check, editable_fields):
    if df_processed is None or df_processed.empty: return {}
    changes = {}
    for idx, current_row in df_processed.iterrows():
        status = str(current_row.get("Farol Status", ""))
        is_status_match = status_to_check in status
        
        is_carrier_return = False
        if status_to_check == "📨 Received from Carrier":
            pdf_date = current_row.get("PDF Booking Emission Date", pd.NaT)
            is_pdf_filled = pd.notna(pdf_date) and str(pdf_date).strip() != ""
            is_carrier_return = is_pdf_filled or "Received from Carrier" in status

        if is_status_match or is_carrier_return:
            previous_row = df_processed.iloc[idx - 1] if idx > 0 else None
            if previous_row is None: continue

            for field in editable_fields:
                if field in df_processed.columns:
                    current_val = current_row.get(field)
                    previous_val = previous_row.get(field)
                    
                    def normalize(val):
                        if pd.isna(val) or val is None or val == '': return None
                        if isinstance(val, (datetime, pd.Timestamp)): return val.strftime('%Y-%m-%d %H:%M:%S')
                        return str(val)

                    if normalize(current_val) != normalize(previous_val):
                        changes[(idx, field)] = {'current': current_val, 'previous': previous_val}
    return changes

def apply_highlight_styling(styler, changes_dict):
    def highlight_cells(row):
        styles = [''] * len(row)
        row_idx = row.name
        # Zebra striping
        base_bg = 'background-color: #f5f5f5;' if row_idx % 2 == 0 else 'background-color: white;'
        styles = [base_bg] * len(row)

        for (change_row_idx, col_name), info in changes_dict.items():
            if change_row_idx == row_idx and col_name in styler.columns:
                col_idx = styler.columns.get_loc(col_name)
                color = '#FFF9C4' # Amarelo para New Adjustment
                if info.get('type') == 'carrier': color = '#E1F5FE' # Azul para Carrier Return
                styles[col_idx] += f' background-color: {color}; border: 1px solid #FFD54F;'
        return styles
    return styler.apply(highlight_cells, axis=1)

def prepare_main_data_for_display(main_data, df_fallback):
    """
    Prepara dados principais para exibição nos cards de métricas.
    
    Args:
        main_data: Dicionário com dados da tabela principal (F_CON_SALES_BOOKING_DATA)
        df_fallback: DataFrame como fallback se main_data não tiver dados
    
    Returns:
        tuple: (voyage_carrier, qty, ins)
    """
    from datetime import datetime
    
    if main_data:
        voyage_carrier = str(main_data.get("b_voyage_carrier", "-"))
        
        qty = main_data.get("s_quantity_of_containers", 0)
        try:
            qty = int(qty) if qty is not None and not pd.isna(qty) else 0
        except (ValueError, TypeError):
            qty = 0
        
        ins = main_data.get("row_inserted_date", "-")
        try:
            if isinstance(ins, datetime):
                ins = ins.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(ins, (int, float)):
                ins = datetime.fromtimestamp(ins/1000.0).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    else:
        # Fallback para valores do último registro se a tabela principal não tiver dados
        voyage_carrier = str(df_fallback.iloc[0].get("B_VOYAGE_CARRIER", "-")) if not df_fallback.empty else "-"
        qty = 0
        ins = "-"
    
    return voyage_carrier, qty, ins

def clear_history_session_state_on_selection_change(farol_reference, current_adjustment_id, last_adjustment_id):
    """
    Limpa estados do session_state quando a seleção de PDF muda.
    
    Args:
        farol_reference: Referência Farol atual
        current_adjustment_id: ID do ajuste atualmente selecionado
        last_adjustment_id: ID do último ajuste selecionado
    """
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

def clear_history_session_state_when_no_selection(farol_reference):
    """
    Limpa estados do session_state quando nenhum PDF está selecionado.
    
    Args:
        farol_reference: Referência Farol atual
    """
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

def get_display_columns():
    """
    Retorna a lista de colunas que devem ser exibidas na grade principal.
    
    Returns:
        list: Lista de nomes de colunas
    """
    return [
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
        "LINKED_REFERENCE",
        "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "B_DATA_ATRACACAO_ATB",
        "B_DATA_PARTIDA_ATD",
        "B_DATA_CHEGADA_ATA",
        "ADJUSTMENTS_OWNER",
    ]

def prepare_dataframe_for_display(df, farol_reference):
    """
    Prepara o DataFrame para exibição: seleciona colunas, ordena e aplica filtros.
    
    Args:
        df: DataFrame original
        farol_reference: Referência Farol atual
    
    Returns:
        tuple: (df_display, df_unified, df_received_for_approval)
            - df_display: DataFrame preparado e ordenado
            - df_unified: DataFrame unificado (todas as linhas)
            - df_received_for_approval: DataFrame filtrado para PDFs "Received from Carrier" da referência atual
    """
    display_cols = get_display_columns()
    internal_cols = display_cols + ["ADJUSTMENT_ID"]
    
    # Seleciona apenas colunas relevantes
    df_show = df[[c for c in internal_cols if c in df.columns]].copy()
    
    # Força a ordem correta das colunas
    ordered_cols = [c for c in internal_cols if c in df_show.columns]
    df_show = df_show[ordered_cols]
    
    # Aplica ordenação por Inserted Date
    if "ROW_INSERTED_DATE" in df_show.columns:
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
            df_show = df_show.drop(columns=["__ref_root", "__ref_suffix_num"])
        else:
            df_show = df_show.sort_values(by=["ROW_INSERTED_DATE"], ascending=[True], kind="mergesort")
    
    df_display = df_show.copy()
    df_unified = df_display.copy()
    
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
    
    return df_display, df_unified, df_received_for_approval

def generate_tab_labels(df_unified, df_received_for_approval, df_voyage_monitoring, farol_reference):
    """
    Gera os rótulos das abas com contagens apropriadas.
    
    Args:
        df_unified: DataFrame unificado
        df_received_for_approval: DataFrame com PDFs para aprovação
        df_voyage_monitoring: DataFrame de monitoramento de viagens
        farol_reference: Referência Farol atual
    
    Returns:
        tuple: (unified_label, voyages_label, audit_label)
    """
    # Labels das abas Request Timeline e Returns Awaiting Review
    unified_label = f"📋 Request Timeline ({len(df_unified)} records)"
    received_label = f"📨 Returns Awaiting Review ({len(df_received_for_approval)} records)"
    
    # Contagem de combinações distintas (Navio + Viagem + Terminal)
    try:
        if df_voyage_monitoring is not None and not df_voyage_monitoring.empty:
            df_tmp_count = df_voyage_monitoring.copy()
            df_tmp_count['navio'] = df_tmp_count['navio'].astype(str)
            df_tmp_count['viagem'] = df_tmp_count['viagem'].astype(str)
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
        from database import get_database_connection
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
    
    audit_label = f"🔍 Audit Trail ({audit_count} records)"
    
    return unified_label, voyages_label, audit_label

def initialize_tab_state(farol_reference, unified_label):
    """
    Inicializa o estado das abas no session_state.
    
    Args:
        farol_reference: Referência Farol atual
        unified_label: Label da aba unificada
    """
    active_tab_key = f"history_active_tab_{farol_reference}"
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    if active_tab_key not in st.session_state:
        st.session_state[active_tab_key] = unified_label
        st.session_state[last_active_tab_key] = unified_label

def handle_tab_change(farol_reference, active_tab, unified_label, voyages_label, audit_label):
    """
    Gerencia a troca de abas, limpando seleções quando necessário.
    
    Args:
        farol_reference: Referência Farol atual
        active_tab: Aba atualmente ativa
        unified_label: Label da aba unificada
        voyages_label: Label da aba de viagens
        audit_label: Label da aba de audit trail
    """
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    prev_tab = st.session_state.get(last_active_tab_key)
    
    if prev_tab != active_tab:
        # Limpa seleções ao trocar de aba
        pdf_select_key = f"pdf_approval_select_{farol_reference}"
        if active_tab in [unified_label, audit_label, voyages_label]:
            if pdf_select_key in st.session_state:
                del st.session_state[pdf_select_key]
        # Recolhe a seção de anexos ao trocar de aba
        st.session_state["history_show_attachments"] = False
        st.session_state[last_active_tab_key] = active_tab

def display_flash_messages():
    """
    Exibe mensagens persistentes (flash) da última ação realizada.
    Remove a mensagem do session_state após exibi-la.
    """
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

def initialize_history_state(farol_reference):
    """
    Inicializa estados do session_state para a tela History.
    Executa apenas na primeira vez que a tela é aberta para uma referência.
    
    Args:
        farol_reference: Referência Farol atual
    """
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
    
    # Initialize approval_step in session_state if not present
    if f"approval_step_{farol_reference}" not in st.session_state:
        st.session_state[f"approval_step_{farol_reference}"] = None

def handle_no_reference_selected():
    """
    Exibe mensagem e botão quando nenhuma referência está selecionada.
    
    Returns:
        bool: True se deve retornar (sem referência), False caso contrário
    """
    st.info("Selecione uma linha em Shipments para visualizar o Ticket Journey.")
    col = st.columns(1)[0]
    with col:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()
    return True

def handle_empty_dataframe(farol_reference):
    """
    Trata o caso quando não há dados para a referência, tentando exibir registros recentes.
    
    Args:
        farol_reference: Referência Farol atual
    
    Returns:
        tuple: (df, should_return)
            - df: DataFrame (vazio ou com registros recentes)
            - should_return: True se deve retornar (sem dados), False caso contrário
    """
    from database import get_return_carriers_recent
    
    st.info("Nenhum registro para esta referência. Exibindo registros recentes:")
    df = get_return_carriers_recent(limit=200)
    if df.empty:
        st.warning("A tabela F_CON_RETURN_CARRIERS está vazia.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return df, True
    return df, False