from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import streamlit as st
from supabase import Client, create_client

from src.session_manager import clear_session, get_saved_refresh_token, save_session


LOGO_APP = Path(__file__).resolve().parents[1] / "assets" / "comida-saudavel.png"


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nome: str


def cliente_supabase() -> Client:
    if "supabase" not in st.secrets:
        raise ValueError("Configure [supabase] no secrets.toml.")
    config = st.secrets["supabase"]
    if not config.get("url") or not config.get("key"):
        raise ValueError("A URL ou a chave publicável do Supabase não foi configurada.")
    cliente = create_client(config["url"], config["key"])
    sessao = st.session_state.get("auth_session")
    if sessao:
        try:
            resposta = cliente.auth.set_session(sessao["access_token"], sessao["refresh_token"])
            if resposta.session:
                save_session(resposta.session.access_token, resposta.session.refresh_token)
        except Exception:
            clear_session()
    else:
        refresh_token = get_saved_refresh_token()
        if refresh_token:
            try:
                resposta = cliente.auth.refresh_session(refresh_token)
                if resposta.session:
                    save_session(resposta.session.access_token, resposta.session.refresh_token)
            except Exception:
                clear_session()
    return cliente


def _perfil_ativo(cliente: Client, user_id: str) -> dict | None:
    resposta = cliente.table("profiles").select("id,email,name,active").eq("id", user_id).maybe_single().execute()
    perfil = resposta.data
    return perfil if perfil and perfil.get("active") else None


def usuario_atual(cliente: Client) -> Usuario | None:
    if "auth_session" not in st.session_state:
        return None
    try:
        resposta = cliente.auth.get_user()
        if not resposta.user:
            return None
        perfil = _perfil_ativo(cliente, str(resposta.user.id))
        if not perfil:
            return None
        return Usuario(id=str(perfil["id"]), email=perfil["email"], nome=perfil.get("name") or perfil["email"])
    except Exception:
        return None


def entrar(cliente: Client, email: str, senha: str) -> None:
    resposta = cliente.auth.sign_in_with_password({"email": email.strip().lower(), "password": senha})
    if not resposta.session or not resposta.user:
        raise ValueError("E-mail ou senha inválidos.")
    perfil = _perfil_ativo(cliente, str(resposta.user.id))
    if not perfil:
        cliente.auth.sign_out()
        raise PermissionError("Sua conta ainda não foi aprovada ou está desativada.")
    save_session(resposta.session.access_token, resposta.session.refresh_token)
    # Dá tempo para os componentes gravarem a sessão antes do rerun do Streamlit.
    time.sleep(0.8)


def cadastrar(cliente: Client, nome: str, email: str, senha: str) -> None:
    if len(nome.strip()) < 2:
        raise ValueError("Informe seu nome.")
    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    resposta = cliente.auth.sign_up({
        "email": email.strip().lower(),
        "password": senha,
        "options": {"data": {"name": nome.strip()}},
    })
    if not resposta.user:
        raise ValueError("Não foi possível criar a solicitação.")


def solicitar_redefinicao(cliente: Client, email: str) -> None:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Informe um e-mail válido.")
    cliente.auth.reset_password_email(email)


def tela_redefinir_senha(cliente: Client) -> None:
    """Confirma o link de recuperação e permite cadastrar uma nova senha."""
    token_hash = st.query_params.get("token_hash")
    if not st.session_state.get("recovery_verified"):
        if not token_hash:
            st.error("O link de recuperação é inválido ou expirou.")
            st.stop()
        try:
            resposta = cliente.auth.verify_otp({
                "token_hash": token_hash,
                "type": "recovery",
            })
            if not resposta.session:
                raise ValueError("Sessão de recuperação não criada.")
            save_session(resposta.session.access_token, resposta.session.refresh_token)
            st.session_state["recovery_verified"] = True
        except Exception:
            st.error("O link de recuperação é inválido ou expirou.")
            st.stop()

    st.image(str(LOGO_APP), width=84)
    st.title("Rio de Una — Nova senha")
    with st.form("nova_senha_recuperacao"):
        senha = st.text_input("Nova senha", type="password")
        confirmar = st.text_input("Confirmar nova senha", type="password")
        salvar = st.form_submit_button("Salvar nova senha", type="primary")
    if salvar:
        if len(senha) < 8:
            st.error("A senha deve ter pelo menos 8 caracteres.")
        elif senha != confirmar:
            st.error("As senhas não coincidem.")
        else:
            try:
                cliente.auth.update_user({"password": senha})
            except Exception as erro:
                st.error(f"Não foi possível alterar a senha: {erro}")
            else:
                st.session_state.pop("recovery_verified", None)
                st.query_params.clear()
                st.success("Senha alterada. Você já pode continuar no aplicativo.")


def sair(cliente: Client) -> None:
    try:
        cliente.auth.sign_out()
    finally:
        clear_session()


def tela_login(cliente: Client) -> None:
    st.image(str(LOGO_APP), width=96)
    st.title("Rio de Una — Pedidos")
    st.caption("Acesso seguro para usuários aprovados.")
    entrar_tab, cadastro_tab, recuperar_tab = st.tabs(
        ["Entrar", "Solicitar acesso", "Esqueci minha senha"]
    )
    with entrar_tab:
        with st.form("login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            enviar = st.form_submit_button("Entrar", type="primary")
        if enviar:
            try:
                entrar(cliente, email, senha)
            except PermissionError as erro:
                st.warning(str(erro))
            except Exception:
                st.error("E-mail ou senha inválidos.")
            else:
                st.rerun()
    with cadastro_tab:
        st.caption("A conta ficará pendente até ser aprovada por um administrador.")
        with st.form("cadastro"):
            nome = st.text_input("Nome")
            novo_email = st.text_input("E-mail", key="novo_email")
            nova_senha = st.text_input("Senha", type="password", key="nova_senha")
            confirmar = st.text_input("Confirmar senha", type="password")
            solicitar = st.form_submit_button("Solicitar acesso")
        if solicitar:
            if nova_senha != confirmar:
                st.error("As senhas não coincidem.")
            else:
                try:
                    cadastrar(cliente, nome, novo_email, nova_senha)
                except Exception as erro:
                    st.error(str(erro))
                else:
                    st.success("Solicitação criada. Confirme seu e-mail e aguarde a aprovação.")
    with recuperar_tab:
        st.caption("Enviaremos um link seguro para cadastrar uma nova senha.")
        with st.form("recuperar_senha"):
            email_recuperacao = st.text_input("E-mail", key="email_recuperacao")
            recuperar = st.form_submit_button("Enviar link de redefinição")
        if recuperar:
            try:
                solicitar_redefinicao(cliente, email_recuperacao)
            except Exception as erro:
                st.error(f"Não foi possível enviar o link: {erro}")
            else:
                # A mesma mensagem evita revelar se um endereço está cadastrado.
                st.success("Se o e-mail estiver cadastrado, o link chegará em instantes.")
