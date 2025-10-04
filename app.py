import streamlit as st
 
# Primeira linha: configurar a página
st.set_page_config(page_title="Farol", layout="wide")

# Importar sistema de login
from auth.login import show_login_form, is_logged_in, get_user_info, logout
 
from streamlit_option_menu import option_menu 
import shipments
# import booking_adjustments  # Funcionalidade movida para history.py
import operation_control
import performance_control
import tracking
import setup
 
# Ícone SVG personalizado (Farol)
svg_lighthouse = """
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
<path fill="currentColor" d="M12 15q1.25 0 2.125-.875T15 12t-.875-2.125T12 9t-2.125.875T9 12t.875 2.125T12 15m0 1q-1.671 0-2.835-1.164Q8 13.67 8 12t1.165-2.835T12 8t2.836 1.165T16 12t-1.164 2.836T12 16m-7-3.5H1.5v-1H5zm17.5 0H19v-1h3.5zM11.5 5V1.5h1V5zm0 17.5V19h1V3.5zM6.746 7.404l-2.16-2.098l.695-.745l2.111 2.135zM18.72 19.439l-2.117-2.141l.652-.702l2.16 2.098zM16.596 6.745l2.098-2.16l.745.695l-2.135 2.111zM4.562 18.72l2.14-2.117l.664.652l-2.08 2.179zM12 12"/>
</svg>
"""

# Guard de login - verificar se usuário está logado
if not is_logged_in():
    show_login_form()
    st.stop()  # Para a execução se não estiver logado

# Inicializa o estado do menu se não existir
if "menu_choice" not in st.session_state:
    st.session_state.menu_choice = "Shipments"

# Verifica se há uma solicitação de navegação programática
if "navigate_to" in st.session_state:
    st.session_state.menu_choice = st.session_state["navigate_to"]
    del st.session_state["navigate_to"]  # Remove após usar

# Redireciona "History" para "Shipments" (opção removida do menu)
if st.session_state.menu_choice == "History":
    st.session_state.menu_choice = "Shipments"
    # Força limpeza de cache do Streamlit
    st.cache_data.clear()

# Sidebar personalizada com SVG
with st.sidebar:
    st.markdown(f"""
    <h2 style="display: flex; align-items: center; gap: 10px;">
    {svg_lighthouse} Farol
    </h2>
    """, unsafe_allow_html=True)
    
    # Informações do usuário logado
    user_info = get_user_info()
    if user_info:
        st.markdown("---")
        st.markdown(f"**👤 Usuário:** {user_info['username']}")
        if user_info.get('login_time'):
            duration = user_info['session_duration']
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            st.markdown(f"**⏱️ Sessão:** {int(hours)}h {int(minutes)}m")
        
        # Botão de logout
        if st.button("🚪 Logout", use_container_width=True):
            logout()
 
    # Lista de opções (History removido - acessível via Shipments)
    options = ["Shipments", "Op. Control", "Performance", "Tracking", "Setup"]
    
    # Encontra o índice da opção atual
    current_index = options.index(st.session_state.menu_choice) if st.session_state.menu_choice in options else 0
    
    # Menu lateral com ícones
    choice = option_menu(
        None,
        options,
        icons=["truck", "clipboard-data", "bar-chart", "geo-alt", "gear"],  # Removido ícone "sliders" do Adjustments
        menu_icon="menu",
        default_index=current_index,
        key="main_menu",  # Chave estável para evitar remount e flicker
        styles={
            "container": {"padding": "0!important", "background-color": "#f8f9fa"},
            "icon": {"color": "#2c3f43", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "left", "margin": "5px"},
            "nav-link-selected": {"background-color": "#007681", "color": "white"},
        }
    )
    
    # Atualiza o estado do menu se houve mudança
    if choice != st.session_state.menu_choice:
        st.session_state.menu_choice = choice
        # Reset do estado quando muda de menu
        if choice == "Shipments":
            # Limpa estados específicos do Shipments para voltar à primeira tela
            for key in ["shipments_data", "original_data", "changes", "grid_update_key"]:
                if key in st.session_state:
                    del st.session_state[key]
            # Força reset para primeira página (main = tela principal do shipments)
            st.session_state["current_page"] = "main"

# Usa o estado do menu para determinar qual página exibir
if st.session_state.menu_choice == "Shipments":
    shipments.main()
elif st.session_state.menu_choice == "Op. Control":
    operation_control.exibir_operation_control()
elif st.session_state.menu_choice == "Performance":
    performance_control.exibir_performance_control()
elif st.session_state.menu_choice == "Tracking":
    tracking.exibir_tracking()
elif st.session_state.menu_choice == "Setup":
    setup.exibir_setup()
 