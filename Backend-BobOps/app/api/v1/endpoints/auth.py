"""
api/v1/endpoints/auth.py

Endpoints de autenticación usando Supabase Auth como identity provider.
El frontend puede usar supabase-js directamente; estos endpoints
sirven como puente server-side y para validación de sesiones.
"""

import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.analysis import User
from app.schemas.item import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _supabase_request(
    path: str,
    data: dict,
    params: dict | None = None,
    api_key: str | None = None,
) -> dict:
    url = f"{settings.SUPABASE_URL}/auth/v1/{path}"
    key = api_key or settings.SUPABASE_ANON_KEY
    logger.debug("Supabase Auth: url=%s, key_len=%d", url, len(key))
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {key}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(url, headers=headers, json=data, params=params)
        if resp.status_code >= 400:
            try:
                error_body = resp.json()
                detail = (
                    error_body.get("message")
                    or error_body.get("error_description")
                    or error_body.get("error")
                    or error_body.get("msg")
                    or resp.text
                )
            except Exception:
                detail = resp.text
            raise HTTPException(
                status_code=resp.status_code,
                detail=detail,
            )
        return resp.json()


async def _admin_create_user(email: str, password: str) -> dict:
    logger.info("Creating user via Admin API: %s", email)
    return await _supabase_request(
        "admin/users",
        {
            "email": email,
            "password": password,
            "email_confirm": True,
        },
        api_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Registra un nuevo usuario via Supabase Auth.
    Reintenta hasta 3 veces si hay rate limit (429).
    Si se agotan los reintentos, crea el usuario via Admin API (service_role).
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            data = await _supabase_request("signup", {
                "email": body.email,
                "password": body.password,
            })
        except HTTPException as e:
            if e.status_code == 429:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.info(
                        "Signup rate limited, retrying in %ds (attempt %d/%d): %s",
                        wait, attempt + 1, max_retries, body.email,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.info(
                    "Signup rate limited after %d retries, using Admin API: %s",
                    max_retries, body.email,
                )
                data = await _admin_create_user(body.email, body.password)
                break
            raise

        if "access_token" in data:
            return TokenResponse(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
            )

        user_id = data.get("id")
        if user_id:
            await db.execute(
                text("UPDATE auth.users SET email_confirmed_at = NOW() WHERE id = :uid"),
                {"uid": user_id},
            )
            await db.commit()
        break

    login_data = await _supabase_request(
        "token",
        {"email": body.email, "password": body.password},
        params={"grant_type": "password"},
    )
    return TokenResponse(
        access_token=login_data["access_token"],
        refresh_token=login_data["refresh_token"],
        expires_in=login_data["expires_in"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Login con email y password via Supabase Auth.
    """
    data = await _supabase_request(
        "token",
        {"email": body.email, "password": body.password},
        params={"grant_type": "password"},
    )

    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """
    Refresca el access_token usando el refresh_token.
    """
    data = await _supabase_request(
        "token",
        {"refresh_token": body.refresh_token},
        params={"grant_type": "refresh_token"},
    )

    return TokenResponse(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data["expires_in"],
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retorna la información del usuario autenticado.
    Protegido: requiere JWT válido en Authorization header.
    """
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )
