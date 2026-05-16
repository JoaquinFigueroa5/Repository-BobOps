"""
auth.py — Dependencias de autenticación para FastAPI.

Valida JWTs emitidos por Supabase Auth usando JWKS asimétricos (RS256).
Provee get_current_user() como dependencia para proteger rutas.
"""

import time
import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.crud.todo import get_or_create_user, get_user_by_id
from app.models.analysis import User

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_cache: tuple[dict | None, float] = (None, 0.0)

SUPABASE_URL = "https://atyinelljklmiowkmyhe.supabase.co"
SUPABASE_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1"


async def get_jwks() -> dict:
    global _jwks_cache
    cached_keys, cached_time = _jwks_cache
    if cached_keys and time.time() - cached_time < 3600:
        return cached_keys
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(SUPABASE_JWKS_URL)
            resp.raise_for_status()
            _jwks_cache = (resp.json(), time.time())
            return _jwks_cache[0]
    except Exception as e:
        logger.error("Error fetching JWKS: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify authentication keys",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        jwks = await get_jwks()
        key_alg = jwks["keys"][0].get("alg", "RS256")
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[key_alg],
            issuer=SUPABASE_ISSUER,
            audience="authenticated",
        )
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_uid = payload.get("sub")
    email = payload.get("email", "")

    if not supabase_uid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub)",
        )

    user = await get_or_create_user(db, supabase_uid, email)
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
