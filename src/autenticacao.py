from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow


ESCOPOS = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _config_oauth() -> dict:
    if "google_oauth" not in st.secrets:
        raise ValueError("Configure [google_oauth] no arquivo .streamlit/secrets.toml.")
    config = dict(st.secrets["google_oauth"])
    obrigatorios = ["client_id", "client_secret", "redirect_uri", "state_secret"]
    faltantes = [campo for campo in obrigatorios if not config.get(campo)]
    if faltantes:
        raise ValueError("Configuração OAuth incompleta: " + ", ".join(faltantes))
    return config


def _emails_permitidos() -> set[str]:
    if "access" not in st.secrets:
        return set()
    return {str(email).strip().lower() for email in st.secrets["access"].get("allowed_emails", [])}


def _flow(config: dict, state: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [config["redirect_uri"]],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=ESCOPOS,
        state=state,
        redirect_uri=config["redirect_uri"],
    )


def _novo_estado(config: dict) -> str:
    mensagem = f"{int(time.time())}.{secrets.token_urlsafe(24)}"
    assinatura = hmac.new(
        config["state_secret"].encode(), mensagem.encode(), hashlib.sha256
    ).digest()
    return f"{mensagem}.{base64.urlsafe_b64encode(assinatura).decode().rstrip('=')}"


def _estado_valido(config: dict, estado: str) -> bool:
    try:
        timestamp, aleatorio, assinatura = estado.split(".", 2)
        mensagem = f"{timestamp}.{aleatorio}"
        esperado = base64.urlsafe_b64encode(
            hmac.new(config["state_secret"].encode(), mensagem.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return hmac.compare_digest(assinatura, esperado) and time.time() - int(timestamp) < 600
    except (TypeError, ValueError):
        return False


def _processar_retorno(config: dict) -> None:
    codigo = st.query_params.get("code")
    estado = st.query_params.get("state")
    if not codigo:
        return
    if not estado or not _estado_valido(config, estado):
        st.query_params.clear()
        raise ValueError("A validação de segurança do login expirou. Tente entrar novamente.")

    flow = _flow(config, state=estado)
    flow.fetch_token(code=codigo)
    credenciais = flow.credentials
    identidade = id_token.verify_oauth2_token(
        credenciais.id_token,
        Request(),
        config["client_id"],
    )
    email = str(identidade.get("email", "")).strip().lower()
    if not identidade.get("email_verified") or email not in _emails_permitidos():
        st.query_params.clear()
        raise PermissionError(f"O e-mail {email or 'informado'} não está autorizado.")

    st.session_state["usuario_google"] = {
        "email": email,
        "nome": identidade.get("name", email),
    }
    st.session_state["google_credentials"] = {
        "token": credenciais.token,
        "refresh_token": credenciais.refresh_token,
        "token_uri": credenciais.token_uri,
        "client_id": credenciais.client_id,
        "client_secret": credenciais.client_secret,
        "scopes": list(credenciais.scopes or ESCOPOS),
    }
    st.query_params.clear()
    st.rerun()


def usuario_autorizado() -> bool:
    return (
        "usuario_google" in st.session_state
        and st.session_state["usuario_google"].get("email", "").lower() in _emails_permitidos()
        and "google_credentials" in st.session_state
    )


def exibir_login() -> None:
    st.title("Acesso aos pedidos")
    st.write("Entre com uma Conta Google autorizada. O aplicativo não recebe nem armazena sua senha.")
    try:
        config = _config_oauth()
        _processar_retorno(config)
    except PermissionError as erro:
        st.error(str(erro))
        return
    except Exception as erro:
        st.error(str(erro))
        return

    estado = _novo_estado(config)
    flow = _flow(config, state=estado)
    url, estado = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    st.link_button("Entrar com Google", url, type="primary")
    st.caption("Acesso permitido somente para e-mails cadastrados pela administradora.")
