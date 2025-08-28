# ==============================================
# 📦 booking_new.py - Transformando um pedido de embarque em um novo booking
# ==============================================
 
# ---------- 1. Importações ----------
import streamlit as st
from database import load_df_udc, get_booking_data_by_farol_reference, update_booking_data_by_farol_reference, get_data_bookingData
from datetime import datetime, date
import time
 
# ---------- 2. Carregamento de dados externos ----------
df_udc = load_df_udc()
carriers = df_udc[df_udc["grupo"] == "Carrier"]["dado"].dropna().unique().tolist()
ports_pol_options = df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist()
ports_pod_options = df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist()
 
# ---------- 3. Constantes ----------
required_fields = {
            "b_voyage_carrier": "**:green[Voyage Carrier]***",
    "b_booking_request_date": "**:green[Booking Request Date]***"
}
 
def show_booking_management_form():
    st.subheader("📦 New Booking")
 
    # Inicializa estado do botão se necessário
    if "button_disabled" not in st.session_state:
        st.session_state.button_disabled = False
 
    # Usar referência armazenada na sessão
    farol_reference = st.session_state.get("selected_reference")
 
    if not farol_reference:
        st.warning("Nenhuma referência foi selecionada.")
        col1, col2 = st.columns([1, 1])
        with col2:
            if st.button("🔙 Back to Shipments"):
                st.session_state.pop("button_disabled", None)
                st.session_state["current_page"] = "main"
                st.rerun()
        return
 
    booking_data = get_booking_data_by_farol_reference(farol_reference)
    if not booking_data:
        # Buscar dados básicos em F_CON_SALES_DATA para inicializar o formulário
        from database import fetch_shipments_data_sales
        df_sales = fetch_shipments_data_sales()
        sales_row = df_sales[df_sales["Sales Farol Reference"] == farol_reference]
        booking_data = {
            "b_voyage_carrier": "",
            "b_freight_forwarder": "",
            "b_booking_request_date": None,
            "b_comments": ""
        }
        if not sales_row.empty:
            sales_row = sales_row.iloc[0]
            # Preenchendo os campos do formulário com os dados do registro de vendas
            booking_data["sales_quantity_of_containers"] = sales_row.get("Sales Quantity of Containers", "")
            booking_data["requested_cut_off_start_date"] = sales_row.get("Requested Cut off Start Date", "")
            booking_data["requested_cut_off_end_date"] = sales_row.get("Requested Cut off End Date", "")
            booking_data["booking_port_of_loading_pol"] = sales_row.get("Port of Loading POL", "")
            booking_data["booking_port_of_delivery_pod"] = sales_row.get("Port of Delivery POD", "")
            booking_data["final_destination"] = sales_row.get("Final Destination", "")
            booking_data["dthc"] = sales_row.get("DTHC", "")
            booking_data["requested_shipment_week"] = sales_row.get("Requested Shipment Week", "")
 
    # Conversão segura da data
    request_date = booking_data["b_booking_request_date"]
    if isinstance(request_date, datetime):
        request_date = request_date.date()
    elif request_date is None:
        request_date = date.today()
 
    with st.form("booking_form"):
        values = {}  # Inicialize aqui, logo no início do formulário
        missing_fields = []
 
        # Primeira linha: Farol Status, Farol Reference
        col_top1, col_top2 = st.columns(2)
        with col_top1:
            st.selectbox(
                "Farol Status",
                ["New request", "Booking requested"],
                index=1,  # Seleciona 'Booking requested'
                disabled=True
            )
        with col_top2:
            st.text_input("Farol Reference", value=farol_reference, disabled=True)

        # Nova linha: DTHC e Requested Shipment Week (layout de 3, mas só 2 campos)
        col_dthc, col_week, _ = st.columns(3)
        with col_dthc:
            st.text_input("DTHC", value=booking_data.get("dthc", ""), disabled=True)
        with col_week:
            st.text_input("Requested Shipment Week", value=booking_data.get("requested_shipment_week", ""), disabled=True)
        # A terceira coluna fica vazia para manter o alinhamento

        # Segunda linha: Quantity, Cut off Start, Cut off End
        col1, col2, col3 = st.columns(3)
        with col1:
            st.text_input("Quantity of Containers", value=booking_data.get("sales_quantity_of_containers", ""), disabled=True)
        with col2:
            st.text_input("Requested Cut off Start Date", value=str(booking_data.get("requested_cut_off_start_date", "")), disabled=True)
        with col3:
            st.text_input("Requested Cut off End Date", value=str(booking_data.get("requested_cut_off_end_date", "")), disabled=True)

        # Terceira linha: POL, POD, Final Destination
        col4, col5, col6 = st.columns(3)
        with col4:
            values["booking_port_of_loading_pol"] = st.selectbox(
                "Port of Loading POL",
                [booking_data.get("booking_port_of_loading_pol", "")] + [opt for opt in ports_pol_options if opt != booking_data.get("booking_port_of_loading_pol", "")],
                index=0 if booking_data.get("booking_port_of_loading_pol", "") else 0
            )
        with col5:
            values["booking_port_of_delivery_pod"] = st.selectbox(
                "Port of Delivery POD",
                [booking_data.get("booking_port_of_delivery_pod", "")] + [opt for opt in ports_pod_options if opt != booking_data.get("booking_port_of_delivery_pod", "")],
                index=0 if booking_data.get("booking_port_of_delivery_pod", "") else 0
            )
        with col6:
            st.text_input("Final Destination", value=booking_data.get("final_destination", ""), disabled=True)

        col1, col2 = st.columns(2)
        with col1:
            current_carrier = booking_data.get("b_voyage_carrier", "")
            carriers_with_blank = [""] + carriers
            selected_index = carriers_with_blank.index(current_carrier) if current_carrier in carriers_with_blank else 0
            values["b_voyage_carrier"] = st.selectbox("**:green[Voyage Carrier]***", carriers_with_blank, index=selected_index)
 
        with col2:
            values["b_freight_forwarder"] = st.text_input("Freight Forwarder", value=booking_data.get("b_freight_forwarder", ""))
 
        # Data e hora combinadas
        default_date = datetime.now().date()
        default_time = datetime.now().time()
        col1, col2 = st.columns(2)
        with col1:
            selected_date = st.date_input("**:green[Booking Request Date]***", value=default_date)
        with col2:
            selected_time = st.time_input("**:green[Booking Request Time]***", value=default_time)
 
        values["b_booking_request_date"] = datetime.combine(selected_date, selected_time)
        values["b_comments"] = st.text_area("Comments Booking", value=booking_data.get("b_comments", ""))
 
        for field, label in required_fields.items():
            if not values.get(field):
                missing_fields.append(label)
 
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            salvar = st.form_submit_button(
                "✅ Confirm",
                disabled=st.session_state.get("button_disabled", False)
            )
        with col_btn2:
            back = st.form_submit_button("🔙 Back to Shipments")
 
    if back:
        st.session_state.pop("button_disabled", None)
        st.session_state["current_page"] = "main"
        st.session_state.pop("selected_reference", None)  # Limpar referência ao voltar
        st.rerun()
 
    if salvar and not st.session_state.get("button_disabled", False):
        with st.spinner("Processando novo booking, por favor aguarde..."):
            if missing_fields:
                st.error(f"Por favor, preencha os campos obrigatórios: {', '.join(missing_fields)}")
            else:
                # Desabilita o botão imediatamente
                st.session_state.button_disabled = True
                
                try:
                    values["b_farol_status"] = "Booking requested"
                    # Adiciona os campos POL e POD para atualização
                    values["booking_port_of_loading_pol"] = values.get("booking_port_of_loading_pol", "")
                    values["booking_port_of_delivery_pod"] = values.get("booking_port_of_delivery_pod", "")
                    update_booking_data_by_farol_reference(farol_reference, values)
                    st.success("✅ Dados atualizados com sucesso!")
                    time.sleep(2)  # Aguarda 2 segundos
                    # Limpa os estados antes de redirecionar
                    st.session_state.pop("selected_reference", None)
                    st.session_state.pop("button_disabled", None)
                    st.cache_data.clear()
                    st.session_state["current_page"] = "main"
                    st.rerun()
                except Exception as e:
                    # Reabilita o botão em caso de erro
                    st.session_state.button_disabled = False
                    st.error(f"Erro ao atualizar os dados: {str(e)}")