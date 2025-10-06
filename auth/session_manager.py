"""
Gerenciador de sessões usando cookies HTTP seguros com JWT
"""
import streamlit as st
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os
from auth.jwt_manager import create_jwt_token, verify_jwt_token
from auth.cookie_manager import set_auth_cookie, get_auth_cookie, clear_auth_cookie
from auth.auth_db import get_user_by_id

def initialize_session_from_cookie() -> bool:
    """
    Tenta restaurar sessão a partir do cookie JWT.
    
    Returns:
        bool: True se sessão foi restaurada com sucesso
    """
    # Se já está logado no session_state, não precisa fazer nada
    if st.session_state.get('current_user'):
        return True
    
    # Tentar ler cookie
    token = get_auth_cookie()
    if not token:
        return False
    
    # Validar JWT
    payload = verify_jwt_token(token)
    if not payload:
        # Token inválido/expirado, limpar cookie
        clear_auth_cookie()
        return False
    
    # Buscar dados completos do usuário no banco
    user_data = get_user_by_id(payload['user_id'])
    if not user_data:
        clear_auth_cookie()
        return False
    
    # Restaurar session_state
    st.session_state.current_user = user_data['username']
    st.session_state.user_data = user_data
    # Usar o tempo de criação do JWT (tempo real do login)
    st.session_state.login_time = datetime.fromtimestamp(payload['iat'])
    
    return True

def create_session(user_data: dict):
    """
    Cria uma nova sessão: gera JWT e salva em cookie.
    
    Args:
        user_data: Dados do usuário autenticado
    """
    # Gerar JWT
    token = create_jwt_token(user_data)
    
    # Salvar em cookie
    set_auth_cookie(token)
    
    # Salvar no session_state
    st.session_state.current_user = user_data['username']
    st.session_state.user_data = user_data
    st.session_state.login_time = datetime.now()

def cleanup_expired_sessions():
    """
    Remove arquivos de sessão expirados (> 8 horas).
    Deve ser chamada no startup da aplicação.
    """
    sessions_dir = Path(".streamlit/sessions")
    if not sessions_dir.exists():
        return
    
    now = datetime.now()
    expired_count = 0
    
    for session_file in sessions_dir.glob("session_*.json"):
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Verificar se sessão está expirada
            expires_at = datetime.fromisoformat(session_data.get('expires_at', ''))
            if now > expires_at:
                session_file.unlink()
                expired_count += 1
        except Exception as e:
            # Se não conseguir ler, deletar arquivo corrompido
            try:
                session_file.unlink()
                expired_count += 1
                print(f"[SESSION_CLEANUP] Arquivo corrompido removido: {session_file}")
            except Exception as e2:
                print(f"[SESSION_CLEANUP] Erro ao remover arquivo corrompido {session_file}: {e2}")
    
    if expired_count > 0:
        print(f"[SESSION_CLEANUP] Removidas {expired_count} sessões expiradas")

def destroy_session():
    """
    Destroi a sessão: limpa arquivo, cookie e session_state.
    """
    # Obter token da sessão atual
    session_token = st.session_state.get('session_token')
    
    # Deletar arquivo da sessão
    if session_token:
        session_file = Path(f".streamlit/sessions/session_{session_token}.json")
        if session_file.exists():
            try:
                session_file.unlink()
                print(f"[SESSION_CLEANUP] Arquivo de sessão removido: {session_file}")
            except Exception as e:
                print(f"[SESSION_CLEANUP] Erro ao remover arquivo de sessão: {e}")
    
    # Limpar cookie
    clear_auth_cookie()
    
    # Limpar session_state
    keys_to_clear = ['current_user', 'user_data', 'login_time', 'force_password_change', 'session_token']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# Funções de compatibilidade (mantidas para não quebrar código existente)
def is_session_valid(session_data: Dict[str, Any]) -> bool:
    """Função de compatibilidade - sempre retorna True para cookies"""
    return True

def get_session(token: str) -> Optional[Dict[str, Any]]:
    """Função de compatibilidade - não usada com cookies"""
    return None

def delete_session(token: str) -> bool:
    """Função de compatibilidade - chama destroy_session"""
    destroy_session()
    return True

def update_session_activity(token: str) -> bool:
    """Função de compatibilidade - não necessária com cookies"""
    return True

def find_active_session_for_user(username: str) -> Optional[Dict[str, Any]]:
    """Função de compatibilidade - não usada com cookies"""
    return None

def validate_session_security(token: str) -> tuple[bool, str]:
    """Função de compatibilidade - não usada com cookies"""
    return True, "Sessão válida"

def validate_session_ownership(token: str) -> bool:
    """Função de compatibilidade - não usada com cookies"""
    return True

def get_session_time_remaining() -> str:
    """
    Calcula tempo restante da sessão.
    
    Returns:
        str: Tempo restante formatado (ex: "3h 45m")
    """
    if not st.session_state.get('login_time'):
        return "0h 0m"
    
    login_time = st.session_state['login_time']
    if isinstance(login_time, str):
        login_time = datetime.fromisoformat(login_time)
    
    elapsed = datetime.now() - login_time
    remaining_seconds = max(0, 4 * 3600 - elapsed.total_seconds())  # 4 horas
    
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    
    return f"{hours}h {minutes}m"

def format_session_time(time_str: str) -> str:
    """
    Formata o tempo de sessão para exibição.
    
    Args:
        time_str: String de tempo (ex: "3h 45m")
    
    Returns:
        str: Tempo formatado com ícone
    """
    if time_str == "0h 0m":
        return "⏰ Sessão: Expirada"
    
    # Determinar ícone baseado no tempo restante
    hours = int(time_str.split('h')[0])
    if hours >= 3:
        icon = "✅"
    elif hours >= 1:
        icon = "⚠️"
    else:
        icon = "🔴"
    
    return f"{icon} Sessão: {time_str}"