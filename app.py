from __future__ import annotations

import pandas as pd
import streamlit as st

from src.autenticacao import exibir_login, usuario_autorizado
from src.extrator import COLUNAS_EXIBICAO, extrair_varios_pdfs
from src.google_sheets import criar_planilha_do_envio


st.set_page_config(page_title="Pedidos TOTVS", page_icon="📄", layout="wide")
if not usuario_autorizado():
    exibir_login()
    st.stop()

usuario = st.session_state["usuario_google"]
topo, sair = st.columns([5, 1])
with topo:
    st.caption(f"Conectado como {usuario['email']}")
with sair:
    if st.button("Sair"):
        for chave in ["google_credentials", "usuario_google"]:
            st.session_state.pop(chave, None)
        st.query_params.clear()
        st.rerun()

st.title("Pedidos TOTVS → Google Planilhas")
st.caption("Envie um ou vários relatórios, revise os itens e crie um arquivo separado no Google Drive.")

arquivos = st.file_uploader(
    "Selecione um ou vários PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if arquivos:
    try:
        tabela, avisos = extrair_varios_pdfs(arquivos)
    except ValueError as erro:
        st.error(str(erro))
        st.stop()

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

    st.divider()
    st.subheader("Finalizar envio")
    st.caption("Será criado um novo arquivo no seu Google Drive. Cada envio gera um arquivo independente.")
    if st.button("Finalizar e criar planilha", type="primary"):
        with st.spinner("Criando a planilha no Google Drive..."):
            try:
                resultado = criar_planilha_do_envio(
                    tabela,
                    st.session_state["google_credentials"],
                    usuario["email"],
                )
            except Exception as erro:
                st.error(f"Não foi possível criar a planilha: {erro}")
            else:
                st.success(f"Planilha criada com {resultado.itens} item(ns).")
                st.link_button("Abrir planilha no Google", resultado.url)
else:
    st.info("Envie os relatórios para começar. Os PDFs não ficam armazenados pelo aplicativo.")
