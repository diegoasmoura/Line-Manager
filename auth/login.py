"""
Sistema de login com banco de dados Oracle e bcrypt
"""
import streamlit as st
from datetime import datetime
from auth.auth_db import authenticate_user
from auth.session_manager import create_session, get_session, delete_session, update_session_activity, find_active_session_for_user, is_session_valid

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
                "Entrar",
                use_container_width=True
            )

            if login_button:
                if not username or not password:
                    st.error("❌ Por favor, preencha usuário e senha")
                else:
                    user_data = authenticate_user(username, password)
                    
                    if user_data:
                        # Criar sessão persistente
                        session_token = create_session(user_data['username'], user_data)
                        
                        # Armazenar dados do usuário na sessão (compatibilidade)
                        st.session_state.current_user = user_data['username']
                        st.session_state.user_data = user_data
                        st.session_state.login_time = datetime.now()
                        st.session_state.session_token = session_token
                        
                        # Verificar se precisa trocar senha
                        if user_data.get('password_reset_required') == 1:
                            st.session_state.force_password_change = True
                        
                        st.success(f"✅ Login bem-sucedido! Bem-vindo, {user_data['full_name']}")
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos, ou usuário inativo")
        
        # Informações de desenvolvimento
        with st.expander("ℹ️ Informações para Desenvolvimento"):
            st.markdown("""
            **Usuário administrador padrão:**
            - `admin` / `Admin@2025`
            
            **Nota:** Sistema de autenticação seguro com banco de dados Oracle e hash bcrypt.
            Acesse Setup > Administração de Usuários para gerenciar usuários.
            """)

def restore_session_if_exists() -> bool:
    """
    Tenta restaurar uma sessão existente do cache.
    
    Returns:
        bool: True se restaurou com sucesso, False caso contrário
    """
    try:
        # 1. Primeiro, tentar com token de sessão (se existir)
        session_token = st.session_state.get('session_token')
        if session_token:
            session_data = get_session(session_token)
            if session_data:
                # Restaurar dados da sessão
                st.session_state.current_user = session_data['username']
                st.session_state.user_data = session_data['user_data']
                st.session_state.login_time = session_data['created_at']
                
                # Atualizar atividade da sessão
                update_session_activity(session_token)
                return True
            else:
                # Sessão não encontrada ou expirada, limpar token
                st.session_state.pop('session_token', None)
        
        # 2. Se não encontrou com token, tentar buscar por sessões ativas
        # (útil quando o session_token foi perdido mas há sessões válidas)
        try:
            # Buscar por sessões ativas (assumindo que pode haver uma sessão ativa)
            # Como não sabemos o username, vamos tentar buscar qualquer sessão válida
            import os
            import json
            from datetime import datetime
            
            sessions_dir = ".streamlit/sessions"
            if os.path.exists(sessions_dir):
                for filename in os.listdir(sessions_dir):
                    if filename.startswith("session_") and filename.endswith(".json"):
                        file_path = os.path.join(sessions_dir, filename)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            
                            # Converter strings de volta para datetime
                            for key, value in data.items():
                                if isinstance(value, str) and key in ['created_at', 'expires_at', 'last_activity']:
                                    try:
                                        data[key] = datetime.fromisoformat(value)
                                    except:
                                        pass
                            
                            # Verificar se está válida
                            if is_session_valid(data):
                                # Restaurar dados da sessão
                                st.session_state.current_user = data['username']
                                st.session_state.user_data = data['user_data']
                                st.session_state.login_time = data['created_at']
                                
                                # Extrair token do filename
                                token = filename.replace("session_", "").replace(".json", "")
                                st.session_state.session_token = token
                                
                                # Atualizar atividade da sessão
                                update_session_activity(token)
                                return True
                                
                        except Exception as e:
                            print(f"Erro ao ler arquivo de sessão {filename}: {e}")
                            continue
        except Exception as e:
            print(f"Erro ao buscar sessões ativas: {e}")
        
        return False
        
    except Exception as e:
        print(f"Erro ao restaurar sessão: {e}")
        # Limpar token em caso de erro
        st.session_state.pop('session_token', None)
        return False

def logout():
    """Realiza logout do usuário"""
    # Deletar sessão do cache
    session_token = st.session_state.get('session_token')
    if session_token:
        delete_session(session_token)
    
    # Limpar sessão
    keys_to_clear = ['current_user', 'user_data', 'login_time', 'force_password_change', 'session_token']
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    
    st.rerun()

def get_current_user() -> str:
    """Retorna o usuário logado atual"""
    return st.session_state.get("current_user", None)

def is_logged_in() -> bool:
    """Verifica se há usuário logado"""
    return get_current_user() is not None

def has_access_level(required_level: str) -> bool:
    """
    Verifica se usuário tem nível de acesso necessário.
    Níveis: VIEW < EDIT < ADMIN
    """
    if not is_logged_in():
        return False
    
    user_data = st.session_state.get('user_data', {})
    current_level = user_data.get('access_level', 'VIEW')
    
    levels = {'VIEW': 1, 'EDIT': 2, 'ADMIN': 3}
    
    return levels.get(current_level, 0) >= levels.get(required_level, 0)

def get_user_info() -> dict:
    """Retorna informações do usuário logado"""
    if not is_logged_in():
        return {}
    
    user_data = st.session_state.get('user_data', {})
    
    return {
        "username": get_current_user(),
        "full_name": user_data.get('full_name', ''),
        "email": user_data.get('email', ''),
        "business_unit": user_data.get('business_unit', 'Todas'),
        "access_level": user_data.get('access_level', 'VIEW'),
        "login_time": st.session_state.get("login_time"),
        "session_duration": datetime.now() - st.session_state.get("login_time", datetime.now())
    }
