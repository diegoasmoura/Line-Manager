"""
Módulo de Tracking integrado ao sistema Farol
Utiliza a API Ellox da Comexia para consultas de tracking em tempo real
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import re
from ellox_api import ElloxAPI, enrich_booking_data, format_tracking_display, get_default_api_client
from database import get_database_connection
from sqlalchemy import text

def format_cnpj(cnpj_input: str) -> str:
    """
    Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX
    
    Args:
        cnpj_input: CNPJ em qualquer formato (só números ou já formatado)
        
    Returns:
        CNPJ formatado ou string original se inválido
    """
    if not cnpj_input:
        return ""
    
    # Remove tudo que não é número
    numbers_only = re.sub(r'[^\d]', '', cnpj_input)
    
    # Verifica se tem 14 dígitos
    if len(numbers_only) != 14:
        return cnpj_input  # Retorna original se não tiver 14 dígitos
    
    # Aplica a máscara XX.XXX.XXX/XXXX-XX
    formatted = f"{numbers_only[:2]}.{numbers_only[2:5]}.{numbers_only[5:8]}/{numbers_only[8:12]}-{numbers_only[12:14]}"
    
    return formatted

def validate_cnpj_format(cnpj: str) -> bool:
    """
    Valida se o CNPJ tem o formato correto (14 dígitos)
    
    Args:
        cnpj: CNPJ para validar
        
    Returns:
        True se válido, False caso contrário
    """
    if not cnpj:
        return False
    
    # Remove caracteres não numéricos
    numbers_only = re.sub(r'[^\d]', '', cnpj)
    
    # Verifica se tem exatamente 14 dígitos
    return len(numbers_only) == 14

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_ships_from_database():
    """Carrega navios do banco com cache"""
    try:
        from ellox_data_queries import ElloxDataQueries
        queries = ElloxDataQueries()
        ships_df = queries.get_ships_by_terminal()
        return ships_df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)  # Cache por 5 minutos  
def load_terminals_from_database():
    """Carrega terminais do banco com cache"""
    try:
        from ellox_data_queries import ElloxDataQueries
        queries = ElloxDataQueries()
        terminals_df = queries.get_all_terminals()
        return terminals_df
    except:
        return pd.DataFrame()

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
    
    # Carregar dados do banco com cache
    all_ships = load_ships_from_database()
    all_terminals = load_terminals_from_database()
    
    # Preparar opções para selectbox
    ship_options = [""] + sorted(all_ships['navio'].unique().tolist()) if not all_ships.empty else [""]
    terminal_options = [""] + all_terminals['nome'].tolist() if not all_terminals.empty else [""]
    
    # Mostrar contador de opções
    if len(ship_options) > 1:
        st.info(f"📊 {len(ship_options)-1} navios e {len(terminal_options)-1} terminais carregados do banco")
    
    # Filtro por carrier para reduzir lista de navios
    col_filter1, col_filter2 = st.columns(2)
    
    with col_filter1:
        carrier_filter = st.selectbox(
            "🔍 Filtrar por Carrier (Opcional)",
            ["Todos"] + ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
            help="Filtrar lista de navios por carrier para facilitar seleção"
        )
    
    # Filtrar navios por carrier se selecionado
    filtered_ship_options = ship_options
    if carrier_filter != "Todos" and not all_ships.empty:
        filtered_ships = all_ships[all_ships['carrier'] == carrier_filter]['navio'].unique()
        filtered_ship_options = [""] + sorted(filtered_ships.tolist())
        
        if len(filtered_ship_options) > 1:
            st.success(f"✅ {len(filtered_ship_options)-1} navios do carrier {carrier_filter}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        vessel_name = st.selectbox(
            "Nome do Navio",
            filtered_ship_options,
            help="Selecione um navio da lista filtrada"
        )
        
        # Detectar carrier automaticamente baseado no navio selecionado
        detected_carrier = ""
        if vessel_name and not all_ships.empty:
            ship_info = all_ships[all_ships['navio'] == vessel_name]
            if not ship_info.empty:
                detected_carrier = ship_info['carrier'].iloc[0]
        
        carrier = st.selectbox(
            "Carrier/Armador",
            ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
            index=(["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"].index(detected_carrier) 
                   if detected_carrier in ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"] else 0)
        )
    
    with col2:
        voyage = st.text_input("Voyage", help="Ex: 240W")
        port_terminal = st.selectbox(
            "Terminal (Opcional)",
            terminal_options,
            help="Selecione um terminal da lista ou deixe vazio"
        )
        
        # Mostrar informações do navio selecionado
        if vessel_name and not all_ships.empty:
            ship_info = all_ships[all_ships['navio'] == vessel_name]
            if not ship_info.empty:
                ship_data = ship_info.iloc[0]
                real_carrier = ship_data.get('carrier', 'N/A')
                real_terminal = ship_data.get('terminal', 'N/A')
                
                # Verificar se carrier selecionado difere do real
                if carrier and carrier != real_carrier:
                    st.warning(f"⚠️ **Inconsistência detectada!**\n"
                             f"🚢 Navio: **{vessel_name}**\n"
                             f"📦 Carrier no banco: **{real_carrier}**\n"
                             f"📦 Carrier selecionado: **{carrier}**\n"
                             f"🏢 Terminal: {real_terminal}\n\n"
                             f"💡 **Recomendação**: Use o carrier do banco para melhor resultado na API")
                else:
                    st.info(f"🚢 **{vessel_name}**\n"
                           f"📦 Carrier: {real_carrier}\n"
                           f"🏢 Terminal: {real_terminal}")
    
    # Pré-popular terminal se o navio foi selecionado
    if vessel_name and not all_ships.empty and not port_terminal:
        ship_info = all_ships[all_ships['navio'] == vessel_name]
        if not ship_info.empty:
            suggested_terminal = ship_info['terminal'].iloc[0]
            if suggested_terminal in terminal_options:
                st.info(f"💡 Sugestão: Terminal **{suggested_terminal}** (baseado no navio selecionado)")
    
    # Botão para usar carrier do banco automaticamente
    if vessel_name and not all_ships.empty:
        ship_info = all_ships[all_ships['navio'] == vessel_name]
        if not ship_info.empty:
            real_carrier = ship_info.iloc[0]['carrier']
            if carrier != real_carrier:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"🔄 Usar Carrier do Banco ({real_carrier})", key="use_real_carrier"):
                        st.session_state.temp_carrier = real_carrier
                        st.rerun()
                        
                # Aplicar carrier do banco se selecionado
                if st.session_state.get('temp_carrier'):
                    carrier = st.session_state.temp_carrier
                    st.success(f"✅ Usando carrier do banco: **{carrier}**")
    
    if st.button("🚢 Buscar Informações de Tracking"):
        if not vessel_name or not carrier or not voyage:
            st.error("⚠️ Preencha pelo menos Nome do Navio, Carrier e Voyage")
            return
        
        # Usar carrier do banco se disponível
        final_carrier = carrier
        if vessel_name and not all_ships.empty:
            ship_info = all_ships[all_ships['navio'] == vessel_name]
            if not ship_info.empty:
                real_carrier = ship_info.iloc[0]['carrier']
                if st.session_state.get('use_bank_carrier', False):
                    final_carrier = real_carrier
                    st.info(f"🔄 Usando carrier do banco: **{real_carrier}**")
                
                # Aviso especial para carrier "OUTROS"
                if real_carrier == "OUTROS":
                    st.warning(f"⚠️ **Atenção**: O navio **{vessel_name}** está classificado como carrier \"**OUTROS**\" no banco.\n"
                             f"Isso pode indicar que o carrier real não foi identificado corretamente pela API Ellox.\n"
                             f"A busca pode não retornar resultados precisos.")
        
        with st.spinner("Consultando API Ellox..."):
            client = get_default_api_client()
            
            if not client.authenticated:
                st.error("⚠️ Falha na autenticação com a API Ellox")
                return
            result = client.search_voyage_tracking(
                vessel_name=vessel_name,
                carrier=final_carrier,
                voyage=voyage,
                port_terminal=port_terminal
            )
        
        if result.get("success"):
            st.success("✅ Viagem encontrada!")
            
            # Exibir dados em formato amigável
            data = result.get("data", {})
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🚢 Navio", data.get("vessel_name", "N/A"))
                st.metric("📦 Carrier", data.get("carrier", "N/A"))
            
            with col2:
                st.metric("🚢 Voyage", data.get("voyage", "N/A"))
                st.metric("🏢 Terminal", data.get("terminal", "N/A"))
            
            with col3:
                st.metric("📋 Status", data.get("status", "N/A"))
                if data.get("voyage_confirmed"):
                    st.metric("✅ Voyage Confirmada", "Sim")
                else:
                    st.metric("⚠️ Voyage Confirmada", "Não")
            
            # Mostrar voyages disponíveis
            if data.get("available_voyages"):
                st.info(f"🚢 **Voyages disponíveis para este navio:** {', '.join(data.get('available_voyages', []))}")
            
            # Exibir dados completos em expandir
            with st.expander("📋 Dados Técnicos Completos"):
                st.json(data)
        
        else:
            error_msg = result.get('error', 'Erro desconhecido')
            st.error(f"❌ {error_msg}")
            
            # Se o navio foi encontrado mas não a voyage, mostrar informações úteis
            if result.get("data"):
                data = result.get("data", {})
                st.warning("⚠️ **Navio encontrado, mas voyage específica não disponível**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"🚢 **Navio**: {data.get('vessel_name', 'N/A')}")
                    st.info(f"🏢 **Terminal**: {data.get('terminal', 'N/A')}")
                
                with col2:
                    st.info(f"🚢 **Voyage procurada**: {data.get('voyage', 'N/A')}")
                    if data.get("available_voyages"):
                        st.success(f"🚢 **Voyages disponíveis**: {', '.join(data.get('available_voyages', []))}")
                
                st.info("💡 **Sugestão**: Tente uma das voyages disponíveis listadas acima")
            
            # Verificar outros tipos de erro
            elif result.get("suggestion"):
                st.info(f"💡 **Sugestão**: {result.get('suggestion')}")
            
            if result.get("website_url"):
                st.markdown(f"🌐 **Consulte diretamente no site:** [{result.get('website_url')}]({result.get('website_url')})")
            
            if result.get("status_code") == 404 and not result.get("data"):
                st.info("💡 **Dica**: Verifique se os dados estão corretos ou se a viagem já foi finalizada.")

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
    
    # Carregar dados do banco com cache
    all_ships = load_ships_from_database()
    ship_options = [""] + sorted(all_ships['navio'].unique().tolist()) if not all_ships.empty else [""]
    
    # Mostrar contador de opções
    if len(ship_options) > 1:
        st.info(f"📊 {len(ship_options)-1} navios disponíveis no banco")
    
    # Filtro por carrier para cronograma
    carrier_filter_schedule = st.selectbox(
        "🔍 Filtrar por Carrier (Opcional)",
        ["Todos"] + ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
        key="schedule_carrier_filter",
        help="Filtrar lista de navios por carrier"
    )
    
    # Filtrar navios por carrier se selecionado
    filtered_ship_options_schedule = ship_options
    if carrier_filter_schedule != "Todos" and not all_ships.empty:
        filtered_ships = all_ships[all_ships['carrier'] == carrier_filter_schedule]['navio'].unique()
        filtered_ship_options_schedule = [""] + sorted(filtered_ships.tolist())
        
        if len(filtered_ship_options_schedule) > 1:
            st.success(f"✅ {len(filtered_ship_options_schedule)-1} navios do carrier {carrier_filter_schedule}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        vessel_name = st.selectbox(
            "Nome do Navio",
            filtered_ship_options_schedule,
            key="schedule_vessel",
            help="Selecione um navio da lista filtrada"
        )
        
        # Mostrar informações do navio selecionado
        if vessel_name and not all_ships.empty:
            ship_info = all_ships[all_ships['navio'] == vessel_name]
            if not ship_info.empty:
                ship_data = ship_info.iloc[0]
                st.info(f"🚢 **{vessel_name}**\n"
                       f"Carrier: {ship_data.get('carrier', 'N/A')}\n"
                       f"Terminal: {ship_data.get('terminal', 'N/A')}")
    
    with col2:
        # Detectar carrier automaticamente
        detected_carrier_schedule = ""
        if vessel_name and not all_ships.empty:
            ship_info = all_ships[all_ships['navio'] == vessel_name]
            if not ship_info.empty:
                detected_carrier_schedule = ship_info['carrier'].iloc[0]
        
        carrier = st.selectbox(
            "Carrier",
            ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
            key="schedule_carrier",
            index=(["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"].index(detected_carrier_schedule) 
                   if detected_carrier_schedule in ["", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"] else 0)
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Busca Manual", 
        "📦 Bookings Existentes", 
        "📅 Cronograma de Navios",
        "📊 Dados da API",
        "🔔 Monitoramento"
    ])
    
    with tab1:
        display_voyage_search()
    
    with tab2:
        display_bookings_tracking()
    
    with tab3:
        display_vessel_schedule()
    
    with tab4:
        display_ellox_database_data()
    
    with tab5:
        display_vessel_monitoring()
    
def display_vessel_monitoring():
    """Interface para monitoramento de navios"""
    st.markdown("### 🔔 Terminal - Monitoramento de Navios")
    
    # Carregar dados do banco com cache
    all_ships = load_ships_from_database()
    all_terminals = load_terminals_from_database()
    
    # Preparar opções para selectbox
    ship_options = [""] + sorted(all_ships['navio'].unique().tolist()) if not all_ships.empty else [""]
    terminal_options = [""] + all_terminals['nome'].tolist() if not all_terminals.empty else [""]
    
    # Sub-tabs para diferentes funcionalidades
    subtab1, subtab2 = st.tabs(["📝 Solicitar Monitoramento", "👁️ Visualizar Monitoramento"])
    
    with subtab1:
        st.markdown("#### 📝 Solicitar Monitoramento de Navios")
        
        # Configuração do cliente
        st.markdown("##### 🏢 Configuração do Cliente")
        cnpj_client_raw = st.text_input(
            "CNPJ do Cliente",
            placeholder="00.000.000/0000-00 ou 00000000000000",
            help="CNPJ da empresa que está solicitando o monitoramento (digite apenas números ou formatado)"
        )
        
        # Formatação automática do CNPJ
        cnpj_client = ""
        if cnpj_client_raw:
            cnpj_client = format_cnpj(cnpj_client_raw)
            if cnpj_client != cnpj_client_raw:
                st.info(f"🔄 **CNPJ formatado automaticamente:** `{cnpj_client}`")
            
            if not validate_cnpj_format(cnpj_client):
                st.error("❌ CNPJ deve ter exatamente 14 dígitos")
            else:
                st.success(f"✅ CNPJ válido: `{cnpj_client}`")
        
        # Seção para múltiplas solicitações
        st.markdown("##### 🚢 Navios para Monitoramento")
        
        # Inicializar session state para múltiplas solicitações
        if 'monitoring_requests' not in st.session_state:
            st.session_state.monitoring_requests = []
        
        # Formulário para adicionar nova solicitação
        with st.form("add_monitoring_request"):
            st.markdown("**Adicionar Navio ao Monitoramento**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Filtro por carrier
                carrier_filter = st.selectbox(
                    "🔍 Filtrar por Carrier (Opcional)",
                    ["Todos"] + ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
                    key="monitoring_carrier_filter"
                )
                
                # Filtrar navios por carrier
                filtered_ship_options = ship_options
                if carrier_filter != "Todos" and not all_ships.empty:
                    filtered_ships = all_ships[all_ships['carrier'] == carrier_filter]['navio'].unique()
                    filtered_ship_options = [""] + sorted(filtered_ships.tolist())
                
                vessel_name = st.selectbox(
                    "Nome do Navio",
                    filtered_ship_options,
                    key="monitoring_vessel"
                )
                
                terminal_name = st.selectbox(
                    "Terminal",
                    terminal_options,
                    key="monitoring_terminal"
                )
            
            with col2:
                # Buscar voyages automaticamente quando navio e terminal são selecionados
                available_voyages = []
                if vessel_name and terminal_name and not all_terminals.empty:
                    terminal_info = all_terminals[all_terminals['nome'] == terminal_name]
                    if not terminal_info.empty:
                        terminal_cnpj = terminal_info.iloc[0]['cnpj']
                        
                        # Buscar voyages via API
                        try:
                            client = get_default_api_client()
                            if client.authenticated:
                                from urllib.parse import quote
                                encoded_ship = quote(vessel_name)
                                voyages_response = client._make_api_request(
                                    f"/api/voyages?ship={encoded_ship}&terminal={terminal_cnpj}"
                                )
                                if voyages_response.get("success"):
                                    available_voyages = voyages_response.get("data", [])
                        except:
                            pass
                
                # Campo de texto para voyage
                viagem_navio = st.text_input(
                    "Voyage do Navio",
                    key="monitoring_voyage_text",
                    placeholder="Ex: 044E, MM223A, etc.",
                    help="Digite a voyage do navio"
                )
                
                # Mostrar voyages disponíveis como sugestão (se houver)
                if available_voyages:
                    st.info(f"💡 **Sugestões da API**: {', '.join(available_voyages[:10])}")
                    if len(available_voyages) > 10:
                        st.info(f"... e mais {len(available_voyages) - 10} voyages disponíveis")
            
            # Botão para adicionar à lista
            add_button = st.form_submit_button("➕ Adicionar à Lista de Monitoramento")
            
            if add_button:
                if vessel_name and terminal_name and viagem_navio:
                    # Buscar CNPJ do terminal
                    terminal_info = all_terminals[all_terminals['nome'] == terminal_name]
                    if not terminal_info.empty:
                        cnpj_terminal = terminal_info.iloc[0]['cnpj']
                        
                        new_request = {
                            "cnpj_terminal": cnpj_terminal,
                            "nome_navio": vessel_name,
                            "viagem_navio": viagem_navio,
                            "terminal_name": terminal_name  # Para exibição
                        }
                        
                        # Verificar se já existe
                        exists = any(
                            req["nome_navio"] == vessel_name and 
                            req["viagem_navio"] == viagem_navio and
                            req["cnpj_terminal"] == cnpj_terminal
                            for req in st.session_state.monitoring_requests
                        )
                        
                        if not exists:
                            st.session_state.monitoring_requests.append(new_request)
                            st.success(f"✅ {vessel_name} - {viagem_navio} adicionado!")
                        else:
                            st.warning("⚠️ Esta combinação já está na lista")
                    else:
                        st.error("❌ Terminal não encontrado")
                else:
                    st.error("❌ Preencha todos os campos obrigatórios")
        
        # Mostrar lista atual de solicitações
        if st.session_state.monitoring_requests:
            st.markdown("##### 📋 Lista de Monitoramentos Solicitados")
            
            for i, req in enumerate(st.session_state.monitoring_requests):
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    st.text(f"🚢 {req['nome_navio']}")
                with col2:
                    st.text(f"🏢 {req['terminal_name']}")
                with col3:
                    st.text(f"🚢 {req['viagem_navio']}")
                with col4:
                    if st.button("🗑️", key=f"remove_{i}", help="Remover da lista"):
                        st.session_state.monitoring_requests.pop(i)
                        st.rerun()
            
            # Botões de ação
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🧹 Limpar Lista"):
                    st.session_state.monitoring_requests = []
                    st.rerun()
            
            with col2:
                if st.button("📋 Exportar JSON"):
                    import json
                    json_data = json.dumps(st.session_state.monitoring_requests, indent=2, ensure_ascii=False)
                    st.code(json_data, language="json")
            
            with col3:
                # Botão principal para solicitar monitoramento
                if st.button("🔔 Solicitar Monitoramento", type="primary"):
                    if cnpj_client and st.session_state.monitoring_requests:
                        if not validate_cnpj_format(cnpj_client):
                            st.error("❌ CNPJ deve ter 14 dígitos válidos")
                        else:
                            with st.spinner("Verificando empresa no sistema..."):
                                client = get_default_api_client()
                                
                                if client.authenticated:
                                    # Primeiro verifica se o CNPJ existe no sistema
                                    company_check = client.check_company_exists(cnpj_client)
                                    
                                    if company_check.get("success"):
                                        if company_check.get("exists"):
                                            st.success(f"✅ {company_check.get('message')}")
                                            
                                            # Empresa encontrada, prossegue com a solicitação
                                            with st.spinner("Enviando solicitação de monitoramento..."):
                                                # Preparar dados para API (sem terminal_name)
                                                api_requests = [
                                                    {
                                                        "cnpj_terminal": req["cnpj_terminal"],
                                                        "nome_navio": req["nome_navio"],
                                                        "viagem_navio": req["viagem_navio"]
                                                    }
                                                    for req in st.session_state.monitoring_requests
                                                ]
                                                
                                                result = client.request_vessel_monitoring(cnpj_client, api_requests)
                                                
                                                if result.get("success"):
                                                    st.success("✅ Monitoramento solicitado com sucesso!")
                                                    
                                                    # Mostrar resposta da API
                                                    data = result.get("data", [])
                                                    if data:
                                                        st.markdown("##### 📊 Resposta da API")
                                                        for item in data:
                                                            col1, col2, col3 = st.columns(3)
                                                            with col1:
                                                                st.metric("🚢 Navio", item.get("nome_navio", "N/A"))
                                                            with col2:
                                                                st.metric("🚢 Voyage", item.get("viagem_navio", "N/A"))
                                                            with col3:
                                                                st.metric("🏢 CNPJ Shipowner", item.get("cnpj_shipowner", "N/A"))
                                                    
                                                    # Limpar lista após sucesso
                                                    st.session_state.monitoring_requests = []
                                                    
                                                else:
                                                    st.error(f"❌ Erro no monitoramento: {result.get('error')}")
                                                    if result.get('details'):
                                                        st.code(result.get('details'), language="text")
                                        else:
                                            # Empresa não encontrada
                                            st.error(f"❌ {company_check.get('message')}")
                                            st.info(f"💡 {company_check.get('suggestion', '')}")
                                            
                                            # Mostrar CNPJs válidos como exemplo
                                            st.markdown("##### 🏢 CNPJs de Exemplo (Terminais Cadastrados)")
                                            
                                            # Buscar alguns CNPJs válidos para mostrar como exemplo
                                            try:
                                                terminals_response = client._make_api_request("/api/terminals")
                                                if terminals_response.get("success"):
                                                    terminals = terminals_response.get("data", [])
                                                    if terminals:
                                                        st.markdown("**Exemplos de CNPJs válidos no sistema:**")
                                                        for terminal in terminals[:5]:  # Mostrar apenas os primeiros 5
                                                            terminal_name = terminal.get('nome', 'N/A')
                                                            terminal_cnpj = terminal.get('cnpj', 'N/A')
                                                            st.info(f"🏢 **{terminal_name}**: `{terminal_cnpj}`")
                                            except:
                                                pass
                                    else:
                                        st.error(f"❌ Erro na verificação: {company_check.get('error')}")
                                else:
                                    st.error("❌ Falha na autenticação com a API")
                    else:
                        st.error("❌ Preencha o CNPJ do cliente e adicione pelo menos um navio")
        else:
            st.info("📝 Adicione navios à lista de monitoramento usando o formulário acima")
    
    with subtab2:
        st.markdown("#### 👁️ Visualizar Monitoramento")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cnpj_client_view_raw = st.text_input(
                "CNPJ do Cliente",
                placeholder="00.000.000/0000-00 ou 00000000000000",
                key="view_cnpj_client",
                help="Digite apenas números ou formatado"
            )
            
            # Formatação automática do CNPJ para visualização
            cnpj_client_view = ""
            if cnpj_client_view_raw:
                cnpj_client_view = format_cnpj(cnpj_client_view_raw)
                if cnpj_client_view != cnpj_client_view_raw:
                    st.info(f"🔄 **CNPJ formatado:** `{cnpj_client_view}`")
                
                if not validate_cnpj_format(cnpj_client_view):
                    st.error("❌ CNPJ deve ter 14 dígitos")
                else:
                    st.success(f"✅ CNPJ válido")
            
            # Filtro por carrier
            carrier_filter_view = st.selectbox(
                "🔍 Filtrar por Carrier (Opcional)",
                ["Todos"] + ["HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"],
                key="view_carrier_filter"
            )
            
            # Filtrar navios por carrier
            filtered_ship_options_view = ship_options
            if carrier_filter_view != "Todos" and not all_ships.empty:
                filtered_ships = all_ships[all_ships['carrier'] == carrier_filter_view]['navio'].unique()
                filtered_ship_options_view = [""] + sorted(filtered_ships.tolist())
            
            vessel_name_view = st.selectbox(
                "Nome do Navio",
                filtered_ship_options_view,
                key="view_vessel"
            )
        
        with col2:
            terminal_name_view = st.selectbox(
                "Terminal",
                terminal_options,
                key="view_terminal"
            )
            
            # Buscar voyages automaticamente
            available_voyages_view = []
            if vessel_name_view and terminal_name_view and not all_terminals.empty:
                terminal_info = all_terminals[all_terminals['nome'] == terminal_name_view]
                if not terminal_info.empty:
                    terminal_cnpj = terminal_info.iloc[0]['cnpj']
                    
                    try:
                        client = get_default_api_client()
                        if client.authenticated:
                            from urllib.parse import quote
                            encoded_ship = quote(vessel_name_view)
                            voyages_response = client._make_api_request(
                                f"/api/voyages?ship={encoded_ship}&terminal={terminal_cnpj}"
                            )
                            if voyages_response.get("success"):
                                available_voyages_view = voyages_response.get("data", [])
                    except:
                        pass
            
            # Campo de texto para voyage
            viagem_navio_view = st.text_input(
                "Voyage do Navio",
                key="view_voyage_text",
                placeholder="Ex: 044E, MM223A, etc.",
                help="Digite a voyage do navio"
            )
            
            # Mostrar sugestões da API (se houver)
            if available_voyages_view:
                st.info(f"💡 **Sugestões da API**: {', '.join(available_voyages_view[:10])}")
                if len(available_voyages_view) > 10:
                    st.info(f"... e mais {len(available_voyages_view) - 10} voyages disponíveis")
        
        if st.button("👁️ Consultar Monitoramento"):
            if cnpj_client_view and vessel_name_view and terminal_name_view and viagem_navio_view:
                # Buscar CNPJ do terminal
                terminal_info = all_terminals[all_terminals['nome'] == terminal_name_view]
                if not terminal_info.empty:
                    cnpj_terminal_view = terminal_info.iloc[0]['cnpj']
                    
                    with st.spinner("Consultando monitoramento..."):
                        client = get_default_api_client()
                        
                        if client.authenticated:
                            result = client.view_vessel_monitoring(
                                cnpj_client_view,
                                cnpj_terminal_view,
                                vessel_name_view,
                                viagem_navio_view
                            )
                            
                            if result.get("success"):
                                st.success(f"✅ {result.get('message')}")
                                
                                data = result.get("data", {})
                                if data:
                                    st.markdown("##### 📊 Informações do Monitoramento")
                                    st.json(data)
                                else:
                                    st.info("📋 Monitoramento ativo, mas sem dados detalhados disponíveis")
                            else:
                                st.error(f"❌ {result.get('error')}")
                                if result.get('details'):
                                    st.code(result.get('details'), language="text")
                        else:
                            st.error("❌ Falha na autenticação com a API")
                else:
                    st.error("❌ Terminal não encontrado")
            else:
                st.error("❌ Preencha todos os campos obrigatórios")

    # Footer
    st.markdown("---")
    st.markdown("*Powered by [Ellox API - Comexia](https://developers.comexia.digital/)*")

def display_ellox_database_data():
    """Exibe interface para consultar dados extraídos da API Ellox"""
    st.markdown("### 📊 Dados Extraídos da API Ellox")
    
    try:
        from ellox_data_queries import ElloxDataQueries
        
        queries = ElloxDataQueries()
        
        # Estatísticas gerais
        stats = queries.get_database_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏢 Terminais", stats['terminais'])
        with col2:
            st.metric("🚢 Navios", stats['navios'])
        with col3:
            st.metric("⛵ Voyages", stats['voyages'])
        with col4:
            st.metric("🏪 Carriers", stats['carriers'])
        
        st.info(f"📅 Última atualização: {stats['ultima_atualizacao']}")
        
        # Botão para nova extração
        col_btn1, col_btn2 = st.columns([1, 3])
        with col_btn1:
            if st.button("🔄 Atualizar Dados"):
                with st.spinner("Executando nova extração..."):
                    try:
                        from ellox_data_extractor import ElloxDataExtractor
                        extractor = ElloxDataExtractor()
                        result = extractor.run_full_extraction(ships_sample=30)
                        
                        st.success("✅ Dados atualizados com sucesso!")
                        st.json(result)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Erro na atualização: {str(e)}")
        
        # Sub-tabs para diferentes consultas
        subtab1, subtab2, subtab3 = st.tabs([
            "🔍 Buscar Navios", "🏢 Terminais", "📊 Relatórios"
        ])
        
        with subtab1:
            st.markdown("#### 🔍 Busca de Navios no Banco")
            
            col1, col2 = st.columns(2)
            with col1:
                search_term = st.text_input("Nome do navio:", placeholder="Ex: MAERSK")
            with col2:
                carrier_options = ["Todos", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"]
                selected_carrier = st.selectbox("Carrier:", carrier_options, key="db_carrier")
            
            if search_term:
                results = queries.search_ships(search_term)
                
                if not results.empty:
                    # Filtrar por carrier se selecionado
                    if selected_carrier != "Todos":
                        results = results[results['CARRIER'] == selected_carrier]
                    
                    st.success(f"✅ {len(results)} navios encontrados")
                    st.dataframe(results, use_container_width=True)
                    
                    # Exportar resultados
                    csv = results.to_csv(index=False)
                    st.download_button(
                        label="📥 Baixar CSV",
                        data=csv,
                        file_name=f"navios_{search_term}_{selected_carrier}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ Nenhum navio encontrado")
        
        with subtab2:
            st.markdown("#### 🏢 Terminais e Estatísticas")
            
            # Resumo dos terminais
            terminals_summary = queries.get_terminals_summary()
            st.dataframe(terminals_summary, use_container_width=True)
            
            # Gráfico de navios por terminal
            if not terminals_summary.empty:
                st.markdown("#### 📈 Navios por Terminal")
                top_terminals = terminals_summary.head(10)
                st.bar_chart(top_terminals.set_index('TERMINAL')['TOTAL_NAVIOS'])
        
        with subtab3:
            st.markdown("#### 📊 Relatórios por Carrier")
            
            # Resumo por Carrier
            carriers_summary = queries.get_carriers_summary()
            st.dataframe(carriers_summary, use_container_width=True)
            
            # Gráfico de navios por carrier
            if not carriers_summary.empty:
                st.markdown("#### 📈 Navios por Carrier")
                st.bar_chart(carriers_summary.set_index('CARRIER')['TOTAL_NAVIOS'])
                
                # Exportar relatório completo
                csv = carriers_summary.to_csv(index=False)
                st.download_button(
                    label="📥 Baixar Relatório Completo",
                    data=csv,
                    file_name="relatorio_carriers_ellox.csv",
                    mime="text/csv"
                )
    
    except ImportError:
        st.error("❌ Módulo ellox_data_queries não encontrado")
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {str(e)}")