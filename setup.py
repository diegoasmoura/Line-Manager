import streamlit as st
from ellox_api import get_default_api_client, ElloxAPI # Import ElloxAPI class for direct use
from app_config import ELLOX_API_CONFIG, PROXY_CONFIG # Import config for default values
from datetime import datetime, timedelta # NEW
import os # NEW
import requests # NEW
import pandas as pd # NEW
import traceback # NEW
import time # NEW
from auth.login import has_access_level, get_current_user # NEW
from auth.auth_db import ( # NEW
    list_users, create_user, update_user, 
    reset_user_password, get_business_units,
    check_username_exists, check_email_exists
)
from ellox_sync_functions import get_sync_config, update_sync_config, get_sync_statistics, get_sync_logs

def exibir_setup():
    st.title("⚙️ Configurações do Sistema Farol")

    # NEW: Function to test general internet/proxy connection
    def test_general_connection():
        with st.spinner(st.session_state.get('general_connection_message', 'Testando conexão geral...')):
            try:
                # Initialize variables to None to ensure they exist in all code paths
                original_http_proxy = None
                original_https_proxy = None

                proxies = {}
                # Check if proxy credentials are set in session state
                if (st.session_state.proxy_host and st.session_state.proxy_port and
                    st.session_state.proxy_username and st.session_state.proxy_password):
                    
                    proxy_url = f"http://{st.session_state.proxy_username}:{st.session_state.proxy_password}@{st.session_state.proxy_host}:{st.session_state.proxy_port}"
                    proxies = {
                        "http": proxy_url,
                        "https": proxy_url,
                    }
                    st.session_state.general_connection_message = "Testando conexão via proxy..."
                else:
                    st.session_state.general_connection_message = "Testando conexão direta (sem proxy)..."
                    # Ensure no proxy environment variables interfere if not set by the app
                    # Temporarily clear proxy env vars for this request
                    original_http_proxy = os.environ.get('http_proxy')
                    original_https_proxy = os.environ.get('https_proxy')
                    if 'http_proxy' in os.environ: del os.environ['http_proxy']
                    if 'https_proxy' in os.environ: del os.environ['https_proxy']

                response = requests.get("https://www.google.com", timeout=10, proxies=proxies)

                # Restore original proxy env vars if they existed
                if original_http_proxy: os.environ['http_proxy'] = original_http_proxy
                if original_https_proxy: os.environ['https_proxy'] = original_https_proxy

                if response.status_code == 200:
                    st.session_state.general_connection_result = {
                        "success": True,
                        "message": f"Conexão bem-sucedida (Status: {response.status_code})",
                        "response_time": response.elapsed.total_seconds()
                    }
                else:
                    st.session_state.general_connection_result = {
                        "success": False,
                        "message": f"Falha na conexão (Status: {response.status_code})",
                        "error": f"HTTP Status Code: {response.status_code}"
                    }
            except requests.exceptions.ProxyError as e:
                st.session_state.general_connection_result = {
                    "success": False,
                    "message": "Falha na conexão via proxy",
                    "error": str(e)
                }
            except requests.exceptions.RequestException as e:
                st.session_state.general_connection_result = {
                    "success": False,
                    "message": "Falha na conexão geral",
                    "error": str(e)
                }
            st.session_state.general_connection_last_validated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Initialize session state for credentials if not already present
    if 'api_email' not in st.session_state:
        st.session_state.api_email = ELLOX_API_CONFIG.get("email", "")
    if 'api_password' not in st.session_state:
        st.session_state.api_password = ELLOX_API_CONFIG.get("password", "")
    if 'api_base_url' not in st.session_state:
        st.session_state.api_base_url = ELLOX_API_CONFIG.get("base_url", "https://apidtz.comexia.digital")
    # NEW: Initialize last validated time
    if 'api_last_validated' not in st.session_state:
        st.session_state.api_last_validated = "Nunca validado"

    # Initialize session state for proxy credentials
    if 'proxy_username' not in st.session_state:
        st.session_state.proxy_username = PROXY_CONFIG.get("username", "")
    if 'proxy_password' not in st.session_state:
        st.session_state.proxy_password = PROXY_CONFIG.get("password", "")
    if 'proxy_host' not in st.session_state:
        st.session_state.proxy_host = PROXY_CONFIG.get("host", "")
    if 'proxy_port' not in st.session_state:
        st.session_state.proxy_port = PROXY_CONFIG.get("port", "")

    # NEW: Initialize session state for general connection test
    if 'general_connection_result' not in st.session_state:
        st.session_state.general_connection_result = {"success": False, "message": "Nunca testado"}
    if 'general_connection_last_validated' not in st.session_state:
        st.session_state.general_connection_last_validated = "Nunca validado"
    if 'general_connection_message' not in st.session_state:
        st.session_state.general_connection_message = "Testando conexão geral..."

    # Function to test connection and update session state for Ellox API
    def test_api_connection():
        with st.spinner("Testando conexão com a API Ellox..."):
            # Create a client with current session state credentials
            client = ElloxAPI(
                email=st.session_state.api_email,
                password=st.session_state.api_password,
                base_url=st.session_state.api_base_url
            )
            connection_result = client.test_connection()
            
            # Ensure 'message' key is always present
            if "message" not in connection_result:
                if connection_result.get("success"):
                    connection_result["message"] = "Conexão bem-sucedida"
                else:
                    connection_result["message"] = connection_result.get("error", "Erro desconhecido")
            
            st.session_state.api_connection_result = connection_result
            st.session_state.api_last_validated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Initialize session state for API connection test result
    if 'api_connection_result' not in st.session_state:
        st.session_state.api_connection_result = {"success": False, "message": "Nunca testado"}

    # Run test on first load or if explicitly requested
    if st.session_state.api_connection_result == {"success": False, "message": "Nunca testado"}:
        test_api_connection()

    # Define as abas disponíveis com base no nível de acesso
    if has_access_level('ADMIN'):
        tab_names = ["Gerenciamento de Credenciais", "Administração de Usuários", "Sincronização Automática"]
    else:
        tab_names = ["Gerenciamento de Credenciais"]

    # Usa st.radio para criar uma navegação que persiste o estado entre recarregamentos
    selected_tab = st.radio(
        "Navegação",
        tab_names,
        key='setup_tab_selection', # Chave para manter o estado
        horizontal=True,
        label_visibility="collapsed"
    )

    # Renderiza o conteúdo da aba selecionada
    if selected_tab == "Gerenciamento de Credenciais":
        st.info("As credenciais salvas aqui são usadas para autenticar com a API Ellox e o Proxy corporativo. As alterações são temporárias para esta sessão.")

        col_general_conn, col_api_conn = st.columns(2)

        with col_general_conn:
            st.subheader("Conexão Geral (Internet/Proxy)")
            general_result = st.session_state.general_connection_result
            api_result = st.session_state.api_connection_result
            
            # Se a API Ellox está funcionando, considerar a conexão geral como OK também
            if api_result.get("success", False):
                st.success(f"Online ✅ (via API Ellox)")
                st.caption(f"Último teste: {st.session_state.api_last_validated}")
            elif general_result["success"]:
                st.success(f"Online ✅ ({general_result.get('response_time', 0.0):.2f}s)")
                st.caption(f"Último teste: {st.session_state.general_connection_last_validated}")
            else:
                st.error(f"Offline ❌: {general_result.get('error', 'Erro desconhecido')}")
                st.caption(f"Último teste: {st.session_state.general_connection_last_validated}")
            
            if st.button("Testar Conexão Geral", key="test_general_conn_card_btn"):
                test_general_connection()

        with col_api_conn:
            st.subheader("Conexão API Ellox")
            api_result = st.session_state.api_connection_result
            if api_result["success"]:
                st.success(f"Online ✅ ({api_result.get('response_time', 0.0):.2f}s)")
            else:
                st.error(f"Offline ❌: {api_result.get('error', 'Erro desconhecido')}")
            st.caption(f"Último teste: {st.session_state.api_last_validated}")
            if st.button("Testar Conexão API Ellox", key="test_api_conn_card_btn"):
                test_api_connection()
                # Não precisa de rerun - a conexão já foi testada e atualizada

        st.markdown("---") # Separator

        # --- Ellox API Credentials Section ---
        with st.form("api_credentials_form_individual"): # NEW: Separate form for API credentials
            with st.expander("Credenciais da API Ellox", expanded=False):
                email_input = st.text_input("Email da API Ellox", value=st.session_state.api_email, key="email_input")
                password_input = st.text_input("Senha da API Ellox", value=st.session_state.api_password, type="password", key="password_input")
                base_url_input = st.text_input("URL Base da API Ellox", value=st.session_state.api_base_url, key="base_url_input")
                submitted_api = st.form_submit_button("Salvar Credenciais da API Ellox") # MOVED INSIDE EXPANDER
            
            if submitted_api:
                st.session_state.api_email = email_input
                st.session_state.api_password = password_input
                st.session_state.api_base_url = base_url_input
                # Trigger re-test of API connection after saving credentials
                test_api_connection()
                st.session_state.api_save_message = "✅ Credenciais da API Ellox salvas para a sessão atual!"

        if 'api_save_message' in st.session_state:
            st.success(st.session_state.api_save_message)

        # --- Proxy Credentials Section ---
        with st.form("proxy_credentials_form_individual"): # NEW: Separate form for Proxy credentials
            with st.expander("Credenciais do Proxy Corporativo", expanded=False):
                proxy_username_input = st.text_input("Usuário do Proxy", value=st.session_state.proxy_username, key="proxy_username_input")
                proxy_password_input = st.text_input("Senha do Proxy", value=st.session_state.proxy_password, type="password", key="proxy_password_input")
                col_proxy_host, col_proxy_port = st.columns(2)
                with col_proxy_host:
                    proxy_host_input = st.text_input("Host do Proxy", value=st.session_state.proxy_host, key="proxy_host_input")
                with col_proxy_port:
                    proxy_port_input = st.text_input("Porta do Proxy", value=st.session_state.proxy_port, key="proxy_port_input")
                submitted_proxy = st.form_submit_button("Salvar Credenciais do Proxy") # MOVED INSIDE EXPANDER
            
            if submitted_proxy:
                st.session_state.proxy_username = proxy_username_input
                st.session_state.proxy_password = proxy_password_input
                st.session_state.proxy_host = proxy_host_input
                st.session_state.proxy_port = proxy_port_input

                if st.session_state.proxy_username and st.session_state.proxy_password and st.session_state.proxy_host and st.session_state.proxy_port:
                    proxy_url = f"http://{st.session_state.proxy_username}:{st.session_state.proxy_password}@{st.session_state.proxy_host}:{st.session_state.proxy_port}"
                    os.environ['http_proxy'] = proxy_url
                    os.environ['HTTP_PROXY'] = proxy_url
                    os.environ['https_proxy'] = proxy_url
                    os.environ['HTTPS_PROXY'] = proxy_url
                    st.session_state.proxy_save_message = "✅ Credenciais do Proxy aplicadas ao ambiente da sessão."
                else:
                    for var in ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']:
                        if var in os.environ:
                            del os.environ[var]
                    st.session_state.proxy_save_message = "⚠️ Credenciais do Proxy incompletas ou removidas. Proxy desativado para a sessão."

                if 'api_connection_result' in st.session_state:
                    del st.session_state.api_connection_result

        if 'proxy_save_message' in st.session_state:
            if "✅" in st.session_state.proxy_save_message:
                st.success(st.session_state.proxy_save_message)
            else:
                st.warning(st.session_state.proxy_save_message)

    elif selected_tab == "Administração de Usuários" and has_access_level('ADMIN'):
        show_user_administration()
    
    elif selected_tab == "Sincronização Automática" and has_access_level('ADMIN'):
        # Sub-abas para Sincronização
        sync_sub_tabs = st.tabs(["⚙️ Configuração", "📊 Logs de Sincronização"])
        
        with sync_sub_tabs[0]:
            show_sync_configuration()
        
        with sync_sub_tabs[1]:
            show_sync_logs()

    print("⚙️ Setup") # Keep the original print for now, can remove later if not needed

def show_user_administration():
    """Exibe interface de administração de usuários"""
    st.header("👥 Administração de Usuários")

    # Exibir mensagem de sucesso de ações (create, update, reset)
    if st.session_state.get('user_admin_message'):
        st.success(st.session_state.pop('user_admin_message')) # Exibe e remove a mensagem
        st.balloons()
    
    # Verificar se houve atualização e limpar cache se necessário
    if st.session_state.get('user_list_updated', False):
        st.cache_data.clear()
        st.session_state['user_list_updated'] = False
    
    st.markdown("---")
    
    # Cards com métricas
    users = list_users()
    total_users = len(users)
    active_users = len([u for u in users if u['is_active'] == 1])
    inactive_users = total_users - active_users
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de DSID", total_users)
    with col2:
        st.metric("DSID Ativos", active_users, delta=f"{inactive_users} inativos")
    with col3:
        admin_count = len([u for u in users if u['access_level'] == 'ADMIN'])
        st.metric("Administradores", admin_count)
    with col4:
        edit_count = len([u for u in users if u['access_level'] == 'EDIT'])
        st.metric("Editores", edit_count)
    
    st.markdown("---")
    
    # Inicializa o estado da aba se não existir
    if 'user_admin_tab_index' not in st.session_state:
        st.session_state.user_admin_tab_index = 0
    
    # Define as opções de navegação
    tab_options = [
        "📋 Listar Usuário",
        "➕ Novo Usuário", 
        "✏️ Editar Usuário",
        "🔑 Reset de Senha"
    ]
    
    # Cria o radio horizontal com configurações otimizadas
    selected_tab = st.radio(
        "Navegação",
        options=tab_options,
        index=st.session_state.user_admin_tab_index,
        key='user_admin_tab_radio',
        label_visibility='collapsed',
        horizontal=True,
        # Configurações para evitar cliques duplos
        help=None,
        disabled=False,
        # Força a atualização do estado
        on_change=lambda: None
    )
    
    # Atualiza o índice da aba selecionada
    new_index = tab_options.index(selected_tab)
    if new_index != st.session_state.user_admin_tab_index:
        st.session_state.user_admin_tab_index = new_index
        st.rerun()
    
    st.markdown("---")
    
    # Renderiza o conteúdo baseado na aba selecionada
    if st.session_state.user_admin_tab_index == 0:
        show_user_list(users)
    elif st.session_state.user_admin_tab_index == 1:
        show_create_user_form()
    elif st.session_state.user_admin_tab_index == 2:
        show_edit_user_form(users)
    else:
        show_reset_password_form(users)

def show_user_list(users):
    """Lista todos os usuários em tabela formatada"""
    st.subheader("DSID Cadastrados")
    
    if not users:
        st.info("Nenhum DSID cadastrado.")
        return
    
    # Converter para DataFrame
    df = pd.DataFrame(users)
    
    # Formatar colunas
    df['is_active'] = df['is_active'].apply(lambda x: '✅ Ativo' if x == 1 else '❌ Inativo')
    df['access_level'] = df['access_level'].replace({
        'VIEW': '👁️ Visualização',
        'EDIT': '✏️ Edição',
        'ADMIN': '⚙️ Administrador'
    })
    df['business_unit'] = df['business_unit'].fillna('Todas')
    
    # Renomear colunas para exibição
    df = df.rename(columns={
        'username': 'DSID',
        'full_name': 'Nome Completo',
        'email': 'Email',
        'business_unit': 'Unidade de Negócio',
        'access_level': 'Nível de Acesso',
        'is_active': 'Status',
        'last_login': 'Último Login'
    })
    
    # Exibir tabela
    st.dataframe(
        df[['DSID', 'Nome Completo', 'Email', 'Unidade de Negócio', 
            'Nível de Acesso', 'Status', 'Último Login']],
        use_container_width=True,
        hide_index=True
    )

def show_create_user_form():
    """Formulário de criação de usuário"""
    st.subheader("Criar Novo DSID")
    
    business_units = get_business_units()
    unit_options = ['Todas'] + [u['UNIT_NAME'] for u in business_units]
    
    # Usar key dinâmico para forçar recriação do formulário quando necessário
    form_counter = st.session_state.get('form_counter', 0)
    form_key = f"create_user_form_{form_counter}"
    
    with st.form(form_key):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input("DSID*", placeholder="D510098", 
                                   help="Identificador corporativo (DSID)", key=f"create_username_{form_counter}")
            email = st.text_input("Email*", placeholder="name_sobrenome@cargil.com", key=f"create_email_{form_counter}")
            full_name = st.text_input("Nome Completo*", placeholder="Nome Sobrenome", key=f"create_full_name_{form_counter}")
        
        with col2:
            password = st.text_input("Senha Inicial*", type="password",
                                   help="O usuário DSID será solicitado a trocar no primeiro login", key=f"create_password_{form_counter}")
            
            business_unit = st.selectbox("Unidade de Negócio", options=unit_options)
            
            access_level = st.selectbox(
                "Nível de Acesso*",
                options=['VIEW', 'EDIT', 'ADMIN'],
                format_func=lambda x: {'VIEW': '👁️ Visualização', 'EDIT': '✏️ Edição', 'ADMIN': '⚙️ Administrador'}[x]
            )
        
        st.markdown("**Obs:** O DSID será forçado a trocar a senha no primeiro login.")
        
        if st.form_submit_button("➕ Criar DSID", use_container_width=True):
            if not all([username, email, password, full_name]):
                st.error("❌ Preencha todos os campos obrigatórios (*)")
            elif len(password) < 6:
                st.error("❌ A senha deve ter no mínimo 6 caracteres")
            elif check_username_exists(username):
                st.error("❌ DSID já existe. Escolha outro.")
            elif check_email_exists(email):
                st.error("❌ Email já existe. Escolha outro.")
            else:
                # Converter business_unit
                bu_value = None if business_unit == 'Todas' else next(
                    (u['UNIT_CODE'] for u in business_units if u['UNIT_NAME'] == business_unit), None
                )
                
                if create_user(username, email, password, full_name, bu_value, 
                             access_level, get_current_user()):
                    # SUCESSO: Incrementar contador para limpar o formulário e definir flags.
                    st.session_state['form_counter'] = st.session_state.get('form_counter', 0) + 1
                    st.session_state['user_list_updated'] = True
                    st.session_state['user_admin_message'] = f"✅ DSID '{username}' criado com sucesso!"
                    st.rerun() # Força o recarregamento para exibir o feedback e atualizar a UI
                else:
                    # ERRO: NÃO incrementa contador, para manter os dados do formulário para correção.
                    st.error("❌ Erro ao criar DSID. Tente novamente.")

def show_edit_user_form(users):
    """Formulário de edição de usuário"""
    st.subheader("Editar DSID")
    
    if not users:
        st.info("Nenhum DSID para editar.")
        return
    
    business_units = get_business_units()
    unit_options = ['Todas'] + [u['UNIT_NAME'] for u in business_units]
    
    # Seleção de usuário
    user_to_edit = st.selectbox(
        "Selecione o Usuário",
        options=[u['username'] for u in users],
        format_func=lambda x: f"{x} - {next(u['full_name'] for u in users if u['username'] == x)}"
    )
    
    if user_to_edit:
        user_data = next(u for u in users if u['username'] == user_to_edit)
        
        with st.form("edit_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.text_input("DSID (não editável)", value=user_data['username'], disabled=True)
                email = st.text_input("Email", value=user_data['email'])
                full_name = st.text_input("Nome Completo", value=user_data['full_name'])
            
            with col2:
                business_unit_display = user_data.get('business_unit') or 'Todas'
                business_unit_idx = unit_options.index(business_unit_display) if business_unit_display in unit_options else 0
                
                business_unit = st.selectbox(
                    "Unidade de Negócio",
                    options=unit_options,
                    index=business_unit_idx
                )
                
                access_level = st.selectbox(
                    "Nível de Acesso",
                    options=['VIEW', 'EDIT', 'ADMIN'],
                    format_func=lambda x: {'VIEW': '👁️ Visualização', 'EDIT': '✏️ Edição', 'ADMIN': '⚙️ Administrador'}[x],
                    index=['VIEW', 'EDIT', 'ADMIN'].index(user_data['access_level'])
                )
                
                is_active = st.selectbox(
                    "Status",
                    options=[1, 0],
                    format_func=lambda x: '✅ Ativo' if x == 1 else '❌ Inativo',
                    index=0 if user_data['is_active'] == 1 else 1
                )
            
            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                # Converter business_unit
                bu_value = None if business_unit == 'Todas' else next(
                    (u['UNIT_CODE'] for u in business_units if u['UNIT_NAME'] == business_unit), None
                )
                
                if update_user(
                    user_data['user_id'], email, full_name, bu_value,
                    access_level, is_active, get_current_user()
                ):
                    st.session_state['user_list_updated'] = True
                    st.session_state['user_admin_message'] = "✅ DSID atualizado com sucesso!"
                    st.rerun() # Força o recarregamento para exibir o feedback e atualizar a UI
                else:
                    st.error("❌ Erro ao atualizar DSID. Tente novamente.")

def show_reset_password_form(users):
    """Formulário de reset de senha"""
    st.subheader("Reset de Senha (Usuário)")
    
    if not users:
        st.info("Nenhum DSID para resetar senha.")
        return
    
    with st.form("reset_password_form"):
        user_to_reset = st.selectbox(
            "Selecione o Usuário",
            options=[u['username'] for u in users],
            format_func=lambda x: f"{x} - {next(u['full_name'] for u in users if u['username'] == x)}"
        )
        
        new_password = st.text_input("Nova Senha", type="password")
        confirm_password = st.text_input("Confirmar Nova Senha", type="password")
        
        st.markdown("**Obs:** O DSID será forçado a trocar a senha no próximo login.")
        
        if st.form_submit_button("🔑 Resetar Senha", use_container_width=True):
            if not new_password or not confirm_password:
                st.error("❌ Preencha todos os campos")
            elif new_password != confirm_password:
                st.error("❌ As senhas não coincidem")
            elif len(new_password) < 6:
                st.error("❌ A senha deve ter no mínimo 6 caracteres")
            else:
                user_data = next(u for u in users if u['username'] == user_to_reset)
                
                if reset_user_password(user_data['user_id'], new_password, get_current_user()):
                    st.session_state['user_list_updated'] = True
                    st.session_state['user_admin_message'] = f"✅ Senha do DSID '{user_to_reset}' resetada com sucesso!"
                    st.rerun() # Força o recarregamento para exibir o feedback e atualizar a UI
                else:
                    st.error("❌ Erro ao resetar senha do DSID. Tente novamente.")


def show_sync_configuration():
    """Exibe interface de configuração da sincronização automática Ellox"""
    st.header("🔄 Sincronização Automática Ellox API")
    st.markdown("Configure a sincronização automática de dados de viagens com a API Ellox.")
    st.markdown("---")
    
    try:
        # Carregar configuração atual
        config = get_sync_config()
        
        # Cards de status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_icon = "✅" if config['enabled'] else "❌"
            status_text = "Ativa" if config['enabled'] else "Inativa"
            st.metric("Status", f"{status_icon} {status_text}")
        
        with col2:
            interval_text = f"{config['interval_minutes']} min"
            if config['interval_minutes'] >= 60:
                hours = config['interval_minutes'] // 60
                minutes = config['interval_minutes'] % 60
                if minutes == 0:
                    interval_text = f"{hours}h"
                else:
                    interval_text = f"{hours}h {minutes}min"
            st.metric("Intervalo", interval_text)
        
        with col3:
            last_exec = config.get('last_execution')
            if last_exec:
                st.metric("Última Execução", last_exec.strftime("%d/%m %H:%M"))
            else:
                st.metric("Última Execução", "Nunca")
        
        st.markdown("---")
        
        # Formulário de configuração
        st.subheader("⚙️ Configurações")
        
        with st.form("sync_config_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                enabled = st.checkbox(
                    "Ativar sincronização automática",
                    value=config['enabled'],
                    help="Quando ativado, o sistema sincronizará automaticamente os dados de viagens com a API Ellox"
                )
            
            with col2:
                interval_options = [
                    (30, "30 minutos"),
                    (60, "1 hora"),
                    (120, "2 horas"),
                    (240, "4 horas"),
                    (480, "8 horas")
                ]
                
                current_interval = config['interval_minutes']
                interval_index = next((i for i, (val, _) in enumerate(interval_options) if val == current_interval), 1)
                
                interval_minutes = st.selectbox(
                    "Intervalo de sincronização",
                    options=[val for val, _ in interval_options],
                    format_func=lambda x: next(label for val, label in interval_options if val == x),
                    index=interval_index,
                    help="Frequência com que o sistema verificará por atualizações na API Ellox"
                )
            
            # Informações adicionais
            st.info("""
            **Como funciona:**
            - O sistema consulta a API Ellox no intervalo configurado
            - Apenas viagens sem data de chegada ao destino final são monitoradas
            - Mudanças detectadas são salvas automaticamente no histórico
            - Logs detalhados estão disponíveis na aba Tracking
            """)
            
            if st.form_submit_button("💾 Salvar Configuração", type="primary"):
                try:
                    # Atualizar configuração
                    update_sync_config(
                        enabled=enabled,
                        interval_minutes=interval_minutes,
                        updated_by=get_current_user()
                    )
                    
                    st.success("✅ Configuração salva com sucesso!")
                    st.balloons()
                    
                    # Não usar rerun - deixar o usuário ver a mensagem de sucesso
                    # A configuração já foi salva e será refletida na próxima interação
                    
                except Exception as e:
                    st.error(f"❌ Erro ao salvar configuração: {str(e)}")
        
        st.markdown("---")
        
        # Estatísticas
        st.subheader("📊 Estatísticas (Últimos 30 dias)")
        
        try:
            stats = get_sync_statistics(days=30)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Total de Execuções",
                    f"{stats['total_executions']:,}",
                    help="Número total de sincronizações executadas"
                )
            
            with col2:
                st.metric(
                    "Taxa de Sucesso",
                    f"{stats['success_rate']:.1f}%",
                    help="Percentual de execuções bem-sucedidas"
                )
            
            with col3:
                st.metric(
                    "Viagens Ativas",
                    f"{stats['active_voyages']:,}",
                    help="Viagens sendo monitoradas atualmente"
                )
            
            with col4:
                avg_time = stats['avg_execution_time_ms']
                st.metric(
                    "Tempo Médio",
                    f"{avg_time:.0f}ms",
                    help="Tempo médio de execução por sincronização"
                )
            
            # Resumo detalhado
            st.subheader("📋 Resumo Detalhado")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Execuções por Status:**")
                st.write(f"✅ Sucessos: {stats['successful_executions']}")
                st.write(f"ℹ️ Sem mudanças: {stats['no_changes_executions']}")
                st.write(f"❌ Erros: {stats['error_executions']}")
            
            with col2:
                st.write("**Mudanças Detectadas:**")
                st.write(f"📊 Total: {stats['total_changes_detected']}")
                if stats['total_executions'] > 0:
                    avg_changes = stats['total_changes_detected'] / stats['total_executions']
                    st.write(f"📈 Média por execução: {avg_changes:.1f}")
        
        except Exception as e:
            st.warning(f"⚠️ Não foi possível carregar estatísticas: {str(e)}")
        
        st.markdown("---")
        
        # Ações manuais
        st.subheader("🔧 Ações Manuais")
        
        if st.button("🔄 Executar Sincronização Agora", help="Força uma sincronização imediata"):
            with st.spinner("Executando sincronização..."):
                try:
                    from ellox_sync_service import sync_all_active_voyages
                    result = sync_all_active_voyages()
                    
                    st.success("✅ Sincronização executada com sucesso!")
                    st.json(result)
                    
                except Exception as e:
                    st.error(f"❌ Erro na sincronização: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar configuração de sincronização: {str(e)}")
        st.error("Verifique se as tabelas de sincronização foram criadas corretamente.")


def show_sync_logs():
    """
    Exibe logs de sincronização automática Ellox.
    """
    st.header("📊 Logs de Sincronização Automática Ellox")
    st.markdown("Visualize e analise os logs de execução da sincronização automática com a API Ellox.")
    st.markdown("---")
    
    try:
        # Estatísticas gerais
        with st.spinner("Carregando estatísticas..."):
            stats = get_sync_statistics(days=30)
        
        # Cards de métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📊 Total de Execuções (30d)",
                value=f"{stats['total_executions']:,}",
                delta=None
            )
        
        with col2:
            st.metric(
                label="✅ Taxa de Sucesso",
                value=f"{stats['success_rate']:.1f}%",
                delta=None
            )
        
        with col3:
            st.metric(
                label="🚢 Viagens Ativas",
                value=f"{stats['active_voyages']:,}",
                delta=None
            )
        
        with col4:
            avg_time = stats['avg_execution_time_ms']
            st.metric(
                label="⏱️ Tempo Médio",
                value=f"{avg_time:.0f}ms",
                delta=None
            )
        
        st.divider()
        
        # Filtros
        st.subheader("🔍 Filtros")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            period = st.selectbox(
                "Período",
                options=["7 dias", "30 dias", "90 dias"],
                index=1
            )
            days = int(period.split()[0])
        
        with col2:
            status_filter = st.selectbox(
                "Status",
                options=["Todos", "SUCCESS", "NO_CHANGES", "API_ERROR", "AUTH_ERROR", "SAVE_ERROR", "ERROR"],
                index=0
            )
        
        with col3:
            vessel_filter = st.text_input("Navio (opcional)", placeholder="Digite parte do nome...")
        
        with col4:
            terminal_filter = st.text_input("Terminal (opcional)", placeholder="Digite parte do nome...")
        
        # Aplicar filtros
        filters = {}
        if days:
            filters['start_date'] = datetime.now() - timedelta(days=days)
        if status_filter != "Todos":
            filters['status'] = status_filter
        if vessel_filter:
            filters['vessel'] = vessel_filter
        if terminal_filter:
            filters['terminal'] = terminal_filter
        
        # Buscar logs
        with st.spinner("Carregando logs..."):
            logs = get_sync_logs(filters=filters, limit=1000)
        
        if not logs:
            st.info("Nenhum log encontrado para os filtros selecionados.")
            return
        
        # Converter para DataFrame
        df_logs = pd.DataFrame(logs)
        
        # Formatar colunas
        if not df_logs.empty:
            df_logs['sync_timestamp'] = pd.to_datetime(df_logs['sync_timestamp'])
            df_logs['execution_time_ms'] = df_logs['execution_time_ms'].round(2)
            
            # Mapear status para ícones
            status_icons = {
                'SUCCESS': '✅',
                'NO_CHANGES': 'ℹ️',
                'API_ERROR': '🔴',
                'AUTH_ERROR': '🔐',
                'SAVE_ERROR': '💾',
                'ERROR': '❌',
                'RETRY': '🔄'
            }
            
            df_logs['status_icon'] = df_logs['status'].map(status_icons).fillna('❓')
            df_logs['status_display'] = df_logs['status_icon'] + ' ' + df_logs['status']
        
        # Exibir tabela
        st.subheader(f"📋 Logs de Sincronização ({len(df_logs)} registros)")
        
        # Configurar colunas para exibição
        display_columns = {
            'sync_timestamp': 'Data/Hora',
            'vessel_name': 'Navio',
            'voyage_code': 'Viagem',
            'terminal': 'Terminal',
            'status_display': 'Status',
            'changes_detected': 'Mudanças',
            'execution_time_ms': 'Tempo (ms)',
            'retry_attempt': 'Tentativa',
            'error_message': 'Erro'
        }
        
        # Filtrar colunas que existem no DataFrame
        available_columns = {k: v for k, v in display_columns.items() if k in df_logs.columns}
        
        # Exibir tabela
        st.dataframe(
            df_logs[list(available_columns.keys())].rename(columns=available_columns),
            use_container_width=True,
            hide_index=True
        )
        
        # Botão de export
        if st.button("📥 Exportar CSV"):
            csv = df_logs.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"sync_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Resumo por status
        if not df_logs.empty:
            st.subheader("📊 Resumo por Status")
            status_summary = df_logs['status'].value_counts()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(status_summary)
            
            with col2:
                for status, count in status_summary.items():
                    icon = status_icons.get(status, '❓')
                    percentage = (count / len(df_logs)) * 100
                    st.write(f"{icon} **{status}**: {count} ({percentage:.1f}%)")
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar logs de sincronização: {str(e)}")
        st.error(f"Detalhes: {traceback.format_exc()}")