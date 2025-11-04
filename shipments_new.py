# ==============================================
# 🚢 shipments_new.py - Novo registro de vendas
# ==============================================
 
# ---------- 1. Importações ----------
import streamlit as st
from database import load_df_udc, add_sales_record
from datetime import datetime, timedelta
import uuid
import time
import pandas as pd # Added for Excel upload
 
# ---------- 2. Carregamento de dados externos ----------
df_udc = load_df_udc()
ports_pol_options = df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist()
ports_pod_options = df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist()
dthc_options = df_udc[df_udc["grupo"] == "DTHC"]["dado"].dropna().unique().tolist()
vip_pnl_risk_options = df_udc[df_udc["grupo"] == "VIP PNL Risk"]["dado"].dropna().unique().tolist()
# Carregar terminais da tabela F_ELLOX_TERMINALS (com fallback para unificada)
from database import list_terminal_names, list_terminal_names_from_unified
terminal_options = list_terminal_names() or list_terminal_names_from_unified() or []
 
# ---------- 3. Constantes ----------
# Mapeamento de colunas do Excel para campos internos do sistema
EXCEL_COLUMN_MAPPING = {
    "REFERENCIA": "s_sales_order_reference",
    "Carrier": "b_voyage_carrier",
    "Origem": "s_plant_of_origin",
    "Destino_City": "s_final_destination",
    "Destino_Country": "b_pod_country_acronym",
    "Margem": "b_margin",
    "CTNRS": "s_quantity_of_containers",
    "Week": "s_requested_shipment_week",
    "BOOKING": "b_booking_reference",
    "Total Price": "b_freight_rate_usd",
    "Bogey": "b_bogey_sale_price_usd",
    "PnL Frete": "b_freightppnl",
    "PnL Bogey": "b_bogey_pnl",
    "ML": "b_ml_profit_margin",
    "NAVIO": "b_vessel_name",
    "VIAGEM": "b_voyage_code",
    "ETD": "b_data_estimativa_saida_etd",
    "DTHC": "s_dthc_prepaid",
    "REGION": "b_destination_trade_region",
}

# Colunas obrigatórias do novo template
REQUIRED_EXCEL_COLS = ["REFERENCIA", "CTNRS", "Week", "DTHC"]

# Mapeamento de colunas do Excel para nomes de exibição padrão
EXCEL_DISPLAY_NAMES = {
    "REFERENCIA": "Sales Order Reference",
    "Carrier": "Carrier",
    "Origem": "Plant of Origin",
    "Destino_City": "Final Destination",
    "Destino_Country": "POD Country Acronym",
    "Margem": "Margin",
    "CTNRS": "Sales Quantity of Containers",
    "Week": "Requested Shipment Week",
    "BOOKING": "Booking Reference",
    "Total Price": "Freight Rate USD",
    "Bogey": "Bogey Sale Price USD",
    "PnL Frete": "Freight PNL",
    "PnL Bogey": "Bogey PNL",
    "ML": "ML Profit Margin",
    "NAVIO": "Vessel Name",
    "VIAGEM": "Voyage Code",
    "ETD": "data_estimativa_saida",
    "DTHC": "DTHC",
    "REGION": "Destination Trade Region",
}

# Campos do formulário e seus nomes internos
form_fields = {
    "Type of Shipment": "s_type_of_shipment",
    "Quantity of Containers": "s_quantity_of_containers",
    "Port of Loading POL": "s_port_of_loading_pol",
    "Port of Delivery POD": "s_port_of_delivery_pod",
    "Final Destination": "s_final_destination",
    "Requested Shipment Week": "s_requested_shipment_week",
            "Requested Deadline Start Date": "s_requested_deadlines_start_date",
        "Requested Deadline End Date": "s_requested_deadlines_end_date",
    "Shipment Period Start Date": "s_shipment_period_start_date",
    "Shipment Period End Date": "s_shipment_period_end_date",
    "DTHC Prepaid": "s_dthc_prepaid",
    "Afloat": "s_afloat",
            "Required Arrival Date Expected": "s_required_arrival_date_expected",
    "Comments Sales": "s_comments"
}
 
# Campos obrigatórios
required_fields = {
    "s_type_of_shipment": "**:green[Type of Shipment]***",
    "s_quantity_of_containers": "**:green[Quantity of Containers]***",
    "s_port_of_delivery_pod": "**:green[Port of Delivery POD]***",
    "s_requested_shipment_week": "**:green[Requested Shipment Week]***",
    "s_dthc_prepaid": "**:green[DTHC Prepaid]***",
    "s_afloat": "**:green[Afloat]***"
}
 
# ---------- 4. Função principal ----------
def show_add_form():
    """
    Displays the form to add a new sales record.
    """
    st.subheader("New Sales Record 🚢")

    tab_manual, tab_excel = st.tabs(["Manual Entry", "Excel Upload (Bulk)"])

    with tab_manual:
        # ---------- Manual Form ----------
        if "current_farol_reference" not in st.session_state:
            st.session_state.current_farol_reference = str(uuid.uuid4())
            st.session_state.button_disabled = False

        if "confirm_disabled_until" not in st.session_state:
            st.session_state.confirm_disabled_until = None

        now = datetime.now()
        confirm_disabled = (
            st.session_state.confirm_disabled_until is not None and
            now < st.session_state.confirm_disabled_until
        )

        with st.form("add_form"):
            values = {}
            missing_fields = []

            col1, col2 = st.columns(2)
            with col1:
                values["s_farol_status"] = st.selectbox("**:green[Farol Status]***", ["New request"], index=0, disabled=True)

            col1, col2 = st.columns(2)
            with col1:
                values["s_type_of_shipment"] = st.selectbox("**:green[Type of Shipment]***", ["", "Forecast", "Extra"])
            with col2:
                values["s_quantity_of_containers"] = st.number_input("**:green[Quantity of Containers]***", min_value=0, step=1)

            # Linha 1: Requested Shipment Week com mesma largura dos demais (1/2 da linha)
            col1, col2 = st.columns(2)
            with col1:
                values["s_requested_shipment_week"] = st.number_input("**:green[Requested Shipment Week]***", min_value=1, max_value=52, step=1)
            with col2:
                st.empty()

            # Linha 2: Required Sail Date | Required Arrival Date
            col1, col2 = st.columns(2)
            with col1:
                values["s_required_sail_date"] = st.date_input(
                    "Required Sail Date",
                    value=None,
                    key=f"add_required_sail_date_{st.session_state.current_farol_reference}"
                )
            with col2:
                values["s_required_arrival_date_expected"] = st.date_input(
                    "Required Arrival Date",
                    value=None,
                    key=f"add_required_arrival_date_{st.session_state.current_farol_reference}"
                )

            # Linha 3: Requested Deadline Start | Requested Deadline End
            col1, col2 = st.columns(2)
            with col1:
                values["s_requested_deadlines_start_date"] = st.date_input(
                    "Requested Deadline Start Date",
                    value=None,
                    key=f"add_requested_deadline_start_{st.session_state.current_farol_reference}"
                )
            with col2:
                values["s_requested_deadlines_end_date"] = st.date_input(
                    "Requested Deadline End Date",
                    value=None,
                    key=f"add_requested_deadline_end_{st.session_state.current_farol_reference}"
                )

            # Linha 4: Shipment Period Start | Shipment Period End
            col1, col2 = st.columns(2)
            with col1:
                values["s_shipment_period_start_date"] = st.date_input(
                    "Shipment Period Start Date",
                    value=None,
                    key=f"add_shipment_period_start_{st.session_state.current_farol_reference}"
                )
            with col2:
                values["s_shipment_period_end_date"] = st.date_input(
                    "Shipment Period End Date",
                    value=None,
                    key=f"add_shipment_period_end_{st.session_state.current_farol_reference}"
                )

            col1, col2 = st.columns(2)
            with col1:
                values["s_shipment_period_start_date"] = st.date_input("Shipment Period Start Date", value=None)
            with col2:
                values["s_shipment_period_end_date"] = st.date_input("Shipment Period End Date", value=None)

            # (Mantido sem campo adicional aqui; já foi exibido logo após Required Sail Date)

            col1, col2 = st.columns(2)
            with col1:
                values["s_dthc_prepaid"] = st.selectbox("**:green[DTHC]***", [""] + dthc_options)
            with col2:
                values["s_afloat"] = st.selectbox("**:green[Afloat]***", ["", "Yes", "No"])

            col1, col2 = st.columns(2)
            with col1:
                values["s_port_of_loading_pol"] = st.selectbox("Port of Loading POL", [""] + ports_pol_options)
            with col2:
                values["s_port_of_delivery_pod"] = st.selectbox("**:green[Port of Delivery POD]***", [""] + ports_pod_options)

            col1, col2 = st.columns(2)
            with col1:
                values["s_final_destination"] = st.text_input("Final Destination")
            with col2:
                values["b_terminal"] = st.selectbox("Terminal", [""] + terminal_options)
            
            # Restriction Type na linha de baixo, ocupando 1 coluna
            col1, col2 = st.columns(2)
            with col1:
                values["s_vip_pnl_risk"] = st.selectbox("Restriction Type", [""] + vip_pnl_risk_options)

            values["s_comments"] = st.text_area("Sales Comments")

            for field, label in required_fields.items():
                if not values.get(field):
                    missing_fields.append(label)

            col1, col2 = st.columns(2)
            with col1:
                salvar = st.form_submit_button(
                    "✅ Confirm",
                    disabled=st.session_state.get("button_disabled", False)
                )
            with col2:
                voltar = st.form_submit_button("🔙 Back to Shipments")

            if salvar and not st.session_state.get("button_disabled", False):
                if missing_fields:
                    st.error(f"Please fill in the required fields: {', '.join(missing_fields)}")
                else:
                    st.session_state.button_disabled = True
                    values["adjustment_id"] = st.session_state.current_farol_reference
                    values["user_insert"] = ''
                    
                    # Mapeamento do s_pnl_destination baseado no s_vip_pnl_risk
                    values["s_pnl_destination"] = "Yes" if values.get("s_vip_pnl_risk") == "PNL" else "No"
                    
                    # REMOVIDO: Mapeamento incorreto que colocava VIP/PNL/RISK em s_final_destination
                    # O campo s_final_destination deve ser preenchido manualmente pelo usuário
                    # O campo s_vip_pnl_risk é independente e não deve afetar s_final_destination
                    
                    # Tratamento da data s_required_arrival_date_expected no formulário manual
                    if values.get("s_required_arrival_date_expected"):
                        try:
                            # Converte para datetime se for uma data válida
                            if isinstance(values["s_required_arrival_date_expected"], str):
                                values["s_required_arrival_date_expected"] = pd.to_datetime(values["s_required_arrival_date_expected"])
                        except (ValueError, TypeError):
                            values["s_required_arrival_date_expected"] = None

                    with st.spinner("Processing new shipment, please wait..."):
                        if add_sales_record(values):
                            st.success("✅ Data saved successfully!")
                            time.sleep(2)
                            st.session_state.pop("current_farol_reference", None)
                            st.session_state.pop("button_disabled", None)
                            st.session_state["current_page"] = "main"
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.session_state.button_disabled = False
                            st.error("Error saving data. Please try again.")

            elif voltar:
                st.session_state.pop("current_farol_reference", None)
                st.session_state.pop("button_disabled", None)
                st.session_state["current_page"] = "main"
                st.rerun()

    with tab_excel:
        st.markdown("Download the <a href='/docs/template_embarques.xlsx' download>Excel template</a> to ensure the correct format.", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Select an Excel file (.xlsx)", type=["xlsx"], key="excel_mass_upload")
        df_excel = None
        
        # Processa e exibe o arquivo automaticamente quando carregado
        if uploaded_file:
            try:
                df_excel = pd.read_excel(uploaded_file)
                
                # Criar cópia para exibição com nomes padrão
                df_display = df_excel.copy()
                
                # Renomear colunas para nomes de exibição padrão
                rename_dict = {}
                for col in df_display.columns:
                    if col in EXCEL_DISPLAY_NAMES:
                        rename_dict[col] = EXCEL_DISPLAY_NAMES[col]
                
                if rename_dict:
                    df_display.rename(columns=rename_dict, inplace=True)
                
                # Destacar colunas importantes (todas as colunas mapeadas)
                highlighted_cols = list(EXCEL_DISPLAY_NAMES.values())
                def highlight_specific_cols(s):
                    return [
                        'background-color: #e6f3ff; font-weight: bold;' if s.name in highlighted_cols else ''
                        for _ in s
                    ]
                st.dataframe(df_display.style.apply(highlight_specific_cols, axis=0))
                
                # Validação das colunas obrigatórias
                missing_cols = [col for col in REQUIRED_EXCEL_COLS if col not in df_excel.columns]
                if missing_cols:
                    st.error(f"The file is missing the required columns: {', '.join(missing_cols)}")
                else:
                    st.success(f"✅ File loaded successfully! Found {len(df_excel)} rows to process.")
                    
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
        
        # Formulário apenas para os botões
        with st.form("excel_upload_box"):
            col1, col2 = st.columns(2)
            with col1:
                confirm_bulk = st.form_submit_button("✅ Confirm Bulk Upload", disabled=(df_excel is None))
            with col2:
                back_bulk = st.form_submit_button("🔙 Back to Shipments")
            
            if back_bulk:
                st.session_state["current_page"] = "main"
                st.rerun()
            
            if confirm_bulk and df_excel is not None:
                success, fail = 0, 0
                progress_bar = st.progress(0, text="Processing shipments...")
                
                for idx, row in df_excel.iterrows():
                    values = {
                        # Campos padrão
                        "s_farol_status": "New request",
                        "s_type_of_shipment": "Forecast",
                        "adjustment_id": str(uuid.uuid4()),
                        "user_insert": '',
                    }
                    
                    # Mapear todas as colunas do Excel para os campos internos
                    for excel_col, internal_field in EXCEL_COLUMN_MAPPING.items():
                        if excel_col in df_excel.columns:
                            cell_value = row.get(excel_col, "")
                            
                            # Tratamento especial para diferentes tipos de dados
                            if internal_field in ["s_quantity_of_containers"]:
                                # Converter para inteiro
                                try:
                                    values[internal_field] = int(float(cell_value)) if pd.notna(cell_value) and str(cell_value).strip() != "" else 0
                                except (ValueError, TypeError):
                                    values[internal_field] = 0
                            
                            elif internal_field in ["b_data_estimativa_saida_etd"]:
                                # Converter datas
                                if pd.notna(cell_value) and str(cell_value).strip() != "":
                                    try:
                                        if isinstance(cell_value, str):
                                            values[internal_field] = pd.to_datetime(cell_value)
                                        elif isinstance(cell_value, (int, float)):
                                            values[internal_field] = None
                                        else:
                                            values[internal_field] = cell_value
                                    except (ValueError, TypeError):
                                        values[internal_field] = None
                                else:
                                    values[internal_field] = None
                            
                            elif internal_field in ["b_margin", "b_freight_rate_usd", "b_bogey_sale_price_usd", 
                                                     "b_freightppnl", "b_bogey_pnl", "b_ml_profit_margin"]:
                                # Converter valores numéricos monetários
                                try:
                                    if pd.notna(cell_value) and str(cell_value).strip() != "":
                                        values[internal_field] = float(cell_value)
                                    else:
                                        values[internal_field] = None
                                except (ValueError, TypeError):
                                    values[internal_field] = None
                            
                            else:
                                # Campos de texto simples
                                if pd.notna(cell_value):
                                    values[internal_field] = str(cell_value).strip()
                                else:
                                    values[internal_field] = ""
                    
                    # Validação de campos obrigatórios
                    required_check_fields = {
                        "s_sales_order_reference": "REFERENCIA",
                        "s_quantity_of_containers": "CTNRS",
                        "s_requested_shipment_week": "Week",
                        "s_dthc_prepaid": "DTHC",
                    }
                    
                    missing_required = []
                    for field, excel_col in required_check_fields.items():
                        if not values.get(field) or (isinstance(values.get(field), (int, float)) and values.get(field) == 0):
                            missing_required.append(excel_col)
                    
                    if missing_required:
                        fail += 1
                        continue
                    
                    try:
                        if add_sales_record(values):
                            success += 1
                        else:
                            fail += 1
                    except Exception as e:
                        fail += 1
                        print(f"Erro ao processar linha {idx + 1}: {e}")
                    
                    # Atualiza a barra de progresso
                    progress = (idx + 1) / len(df_excel)
                    progress_bar.progress(progress, text=f"Processing shipment {idx+1} of {len(df_excel)}...")
                
                progress_bar.empty()
                st.success(f"✅ {success} shipments successfully uploaded!")
                if fail:
                    st.error(f"❌ {fail} shipments failed. Please check the file data.")
                
                # Limpa o cache e volta para a tela principal
                st.cache_data.clear()
                time.sleep(2)
                st.session_state["current_page"] = "main"
                st.rerun()