"""
Gerenciador de tokens JWT para autenticação segura
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os

# Chave secreta (deve vir de variável de ambiente em produção)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "farol_super_secret_key_2024_very_secure_256_bits")
ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 8

def create_jwt_token(user_data: dict) -> str:
    """
    Cria um JWT token para o usuário.
    
    Args:
        user_data: Dados do usuário (deve conter user_id, username, access_level)
    
    Returns:
        str: Token JWT assinado
    """
    payload = {
        "user_id": user_data['user_id'],
        "username": user_data['username'],
        "access_level": user_data['access_level'],
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str) -> Optional[Dict]:
    """
    Verifica e decodifica um JWT token.
    
    Args:
        token: Token JWT a ser verificado
    
    Returns:
        Dict com dados do payload se válido, None se inválido
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
