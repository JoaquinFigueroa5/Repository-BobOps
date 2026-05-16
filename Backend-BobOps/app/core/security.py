"""
security.py — Helpers de seguridad.

Nota: La autenticación principal usa Supabase Auth (JWKS RS256).
Este módulo queda como utilidad para operaciones auxiliares.
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)