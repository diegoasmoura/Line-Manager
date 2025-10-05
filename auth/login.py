"""
Sistema de login mínimo para o Farol
"""
import streamlit as st
import hashlib
import os
from datetime import datetime, timedelta

# Usuários hardcoded para desenvolvimento (em produção, usar banco de dados)
USERS = {
    "admin": "admin123",  # senha: admin123
    "user1": "user123",   # senha: user123
    "diego": "diego123",  # senha: diego123
}

def hash_password(password: str) -> str:
    """Hash simples da senha (em produção, usar bcrypt ou similar)"""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(username: str, password: str) -> bool:
    """Autentica usuário com credenciais"""
    if username in USERS and USERS[username] == password:
        return True
    return False

def show_login_form():
    """Exibe formulário de login com layout aprimorado."""
    svg_icon = """<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24"><path fill="currentColor" d="M12 16q-1.671 0-2.835-1.164Q8 13.67 8 12t1.165-2.835T12 8t2.836 1.165T16 12t-1.164 2.836T12 16m-7-3.5H1.5v-1H5zm17.5 0H19v-1h3.5zM11.5 5V1.5h1V5zm0 17.5V19h1v3.5zM6.746 7.404l-2.16-2.098l.695-.745l2.111 2.135zM18.72 19.439l-2.117-2.141l.652-.702l2.16 2.098zM16.596 6.745l2.098-2.16l.745.695l-2.135 2.111zM4.562 18.72l2.14-2.117l.664.652l-2.08 2.179z"/></svg>"""
    st.markdown(f"<h1 style='text-align: center;'>{svg_icon} Login - Sistema Farol</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # Centraliza o formulário
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        with st.form("login_form"):
            st.markdown("<h3 style='text-align: center;'>Acesso ao Sistema</h3>", unsafe_allow_html=True)

            username = st.text_input(
                "👤 **Usuário**",
                placeholder="Digite seu usuário",
                help="Usuários disponíveis: admin, user1, diego"
            )

            password = st.text_input(
                "🔑 **Senha**",
                type="password",
                placeholder="Digite sua senha",
                help="Senhas: admin123, user123, diego123"
            )

            st.markdown("<br>", unsafe_allow_html=True)  # Espaçador

            login_button = st.form_submit_button(
                "🚀 Entrar",
                use_container_width=True
            )

            if login_button:
                if not username or not password:
                    st.error("❌ Por favor, preencha usuário e senha")
                elif authenticate_user(username, password):
                    st.session_state.current_user = username
                    st.session_state.login_time = datetime.now()
                    st.success(f"✅ Login bem-sucedido! Bem-vindo, {username}")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos")
        
        # Informações de desenvolvimento
        with st.expander("ℹ️ Informações para Desenvolvimento"):
            st.markdown("""
            **Usuários de teste:**
            - `admin` / `admin123`
            - `user1` / `user123` 
            - `diego` / `diego123`
            
            **Nota:** Este é um sistema de login básico para desenvolvimento. 
            Em produção, implementar autenticação segura com hash de senhas e banco de dados.
            """)

def logout():
    """Realiza logout do usuário"""
    if 'current_user' in st.session_state:
        del st.session_state.current_user
    if 'login_time' in st.session_state:
        del st.session_state.login_time
    st.rerun()

def get_current_user() -> str:
    """Retorna o usuário logado atual"""
    return st.session_state.get("current_user", None)

def is_logged_in() -> bool:
    """Verifica se há usuário logado"""
    return get_current_user() is not None

def get_user_info() -> dict:
    """Retorna informações do usuário logado"""
    if not is_logged_in():
        return {}
    
    return {
        "username": get_current_user(),
        "login_time": st.session_state.get("login_time"),
        "session_duration": datetime.now() - st.session_state.get("login_time", datetime.now())
    }
