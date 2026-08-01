from __future__ import annotations

from dataclasses import dataclass

import streamlit as st
from supabase import Client, create_client


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
                st.session_state["auth_session"] = {
                    "access_token": resposta.session.access_token,
                    "refresh_token": resposta.session.refresh_token,
                }
        except Exception:
            st.session_state.pop("auth_session", None)
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
    st.session_state["auth_session"] = {
        "access_token": resposta.session.access_token,
        "refresh_token": resposta.session.refresh_token,
    }


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


def sair(cliente: Client) -> None:
    try:
        cliente.auth.sign_out()
    finally:
        st.session_state.pop("auth_session", None)


def tela_login(cliente: Client) -> None:
    st.title("Rio de Una — Pedidos")
    st.caption("Acesso seguro para usuários aprovados.")
    entrar_tab, cadastro_tab = st.tabs(["Entrar", "Solicitar acesso"])
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
