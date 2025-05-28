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
 
# ---------- 3. Constantes ----------
required_fields = {
    "b_carrier": "**:green[Carrier]***",
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
            if st.button("🔙 Back to Home"):
                st.session_state.pop("button_disabled", None)
                st.session_state["current_page"] = "main"
                st.rerun()
        return
 
    booking_data = get_booking_data_by_farol_reference(farol_reference)
    if not booking_data:
        st.error("No booking data found for this Farol Reference.")
        return
 
    # Conversão segura da data
    request_date = booking_data["b_booking_request_date"]
    if isinstance(request_date, datetime):
        request_date = request_date.date()
    elif request_date is None:
        request_date = date.today()
 
    with st.form("booking_form"):
        values = {}
        missing_fields = []
 
        col1, col2 = st.columns(2)
        with col1:
            values["b_booking_status"] = st.selectbox(
                "Booking Status",
                [booking_data.get("b_booking_status", "N/A")],
                index=0,
                disabled=True
            )
        with col2:
            st.text_input("Farol Reference", value=farol_reference, disabled=True)
 
        col1, col2 = st.columns(2)
        with col1:
            current_carrier = booking_data.get("b_carrier", "")
            carriers_with_blank = [""] + carriers
            selected_index = carriers_with_blank.index(current_carrier) if current_carrier in carriers_with_blank else 0
            values["b_carrier"] = st.selectbox("**:green[Carrier]***", carriers_with_blank, index=selected_index)
 
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
            back = st.form_submit_button("🔙 Back to Home")
 
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