"""
Módulo de Tracking integrado ao sistema Farol
Utiliza a API Ellox da Comexia para consultas de tracking em tempo real
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from ellox_api import ElloxAPI, enrich_booking_data, format_tracking_display, get_default_api_client
from database import get_database_connection
from sqlalchemy import text

def get_api_status_indicator():
    """
    Retorna indicador visual do status da API para exibição
    
    Returns:
        Tuple com (status_text, status_color, status_icon)
    """
    # Inicializar cliente com credenciais padrão
    client = get_default_api_client()
    
    if not client.authenticated:
        return ("API Desconectada", "red", "🔴")
    
    # Testar conexão
    try:
        test_result = client.test_connection()
        
        if test_result.get("success"):
            response_time = test_result.get("response_time", 0)
            if response_time < 1.0:
                return (f"API Online ({response_time:.2f}s)", "green", "🟢")
            else:
                return (f"API Lenta ({response_time:.2f}s)", "orange", "🟡")
        else:
            error = test_result.get("error", "Erro desconhecido")
            return (f"API com Erro: {error}", "red", "🔴")
            
    except Exception as e:
        return (f"Erro no Teste: {str(e)}", "red", "🔴")

def display_api_status():
    """Exibe indicador de status da API no canto superior direito"""
    status_text, status_color, status_icon = get_api_status_indicator()
    
    # Criar um container no topo da página para o botão
    col1, col2, col3 = st.columns([6, 2, 1])
    
    with col3:
        # Botão de status da API
        if st.button(
            f"{status_icon} {status_text}",
            help="Clique para ver detalhes da API",
            type="secondary" if status_color == "green" else "primary"
        ):
            # Abrir modal/expander com detalhes
            st.session_state.show_api_details = True
    
    # Mostrar detalhes se solicitado
    if st.session_state.get("show_api_details", False):
        display_api_details_modal()

def display_api_details_modal():
    """Exibe modal com detalhes da API e configurações"""
    st.markdown("---")
    
    with st.expander("🔧 Configurações da API Ellox", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📋 Status Detalhado")
            
            # Obter status atual
            client = get_default_api_client()
            
            # Informações básicas
            st.info(f"**URL Base:** `{client.base_url}`")
            st.info(f"**Email:** `{client.email}`")
            st.info(f"**Senha:** `{'*' * len(client.password) if client.password else 'Não configurada'}`")
            
            # Status de autenticação
            if client.authenticated:
                st.success("✅ **Autenticado com sucesso**")
                if client.api_key:
                    st.code(f"Token: {client.api_key[:20]}...")
            else:
                st.error("❌ **Falha na autenticação**")
            
            # Teste de conectividade
            if st.button("🔄 Testar Conectividade"):
                with st.spinner("Testando..."):
                    test_result = client.test_connection()
                    
                    if test_result.get("success"):
                        st.success(f"✅ **Conectado!** Tempo: {test_result.get('response_time', 0):.2f}s")
                    else:
                        st.error(f"❌ **Erro:** {test_result.get('error', 'Desconhecido')}")
        
        with col2:
            st.markdown("### ⚙️ Configurações")
            
            # Formulário para editar credenciais
            with st.form("api_credentials"):
                st.markdown("**Editar Credenciais:**")
                
                new_email = st.text_input(
                    "Email",
                    value=client.email or "",
                    help="Email para autenticação na API"
                )
                
                new_password = st.text_input(
                    "Senha",
                    value="",
                    type="password",
                    help="Deixe vazio para manter a senha atual"
                )
                
                new_base_url = st.text_input(
                    "URL Base",
                    value=client.base_url,
                    help="URL base da API Ellox"
                )
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.form_submit_button("💾 Salvar", type="primary"):
                        # Atualizar credenciais
                        update_api_credentials(new_email, new_password, new_base_url)
                        st.success("✅ Credenciais atualizadas!")
                        st.rerun()
                
                with col_btn2:
                    if st.form_submit_button("❌ Fechar"):
                        st.session_state.show_api_details = False
                        st.rerun()

def update_api_credentials(email: str, password: str, base_url: str):
    """Atualiza as credenciais da API no session state"""
    if email:
        st.session_state.api_email = email
    if password:
        st.session_state.api_password = password
    if base_url:
        st.session_state.api_base_url = base_url

def get_bookings_from_database():
    """Recupera bookings do banco de dados para consulta"""
    try:
        conn = get_database_connection()
        
        query = text("""
            SELECT 
                farol_reference,
                booking_reference,
                voyage_carrier as carrier,
                voyage_code as voyage,
                vessel_name,
                port_terminal_city,
                port_of_loading_pol as pol,
                port_of_delivery_pod as pod,
                requested_deadline_start_date as etd,
                required_arrival_date as eta,
                created_at
            FROM bookings 
            ORDER BY created_at DESC 
            LIMIT 100
        """)
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar bookings: {str(e)}")
        return pd.DataFrame()

def display_voyage_search():
    """Interface para busca manual de viagens"""
    st.markdown("### 🔍 Busca Manual de Viagem")
    
    col1, col2 = st.columns(2)
    
    with col1:
        vessel_name = st.text_input("Nome do Navio", help="Ex: MAERSK ESSEX")
        carrier = st.selectbox(
            "Carrier/Armador",
            ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"]
        )
    
    with col2:
        voyage = st.text_input("Voyage", help="Ex: 240W")
        port_terminal = st.text_input("Terminal (Opcional)", help="Ex: Santos Brasil S/A")
    
    if st.button("🚢 Buscar Informações de Tracking"):
        if not vessel_name or not carrier or not voyage:
            st.error("⚠️ Preencha pelo menos Nome do Navio, Carrier e Voyage")
            return
        
        with st.spinner("Consultando API Ellox..."):
            client = get_default_api_client()
            
            if not client.authenticated:
                st.error("⚠️ Falha na autenticação com a API Ellox")
                return
            result = client.search_voyage_tracking(
                vessel_name=vessel_name,
                carrier=carrier,
                voyage=voyage,
                port_terminal=port_terminal
            )
        
        if result.get("success"):
            st.success("✅ Informações encontradas!")
            
            # Exibir dados em formato amigável
            data = result.get("data", {})
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Status", data.get("status", "N/A"))
                st.metric("IMO", data.get("vessel_imo", "N/A"))
            
            with col2:
                st.metric("MMSI", data.get("vessel_mmsi", "N/A"))
                st.metric("Próximo Porto", data.get("next_port", "N/A"))
            
            with col3:
                st.metric("ETA Estimado", data.get("estimated_arrival", "N/A"))
                st.metric("Atrasos", data.get("delays", "Nenhum"))
            
            # Exibir dados completos em expandir
            with st.expander("📋 Dados Completos da API"):
                st.json(data)
        
        else:
            st.error(f"❌ {result.get('error', 'Erro na consulta')}")

def display_bookings_tracking():
    """Interface para tracking de bookings existentes"""
    st.markdown("### 📦 Tracking de Bookings Existentes")
    
    # Carregar bookings do banco
    df_bookings = get_bookings_from_database()
    
    if df_bookings.empty:
        st.info("📭 Nenhum booking encontrado no banco de dados")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        carrier_filter = st.selectbox(
            "Filtrar por Carrier",
            ["Todos"] + sorted(df_bookings["carrier"].dropna().unique().tolist())
        )
    
    with col2:
        days_filter = st.selectbox(
            "Período",
            ["Todos", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias"]
        )
    
    with col3:
        search_term = st.text_input("Buscar", placeholder="Booking, navio, voyage...")
    
    # Aplicar filtros
    filtered_df = df_bookings.copy()
    
    if carrier_filter != "Todos":
        filtered_df = filtered_df[filtered_df["carrier"] == carrier_filter]
    
    if days_filter != "Todos":
        days_map = {"Últimos 7 dias": 7, "Últimos 30 dias": 30, "Últimos 90 dias": 90}
        cutoff_date = datetime.now() - timedelta(days=days_map[days_filter])
        filtered_df = filtered_df[pd.to_datetime(filtered_df["created_at"]) >= cutoff_date]
    
    if search_term:
        mask = (
            filtered_df["booking_reference"].str.contains(search_term, case=False, na=False) |
            filtered_df["vessel_name"].str.contains(search_term, case=False, na=False) |
            filtered_df["voyage"].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    st.write(f"**{len(filtered_df)} bookings encontrados**")
    
    # Exibir tabela de bookings
    if not filtered_df.empty:
        # Seleção de booking para tracking
        selected_indices = st.multiselect(
            "Selecione bookings para consultar tracking:",
            options=filtered_df.index,
            format_func=lambda x: f"{filtered_df.loc[x, 'booking_reference']} - {filtered_df.loc[x, 'vessel_name']} ({filtered_df.loc[x, 'voyage']})"
        )
        
        if selected_indices and st.button("🔍 Consultar Tracking Selecionados"):
            client = get_default_api_client()
            
            if not client.authenticated:
                st.error("⚠️ Falha na autenticação com a API Ellox")
                return
            
            for idx in selected_indices:
                booking = filtered_df.loc[idx]
                
                st.markdown(f"#### 📦 {booking['booking_reference']}")
                
                with st.spinner(f"Consultando {booking['vessel_name']}..."):
                    result = client.search_voyage_tracking(
                        vessel_name=booking["vessel_name"],
                        carrier=booking["carrier"],
                        voyage=booking["voyage"],
                        port_terminal=booking.get("port_terminal_city")
                    )
                
                if result.get("success"):
                    data = result.get("data", {})
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Navio", booking["vessel_name"])
                        st.metric("Voyage", booking["voyage"])
                    
                    with col2:
                        st.metric("Carrier", booking["carrier"])
                        st.metric("Status", data.get("status", "N/A"))
                    
                    with col3:
                        st.metric("POL", booking.get("pol", "N/A"))
                        st.metric("POD", booking.get("pod", "N/A"))
                    
                    with col4:
                        st.metric("ETA Original", booking.get("eta", "N/A"))
                        st.metric("ETA Atual", data.get("estimated_arrival", "N/A"))
                    
                    # Alertas de atraso
                    if data.get("delays"):
                        st.warning(f"⚠️ **Atraso reportado:** {data['delays']}")
                    
                    # Posição atual se disponível
                    if data.get("current_position"):
                        pos = data["current_position"]
                        st.info(f"📍 **Posição atual:** {pos.get('latitude', 'N/A')}, {pos.get('longitude', 'N/A')}")
                
                else:
                    st.error(f"❌ Erro na consulta: {result.get('error')}")
                
                st.divider()
        
        # Exibir tabela resumida
        display_columns = [
            "farol_reference", "booking_reference", "vessel_name", 
            "voyage", "carrier", "pol", "pod", "eta"
        ]
        
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        st.dataframe(
            filtered_df[available_columns],
            use_container_width=True,
            hide_index=True
        )

def display_vessel_schedule():
    """Interface para consulta de cronograma de navios"""
    st.markdown("### 🗓️ Cronograma de Navios")
    
    col1, col2 = st.columns(2)
    
    with col1:
        vessel_name = st.text_input("Nome do Navio", key="schedule_vessel")
    
    with col2:
        carrier = st.selectbox(
            "Carrier",
            ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
            key="schedule_carrier"
        )
    
    if st.button("📅 Consultar Cronograma"):
        if not vessel_name or not carrier:
            st.error("⚠️ Preencha Nome do Navio e Carrier")
            return
        
        with st.spinner("Consultando cronograma..."):
            client = get_default_api_client()
            
            if not client.authenticated:
                st.error("⚠️ Falha na autenticação com a API Ellox")
                return
            result = client.get_vessel_schedule(vessel_name, carrier)
        
        if result.get("success"):
            data = result.get("data", {})
            
            st.success("✅ Cronograma encontrado!")
            
            # Exibir cronograma se disponível
            schedule = data.get("schedule", [])
            
            if schedule:
                df_schedule = pd.DataFrame(schedule)
                st.dataframe(df_schedule, use_container_width=True)
            else:
                st.info("📭 Nenhum cronograma detalhado disponível")
            
            # Dados completos
            with st.expander("📋 Dados Completos"):
                st.json(data)
        
        else:
            st.error(f"❌ {result.get('error')}")

def exibir_tracking():
    """Interface principal do módulo de tracking integrado ao Farol"""
    
    st.title("🚢 Tracking via API Ellox")
    st.markdown("**Consulta de informações de viagem e tracking em tempo real**")
    
    # Exibir indicador de status da API no canto superior direito
    display_api_status()
    
    # Verificar status da API
    client = get_default_api_client()
    if client.authenticated:
        st.success("✅ Sistema de tracking ativo e conectado")
    else:
        st.error("❌ Falha na autenticação com a API Ellox - Verifique as credenciais")
    
    # Tabs principais
    tab1, tab2, tab3 = st.tabs([
        "🔍 Busca Manual", 
        "📦 Bookings Existentes", 
        "📅 Cronograma de Navios"
    ])
    
    with tab1:
        display_voyage_search()
    
    with tab2:
        display_bookings_tracking()
    
    with tab3:
        display_vessel_schedule()
    
    # Footer
    st.markdown("---")
    st.markdown("*Powered by [Ellox API - Comexia](https://developers.comexia.digital/)*")