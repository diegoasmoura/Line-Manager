import streamlit as st
from ellox_api import get_default_api_client, ElloxAPI # Import ElloxAPI class for direct use
from app_config import ELLOX_API_CONFIG, PROXY_CONFIG # Import config for default values
from datetime import datetime # NEW
import os # NEW
import requests # NEW

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

    # Definir abas (preparado para futuras expansões)
    tab1 = st.tabs(["Gerenciamento de Credenciais"])

    with tab1[0]:
        st.info("As credenciais salvas aqui são usadas para autenticar com a API Ellox e o Proxy corporativo. As alterações são temporárias para esta sessão.")

        col_general_conn, col_api_conn = st.columns(2)

        with col_general_conn:
            st.subheader("Conexão Geral (Internet/Proxy)")
            general_result = st.session_state.general_connection_result
            if general_result["success"]:
                st.success(f"Online ✅ ({general_result.get('response_time', 0.0):.2f}s)")
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
                st.rerun()

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

    print("⚙️ Setup") # Keep the original print for now, can remove later if not needed