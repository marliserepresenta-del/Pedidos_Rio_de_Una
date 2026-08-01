from __future__ import annotations

import pandas as pd
import streamlit as st

from src.autenticacao import cliente_supabase, sair, tela_login, usuario_atual
from src.extrator import COLUNAS_EXIBICAO, extrair_varios_pdfs
from src.google_sheets import criar_planilha_do_envio


st.set_page_config(page_title="Rio de Una — Pedidos", page_icon="📄", layout="wide")

try:
    supabase = cliente_supabase()
except Exception as erro:
    st.error(f"Configuração incompleta: {erro}")
    st.stop()

usuario = usuario_atual(supabase)
if not usuario:
    tela_login(supabase)
    st.stop()

cabecalho, botao_sair = st.columns([5, 1])
cabecalho.title("Rio de Una — Pedidos")
cabecalho.caption(f"Administrador conectado: {usuario.nome} · {usuario.email}")
if botao_sair.button("Sair"):
    sair(supabase)
    st.rerun()

aba_envio, aba_historico, aba_usuarios = st.tabs(["Enviar pedidos", "Histórico", "Usuários"])

with aba_envio:
    arquivos = st.file_uploader("Selecione um ou vários PDFs", type=["pdf"], accept_multiple_files=True)
    if arquivos:
        try:
            tabela, avisos = extrair_varios_pdfs(arquivos)
        except ValueError as erro:
            st.error(str(erro))
        else:
            for aviso in avisos:
                st.warning(aviso)
            st.success(f"{len(tabela)} itens únicos extraídos de {len(arquivos)} arquivo(s).")
            c1, c2, c3 = st.columns(3)
            c1.metric("Pedidos", tabela["pedido"].nunique())
            c2.metric("Produtos", tabela["codigo_produto"].nunique())
            c3.metric("Valor total", f"R$ {tabela['valor_item'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(tabela[COLUNAS_EXIBICAO], use_container_width=True, hide_index=True)
            csv = tabela[COLUNAS_EXIBICAO].to_csv(index=False).encode("utf-8-sig")
            st.download_button("Baixar CSV", csv, "pedidos_extraidos.csv", "text/csv")
            if st.button("Finalizar e criar planilha", type="primary"):
                with st.spinner("Criando a planilha..."):
                    try:
                        resultado = criar_planilha_do_envio(tabela, st.secrets["gcp_service_account"], usuario.email)
                        supabase.table("shipments").insert({
                            "user_id": usuario.id,
                            "user_email": usuario.email,
                            "file_name": resultado.nome,
                            "sheet_url": resultado.url,
                            "item_count": resultado.itens,
                        }).execute()
                    except Exception as erro:
                        st.error(f"Não foi possível finalizar: {erro}")
                    else:
                        st.success(f"Planilha criada com {resultado.itens} itens.")
                        st.link_button("Abrir planilha", resultado.url)
    else:
        st.info("Envie os relatórios para começar. Os PDFs não ficam armazenados.")

with aba_historico:
    historico = supabase.table("shipments").select("created_at,user_email,file_name,sheet_url,item_count").order("created_at", desc=True).execute().data
    if historico:
        st.dataframe(pd.DataFrame(historico), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum envio finalizado.")

with aba_usuarios:
    perfis = supabase.table("profiles").select("id,name,email,active,created_at").order("created_at").execute().data
    ativos = sum(bool(p["active"]) for p in perfis)
    st.metric("Usuários ativos", f"{ativos} de 4")
    for perfil in perfis:
        linha, acao = st.columns([5, 1])
        status = "Ativo" if perfil["active"] else "Pendente/Desativado"
        linha.write(f"**{perfil.get('name') or 'Sem nome'}** · {perfil['email']} · {status}")
        if perfil["id"] == usuario.id:
            acao.caption("Sua conta")
        elif perfil["active"]:
            if acao.button("Desativar", key=f"off_{perfil['id']}"):
                try:
                    supabase.rpc("set_user_active", {"target_id": perfil["id"], "desired_active": False}).execute()
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))
        else:
            if acao.button("Aprovar", key=f"on_{perfil['id']}", disabled=ativos >= 4):
                try:
                    supabase.rpc("set_user_active", {"target_id": perfil["id"], "desired_active": True}).execute()
                    st.rerun()
                except Exception as erro:
                    st.error(str(erro))
