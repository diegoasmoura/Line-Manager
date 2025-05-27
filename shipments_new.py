# ==============================================
# 🚢 shipments_new.py - Novo registro de vendas
# ==============================================
 
# ---------- 1. Importações ----------
import streamlit as st
from database import load_df_udc, add_sales_record
from datetime import datetime, timedelta
import uuid
 
# ---------- 2. Carregamento de dados externos ----------
df_udc = load_df_udc()
ports_pol_options = df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist()
ports_pod_options = df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist()
 
# ---------- 3. Constantes ----------
# Campos do formulário e seus nomes internos
form_fields = {
    "Shipment Status": "s_shipment_status",
    "Type of Shipment": "s_type_of_shipment",
    "Quantity of Containers": "s_quantity_of_containers",
    "Port of Loading POL": "s_port_of_loading_pol",
    "Port of Delivery POD": "s_port_of_delivery_pod",
    "Final Destination": "s_final_destination",
    "Requested Shipment Week": "s_requested_shipment_week",
    "Requested Cut off Start Date": "s_requested_deadlines_start_date",
    "Requested Cut off End Date": "s_requested_deadlines_end_date",
    "DTHC Prepaid": "s_dthc_prepaid",
    "Afloat": "s_afloat",
    "Required Arrival Date": "s_required_arrival_date",
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
    Exibe o formulário para adicionar um novo registro de vendas.
    """
    st.subheader("New Sales Record 🚢")
 
    # Inicializa sessão se necessário
    if "current_farol_reference" not in st.session_state:
        st.session_state.current_farol_reference = str(uuid.uuid4())
 
    if "confirm_disabled_until" not in st.session_state:
        st.session_state.confirm_disabled_until = None
 
    now = datetime.now()
    confirm_disabled = (
        st.session_state.confirm_disabled_until is not None and
        now < st.session_state.confirm_disabled_until
    )
 
    # ---------- Formulário ----------
    with st.form("add_form"):
        values = {}
        missing_fields = []
 
        # Inputs em colunas organizadas
        col1, col2 = st.columns(2)
        with col1:
            values["s_shipment_status"] = st.selectbox("**:green[Shipment Status]***", ["New request"], index=0, disabled=True)
 
        col1, col2 = st.columns(2)
        with col1:
            values["s_type_of_shipment"] = st.selectbox("**:green[Type of Shipment]***", ["", "Forecast", "Extra"])
        with col2:
            values["s_quantity_of_containers"] = st.number_input("**:green[Quantity of Containers]***", min_value=0, step=1)
 
        col1, col2 = st.columns(2)
        with col1:
            values["s_requested_shipment_week"] = st.number_input("**:green[Requested Shipment Week]***", min_value=1, max_value=52, step=1)
        with col2:
            values["s_required_arrival_date"] = st.date_input("**Required Arrival Date**")
 
        col1, col2 = st.columns(2)
        with col1:
            values["s_requested_deadlines_start_date"] = st.date_input("Requested Cut off Start Date")
        with col2:
            values["s_requested_deadlines_end_date"] = st.date_input("**Requested Cut off End Date**")
 
        col1, col2 = st.columns(2)
        with col1:
            values["s_dthc_prepaid"] = st.selectbox("**:green[DTHC Prepaid]***", ["", "Yes", "No"])
        with col2:
            values["s_afloat"] = st.selectbox("**:green[Afloat]***", ["", "Yes", "No"])
 
        col1, col2 = st.columns(2)
        with col1:
            values["s_port_of_loading_pol"] = st.selectbox("Port of Loading POL", [""] + ports_pol_options)
        with col2:
            values["s_port_of_delivery_pod"] = st.selectbox("**:green[Port of Delivery POD]***", [""] + ports_pod_options)
 
        values["s_final_destination"] = st.text_input("**Final Destination**")
        values["s_comments"] = st.text_area("**Comments Sales**")
 
        # Verifica campos obrigatórios
        for field, label in required_fields.items():
            if not values.get(field):
                missing_fields.append(label)
 
        col1, col2 = st.columns(2)
        with col1:
            salvar = st.form_submit_button("✅ Confirm", disabled=confirm_disabled)
        with col2:
            voltar = st.form_submit_button("🔙 Back to Home")
 
        # ---------- Ações do formulário ----------
        if salvar:
            if missing_fields:
                st.error(f"Por favor, preencha os campos obrigatórios: {', '.join(missing_fields)}")
            else:
                st.session_state.confirm_disabled_until = datetime.now() + timedelta(seconds=3)
                values["adjustment_id"] = st.session_state.current_farol_reference
                values["user_insert"] = ''
 
                with st.spinner("Salvando dados, por favor aguarde..."):
                    if add_sales_record(values):
                        st.success("Dados salvos com sucesso!")
                        #atualizar_dados_shipments()
                        st.session_state.pop("current_farol_reference", None)
                        st.session_state["current_page"] = "main"
                        st.cache_data.clear()
                        st.rerun()
 
 
        elif voltar:
            st.session_state.pop("current_farol_reference", None)
            st.session_state["current_page"] = "main"
            st.rerun()