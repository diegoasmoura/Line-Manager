"""
Sistema de gerenciamento de sessões com cache do Streamlit
"""
import streamlit as st
import uuid
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Configurações
SESSION_TIMEOUT = 14400  # 4 horas em segundos
SESSIONS_DIR = ".streamlit/sessions"  # Diretório para sessões persistentes

@st.cache_data(ttl=SESSION_TIMEOUT, persist="disk")
def _store_session_data(token: str, session_data: Dict[str, Any]) -> bool:
    """
    Armazena dados da sessão no cache do Streamlit com persistência em disco.
    Esta função é cached para persistir entre refreshes e reinicializações.
    """
    return True

def _ensure_sessions_dir():
    """Garante que o diretório de sessões existe"""
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR, exist_ok=True)

def _get_session_file_path(token: str) -> str:
    """Retorna o caminho do arquivo de sessão"""
    return os.path.join(SESSIONS_DIR, f"session_{token}.json")

def _save_session_to_file(token: str, session_data: Dict[str, Any]) -> bool:
    """Salva sessão em arquivo JSON"""
    try:
        _ensure_sessions_dir()
        file_path = _get_session_file_path(token)
        
        # Converter datetime para string para serialização JSON
        serializable_data = session_data.copy()
        for key, value in serializable_data.items():
            if isinstance(value, datetime):
                serializable_data[key] = value.isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar sessão em arquivo: {e}")
        return False

def _load_session_from_file(token: str) -> Optional[Dict[str, Any]]:
    """Carrega sessão de arquivo JSON"""
    try:
        file_path = _get_session_file_path(token)
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Converter strings de volta para datetime
        for key, value in data.items():
            if isinstance(value, str) and key in ['created_at', 'expires_at', 'last_activity']:
                try:
                    data[key] = datetime.fromisoformat(value)
                except:
                    pass
        
        return data
    except Exception as e:
        print(f"Erro ao carregar sessão de arquivo: {e}")
        return None

def _delete_session_file(token: str) -> bool:
    """Remove arquivo de sessão"""
    try:
        file_path = _get_session_file_path(token)
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception as e:
        print(f"Erro ao deletar arquivo de sessão: {e}")
        return False

def generate_session_token() -> str:
    """Gera um token único para a sessão"""
    return str(uuid.uuid4())

def create_session(username: str, user_data: dict) -> str:
    """
    Cria uma nova sessão no cache e retorna o token.
    
    Args:
        username: Nome do usuário
        user_data: Dados do usuário (vindos do authenticate_user)
    
    Returns:
        str: Token da sessão
    """
    token = generate_session_token()
    now = datetime.now()
    
    session_data = {
        "username": username,
        "user_data": user_data,
        "created_at": now,
        "expires_at": now + timedelta(seconds=SESSION_TIMEOUT),
        "last_activity": now
    }
    
    # Armazenar no cache com persistência em disco
    _store_session_data(token, session_data)
    
    # Armazenar no session_state como backup imediato
    cache_key = f"session_{token}"
    st.session_state[cache_key] = session_data
    
    # Salvar em arquivo para persistência entre reinicializações
    _save_session_to_file(token, session_data)
    
    return token

def find_active_session_for_user(username: str) -> Optional[Dict[str, Any]]:
    """
    Busca uma sessão ativa para um usuário específico.
    Útil quando o session_token foi perdido mas sabemos o username.
    
    Args:
        username: Nome do usuário
    
    Returns:
        Dict com dados da sessão ou None se não encontrada
    """
    try:
        _ensure_sessions_dir()
        sessions_dir = SESSIONS_DIR
        
        if not os.path.exists(sessions_dir):
            return None
        
        # Buscar todos os arquivos de sessão
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
                    
                    # Verificar se é do usuário correto e se está válida
                    if (data.get('username') == username and 
                        is_session_valid(data)):
                        return data
                        
                except Exception as e:
                    print(f"Erro ao ler arquivo de sessão {filename}: {e}")
                    continue
        
        return None
        
    except Exception as e:
        print(f"Erro ao buscar sessão ativa: {e}")
        return None

def get_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Recupera dados da sessão do cache se válida.
    Tenta múltiplas fontes para maior robustez.
    
    Args:
        token: Token da sessão
    
    Returns:
        Dict com dados da sessão ou None se inválida/expirada
    """
    if not token:
        return None
    
    try:
        cache_key = f"session_{token}"
        
        # 1. Primeiro, tentar recuperar do session_state (mais rápido)
        if cache_key in st.session_state:
            session_data = st.session_state[cache_key]
            
            # Verificar se a sessão não expirou
            if is_session_valid(session_data):
                # Atualizar última atividade
                session_data["last_activity"] = datetime.now()
                st.session_state[cache_key] = session_data
                # Atualizar arquivo também
                _save_session_to_file(token, session_data)
                return session_data
            else:
                # Sessão expirada, remover
                del st.session_state[cache_key]
                _delete_session_file(token)
                return None
        
        # 2. Se não encontrou no session_state, tentar do arquivo
        session_data = _load_session_from_file(token)
        if session_data and is_session_valid(session_data):
            # Restaurar no session_state
            st.session_state[cache_key] = session_data
            # Atualizar última atividade
            session_data["last_activity"] = datetime.now()
            st.session_state[cache_key] = session_data
            _save_session_to_file(token, session_data)
            return session_data
        elif session_data:
            # Sessão expirada, limpar arquivo
            _delete_session_file(token)
        
        return None
        
    except Exception as e:
        print(f"Erro ao recuperar sessão: {e}")
        return None

def delete_session(token: str) -> bool:
    """
    Remove a sessão do cache e arquivo.
    
    Args:
        token: Token da sessão
    
    Returns:
        bool: True se removida com sucesso
    """
    if not token:
        return False
    
    try:
        # Remover do session_state
        cache_key = f"session_{token}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]
        
        # Remover arquivo
        _delete_session_file(token)
        
        return True
    except Exception as e:
        print(f"Erro ao deletar sessão: {e}")
        return False

def is_session_valid(session_data: Dict[str, Any]) -> bool:
    """
    Verifica se a sessão ainda é válida (não expirou).
    
    Args:
        session_data: Dados da sessão
    
    Returns:
        bool: True se válida, False se expirada
    """
    if not session_data:
        return False
    
    try:
        expires_at = session_data.get("expires_at")
        if not expires_at:
            return False
        
        # Verificar se não expirou
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return datetime.now() < expires_at
        
    except Exception as e:
        print(f"Erro ao verificar validade da sessão: {e}")
        return False

def update_session_activity(token: str) -> bool:
    """
    Atualiza a última atividade da sessão.
    
    Args:
        token: Token da sessão
    
    Returns:
        bool: True se atualizada com sucesso
    """
    if not token:
        return False
    
    try:
        cache_key = f"session_{token}"
        if cache_key in st.session_state:
            session_data = st.session_state[cache_key]
            session_data["last_activity"] = datetime.now()
            st.session_state[cache_key] = session_data
            return True
        return False
    except Exception as e:
        print(f"Erro ao atualizar atividade da sessão: {e}")
        return False

def get_session_time_remaining(session_data: Dict[str, Any]) -> Optional[timedelta]:
    """
    Retorna o tempo restante da sessão.
    
    Args:
        session_data: Dados da sessão
    
    Returns:
        timedelta com tempo restante ou None se inválida
    """
    if not session_data or not is_session_valid(session_data):
        return None
    
    try:
        expires_at = session_data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        remaining = expires_at - datetime.now()
        return remaining if remaining.total_seconds() > 0 else None
        
    except Exception as e:
        print(f"Erro ao calcular tempo restante: {e}")
        return None

def format_session_time(remaining: timedelta) -> str:
    """
    Formata o tempo restante da sessão para exibição.
    
    Args:
        remaining: Tempo restante
    
    Returns:
        str: Tempo formatado (ex: "2h 30m" ou "45m")
    """
    if not remaining:
        return "Expirada"
    
    total_seconds = int(remaining.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
