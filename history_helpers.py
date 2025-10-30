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
            df_processed[col] = df_processed[col].astype(str).replace('NaT', '')
        else:
            df_processed[col] = df_processed[col].fillna('')

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