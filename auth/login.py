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
    st.markdown("<h1 style='text-align: center;'>🔐 Login - Sistema Farol</h1>", unsafe_allow_html=True)
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
