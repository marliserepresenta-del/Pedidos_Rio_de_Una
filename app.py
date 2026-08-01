from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from src.extrator import COLUNAS_EXIBICAO, extrair_varios_pdfs
from src.google_sheets import configurar_planilha, enviar_sem_duplicar


st.set_page_config(page_title="Pedidos TOTVS", page_icon="📄", layout="wide")
st.title("Pedidos TOTVS → Google Planilhas")
st.caption("Extraia um ou vários relatórios PDF, revise os itens e grave apenas registros novos.")

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
    st.subheader("Enviar ao Google Planilhas")
    st.caption("A conexão usa a conta de serviço configurada nos Secrets do Streamlit.")

    try:
        config = configurar_planilha(st.secrets)
    except ValueError as erro:
        st.info(str(erro))
    else:
        st.write(f"Destino: `{config.nome_planilha}` → aba `{config.nome_aba}`")
        if st.button("Adicionar somente itens novos", type="primary"):
            with st.spinner("Comparando e enviando registros..."):
                try:
                    resultado = enviar_sem_duplicar(tabela, config)
                except Exception as erro:
                    st.error(f"Não foi possível atualizar a planilha: {erro}")
                else:
                    st.success(
                        f"{resultado.inseridos} item(ns) inserido(s); "
                        f"{resultado.duplicados} duplicado(s) ignorado(s)."
                    )
else:
    st.info("Envie os relatórios para começar. Os PDFs não ficam armazenados pelo aplicativo.")

