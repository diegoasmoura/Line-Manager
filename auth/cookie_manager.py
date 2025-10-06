"""
Gerenciador de cookies HTTP para persistência de sessão
"""
import streamlit as st
import streamlit.components.v1 as components

def set_auth_cookie(token: str):
    """
    Injeta JavaScript para salvar o token em um cookie HTTP seguro.
    
    Args:
        token: Token JWT a ser armazenado no cookie
    """
    # Cookie com flags de segurança
    js_code = f"""
    <script>
        // Salvar token em cookie seguro
        document.cookie = "farol_auth_token={token}; path=/; max-age=14400; SameSite=Strict; Secure";
        console.log("Cookie de autenticação definido");
        
        // Redirecionar para limpar query params
        const url = new URL(window.location);
        url.searchParams.delete('auth_token');
        if (window.location.search !== url.search) {{
            window.location.href = url.href;
        }}
    </script>
    """
    components.html(js_code, height=0)

def get_auth_cookie() -> str:
    """
    Injeta JavaScript para ler o cookie de autenticação.
    
    Returns:
        str: Token do cookie ou string vazia se não existir
    """
    js_code = """
    <script>
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return '';
        }
        
        const token = getCookie('farol_auth_token');
        if (token) {
            // Redirecionar com token como query param para o Python ler
            const url = new URL(window.location);
            if (!url.searchParams.has('auth_token')) {
                url.searchParams.set('auth_token', token);
                window.location.href = url.href;
            }
        }
    </script>
    """
    components.html(js_code, height=0)
    
    # Ler do query param (o JavaScript redireciona com o token)
    query_params = st.query_params
    return query_params.get("auth_token", "")

def clear_auth_cookie():
    """
    Injeta JavaScript para remover o cookie de autenticação.
    """
    js_code = """
    <script>
        // Remover cookie
        document.cookie = "farol_auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC; SameSite=Strict; Secure";
        console.log("Cookie de autenticação removido");
        
        // Limpar query params
        const url = new URL(window.location);
        url.searchParams.delete('auth_token');
        window.location.href = url.href;
    </script>
    """
    components.html(js_code, height=0)
