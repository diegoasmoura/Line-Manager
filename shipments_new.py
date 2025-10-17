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
 
# ---------- 3. Constantes ----------
# Mapeamento de valores POD do Excel para valores da tabela UDC
# Permite que os valores do Excel Bulk Upload sejam exibidos corretamente nos dropdowns
POD_MAPPING = {
    "ANQING": "Anqing",
    "CARTAGENA": "Cartagen",
    "CHATTOGRAM": "Chattog",
    "HAIPHONG": "Haiphong",
    "HO CHI MINH CITY": "Hochimin",
    "ISKENDERUN": "Iskender",
    "IZMIR": "Izmir",
    "JAKARTA": "Jakarta",
    "KWANGYANG": "Kwangyan",
    "MUNDRA": "Mundra",
    "NHAVA SHEVA (JNP)": "Nhavashe",
    "PORT QASIM/KARACHI": "Karachi",
    "QINGDAO": "Qingdao",
    "ZHANGJIAGANG": "Zhangjia",
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

            col1, col2 = st.columns(2)
            with col1:
                values["s_requested_shipment_week"] = st.number_input("**:green[Requested Shipment Week]***", min_value=1, max_value=52, step=1)
            with col2:
                values["s_required_arrival_date_expected"] = st.date_input("Required Arrival Date Expected", value=None)

            col1, col2 = st.columns(2)
            with col1:
                values["s_requested_deadlines_start_date"] = st.date_input("Requested Deadline Start Date", value=None)
            with col2:
                values["s_requested_deadlines_end_date"] = st.date_input("Requested Deadline End Date", value=None)

            col1, col2 = st.columns(2)
            with col1:
                values["s_shipment_period_start_date"] = st.date_input("Shipment Period Start Date", value=None)
            with col2:
                values["s_shipment_period_end_date"] = st.date_input("Shipment Period End Date", value=None)

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
                highlighted_cols = ["HC", "Week", "LIMITE EMBARQUE - PNL", "DTHC", "TIPO EMBARQUE", "POD", "INLAND", "TERM"]
                def highlight_specific_cols(s):
                    return [
                        'background-color: #e6f3ff; font-weight: bold;' if s.name in highlighted_cols else ''
                        for _ in s
                    ]
                st.dataframe(df_excel.style.apply(highlight_specific_cols, axis=0))
                
                # Validação das colunas obrigatórias
                required_cols = [
                    "HC", "Week", "LIMITE EMBARQUE - PNL", "DTHC", "TIPO EMBARQUE", "POD", "INLAND"
                ]
                missing_cols = [col for col in required_cols if col not in df_excel.columns]
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
                    sales_comments = (str(row.get("RESTRIÇÃO ARMADOR +", "")) + " " + str(row.get("CONTRATO OPÇÃO DESTINO", ""))).strip()
                    tipo_embarque_val = row.get("TIPO EMBARQUE", "")
                    s_afloat_val = "Yes" if str(tipo_embarque_val).strip().lower() == "afloat" else "No"
                    hc_val = row.get("HC", "")
                    try:
                        hc_val = int(float(hc_val)) if pd.notna(hc_val) and str(hc_val).strip() != "" else 0
                    except Exception:
                        hc_val = 0
                    
                    # Mapeamento do campo TERM para s_vip_pnl_risk
                    term_val = str(row.get("TERM", "")).strip().upper()
                    s_vip_pnl_risk = ""
                    if term_val in ["VIP", "PNL", "RISK"]:
                        s_vip_pnl_risk = term_val
                    
                    # Mapeamento do s_pnl_destination baseado no s_vip_pnl_risk
                    s_pnl_destination = "Yes" if s_vip_pnl_risk == "PNL" else "No"
                    
                    # REMOVIDO: Mapeamento incorreto que colocava VIP/PNL/RISK em s_final_destination
                    # O campo s_final_destination deve ser preenchido manualmente pelo usuário
                    # O campo s_vip_pnl_risk é independente e não deve afetar s_final_destination
                    s_final_destination = ""
                    
                    # Tratamento da coluna LIMITE EMBARQUE - PNL para validar se é uma data válida
                    limite_embarque_val = row.get("LIMITE EMBARQUE - PNL", "")
                    s_required_arrival_date_expected = None
                    
                    if pd.notna(limite_embarque_val) and str(limite_embarque_val).strip() != "":
                        try:
                            # Tenta converter para datetime
                            if isinstance(limite_embarque_val, str):
                                # Se for string, tenta fazer parse
                                parsed_date = pd.to_datetime(limite_embarque_val)
                                s_required_arrival_date_expected = parsed_date
                            elif isinstance(limite_embarque_val, (int, float)):
                                # Se for número (como 0), ignora
                                s_required_arrival_date_expected = None
                            else:
                                # Se for datetime/date, mantém como está
                                s_required_arrival_date_expected = limite_embarque_val
                        except (ValueError, TypeError):
                            # Se não conseguir converter, ignora o valor
                            s_required_arrival_date_expected = None
                    
                    # Aplicar mapeamento POD para compatibilidade com UDC
                    pod_value = row.get("POD", "")
                    pod_mapped = POD_MAPPING.get(pod_value, pod_value)
                    
                    values = {
                        "s_farol_status": "New request",
                        "s_type_of_shipment": "Forecast",
                        "s_quantity_of_containers": hc_val,
                        "s_requested_shipment_week": row.get("Week", ""),
                        "s_required_arrival_date_expected": s_required_arrival_date_expected,
                        "s_requested_deadlines_start_date": "",
                        "s_requested_deadlines_end_date": "",
                        "s_shipment_period_start_date": "",
                        "s_shipment_period_end_date": "",
                        "s_dthc_prepaid": row.get("DTHC", ""),
                        "s_afloat": s_afloat_val,
                        "s_port_of_loading_pol": "",
                        "s_vip_pnl_risk": s_vip_pnl_risk,
                        "s_pnl_destination": s_pnl_destination,
                        "s_port_of_delivery_pod": pod_mapped,
                        "s_final_destination": s_final_destination,
                        "s_comments": sales_comments,
                        "adjustment_id": str(uuid.uuid4()),
                        "user_insert": ''
                    }
                    try:
                        if add_sales_record(values):
                            success += 1
                        else:
                            fail += 1
                    except Exception as e:
                        fail += 1
                    
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