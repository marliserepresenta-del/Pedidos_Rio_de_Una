from __future__ import annotations

from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.autenticacao import cliente_supabase, sair, tela_login, usuario_atual
from src.extrator import COLUNAS_EXIBICAO, extrair_varios_pdfs


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
            if st.button("Finalizar e salvar no Supabase", type="primary"):
                with st.spinner("Validando duplicidades e salvando o envio..."):
                    try:
                        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
                        nome_usuario = usuario.email.split("@", 1)[0].replace(".", "_")
                        nome_lote = f"Pedidos_{agora:%Y-%m-%d_%H-%M-%S}_{nome_usuario}"
                        itens = json.loads(tabela[COLUNAS_EXIBICAO].to_json(orient="records"))
                        resposta = supabase.rpc("finalize_shipment", {
                            "p_batch_name": nome_lote,
                            "p_file_names": [arquivo.name for arquivo in arquivos],
                            "p_items": itens,
                        }).execute()
                        resultado = resposta.data[0] if resposta.data else {}
                    except Exception as erro:
                        st.error(f"Não foi possível finalizar: {erro}")
                    else:
                        novos = int(resultado.get("inserted_count", 0))
                        duplicados = int(resultado.get("duplicate_count", 0))
                        st.success(f"Envio salvo: {novos} item(ns) novo(s) e {duplicados} repetido(s) ignorado(s).")
    else:
        st.info("Envie os relatórios para começar. Os PDFs não ficam armazenados.")

with aba_historico:
    historico = supabase.table("shipments").select(
        "id,created_at,user_email,batch_name,file_names,item_count,duplicate_count"
    ).order("created_at", desc=True).execute().data
    if historico:
        tabela_historico = pd.DataFrame(historico)
        st.dataframe(tabela_historico.drop(columns=["id"]), use_container_width=True, hide_index=True)
        opcoes = {f"{item['batch_name']} · {item['item_count']} itens": item["id"] for item in historico}
        envio_escolhido = st.selectbox("Abrir um envio", options=list(opcoes), index=None)
        if envio_escolhido:
            itens_envio = supabase.table("shipment_items").select("*").eq(
                "shipment_id", opcoes[envio_escolhido]
            ).order("pagina").execute().data
            if itens_envio:
                df_envio = pd.DataFrame(itens_envio)
                colunas_internas = [c for c in ["shipment_id", "created_at"] if c in df_envio.columns]
                df_envio = df_envio.drop(columns=colunas_internas)
                st.dataframe(df_envio, use_container_width=True, hide_index=True)
                st.download_button(
                    "Baixar este envio em CSV",
                    df_envio.to_csv(index=False).encode("utf-8-sig"),
                    f"{envio_escolhido.split(' · ')[0]}.csv",
                    "text/csv",
                )
            else:
                st.info("Este envio não adicionou itens novos; todos já existiam no banco.")
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
