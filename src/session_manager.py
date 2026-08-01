"""Persistência segura da sessão de autenticação no navegador."""

from __future__ import annotations

import base64
import hashlib
import time

import streamlit as st


AUTH_KEY = "auth_session"
AUTH_COOKIE = "rio_de_una_auth"
AUTH_STORAGE = "rio_de_una_refresh_token"
STORAGE_ATTEMPTS_KEY = "auth_storage_restore_attempts"
MAX_STORAGE_ATTEMPTS = 4
COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _cookie_controller():
    from streamlit_cookies_controller import CookieController

    return CookieController(key="rio_de_una_auth_cookie_controller")


def _local_storage():
    from streamlit_local_storage import LocalStorage

    return LocalStorage()


def _cipher():
    from cryptography.fernet import Fernet

    try:
        configured = str(st.secrets.get("session", {}).get("cookie_secret", "")).strip()
        fallback = str(st.secrets.get("supabase", {}).get("key", "")).strip()
    except Exception:
        configured = ""
        fallback = ""
    secret = configured or fallback or "rio-de-una-local-session"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def save_session(access_token: str, refresh_token: str) -> None:
    """Mantém os tokens na sessão e persiste somente o refresh token criptografado."""
    st.session_state[AUTH_KEY] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
    st.session_state[STORAGE_ATTEMPTS_KEY] = MAX_STORAGE_ATTEMPTS
    encrypted = _cipher().encrypt(refresh_token.encode("utf-8")).decode("ascii")
    try:
        _local_storage().setItem(AUTH_STORAGE, encrypted)
    except Exception:
        pass
    try:
        secure = str(getattr(st.context, "url", "")).startswith("https://")
        _cookie_controller().set(
            AUTH_COOKIE,
            encrypted,
            max_age=COOKIE_MAX_AGE,
            secure=secure,
            same_site="lax",
        )
    except Exception:
        pass


def get_saved_refresh_token() -> str | None:
    """Lê e descriptografa a sessão persistente do navegador, quando existir."""
    encrypted = None
    try:
        encrypted = _local_storage().getItem(
            AUTH_STORAGE, key="rio_de_una_restore_refresh_token"
        )
    except Exception:
        pass

    if not encrypted:
        attempts = int(st.session_state.get(STORAGE_ATTEMPTS_KEY, 0))
        if attempts < MAX_STORAGE_ATTEMPTS:
            st.session_state[STORAGE_ATTEMPTS_KEY] = attempts + 1
            time.sleep(0.35)
            st.rerun()

    try:
        encrypted = encrypted or _cookie_controller().get(AUTH_COOKIE)
        if not encrypted:
            return None
        return _cipher().decrypt(str(encrypted).encode("ascii")).decode("utf-8")
    except Exception:
        clear_session()
        return None


def clear_session() -> None:
    """Remove a sessão da memória, do armazenamento local e dos cookies."""
    st.session_state.pop(AUTH_KEY, None)
    st.session_state.pop(STORAGE_ATTEMPTS_KEY, None)
    try:
        _local_storage().deleteItem(AUTH_STORAGE)
    except Exception:
        pass
    try:
        _cookie_controller().remove(AUTH_COOKIE)
    except Exception:
        pass
