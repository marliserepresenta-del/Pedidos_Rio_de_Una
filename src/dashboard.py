"""Painel analítico dos pedidos armazenados no Supabase."""

from __future__ import annotations

from datetime import date
from math import ceil

import pandas as pd
import streamlit as st
from supabase import Client

from src.relatorio_pdf import gerar_relatorio_pdf


COLUNAS_NUMERICAS = ("embalagem", "quantidade", "valor_item")


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _coluna_moeda(serie: pd.Series) -> pd.Series:
    """Formata valores monetários no padrão brasileiro para exibição."""
    return serie.map(lambda valor: _moeda(float(valor)))


def _carregar_itens(cliente: Client) -> pd.DataFrame:
    """Pagina a consulta para não limitar o painel aos primeiros mil registros."""
    registros: list[dict] = []
    pagina = 1_000
    inicio = 0
    while True:
        lote = (
            cliente.table("shipment_items")
            .select("*")
            .order("id_registro")
            .range(inicio, inicio + pagina - 1)
            .execute()
            .data
        )
        registros.extend(lote)
        if len(lote) < pagina:
            break
        inicio += pagina
    return pd.DataFrame(registros)


def _opcoes(df: pd.DataFrame, coluna: str) -> list[str]:
    if coluna not in df:
        return []
    return sorted(df[coluna].dropna().astype(str).unique().tolist())


def _aplicar_multiselect(df: pd.DataFrame, coluna: str, escolhas: list[str]) -> pd.DataFrame:
    if escolhas:
        return df[df[coluna].astype(str).isin(escolhas)]
    return df


def _pagina_dataframe(df: pd.DataFrame, chave: str, tamanho: int = 200) -> pd.DataFrame:
    """Exibe controles e devolve somente a página enviada ao PyArrow/Streamlit."""
    total = len(df)
    paginas = max(1, ceil(total / tamanho))
    informacao, navegacao = st.columns([5, 1], vertical_alignment="bottom")
    informacao.caption(f"{total:,} registro(s) · {tamanho} por página".replace(",", "."))
    chave_pagina = f"pagina_{chave}"
    if int(st.session_state.get(chave_pagina, 1)) > paginas:
        st.session_state[chave_pagina] = paginas
    pagina = int(navegacao.number_input(
        "Página",
        min_value=1,
        max_value=paginas,
        value=1,
        step=1,
        key=chave_pagina,
    ))
    inicio = (pagina - 1) * tamanho
    return df.iloc[inicio:inicio + tamanho].copy()


def exibir_dashboard(cliente: Client) -> None:
    st.subheader("Visão geral dos pedidos")
    st.caption("Explore valores, quantidades, lojas e produtos usando os filtros abaixo.")
    st.write("")

    try:
        base = _carregar_itens(cliente)
    except Exception as erro:
        st.error(f"Não foi possível carregar os dados: {erro}")
        return
    if base.empty:
        st.info("Ainda não existem produtos salvos. Finalize um envio para alimentar o painel.")
        return

    for coluna in COLUNAS_NUMERICAS:
        if coluna in base:
            base[coluna] = pd.to_numeric(base[coluna], errors="coerce").fillna(0.0)
    calculado = base["valor_item"].div(base["quantidade"].where(base["quantidade"] != 0))
    if "valor_unitario" in base:
        informado = pd.to_numeric(base["valor_unitario"], errors="coerce")
        base["valor_unitario"] = informado.where(informado.notna() & (informado != 0), calculado)
    else:
        base["valor_unitario"] = calculado
    base["valor_unitario"] = base["valor_unitario"].fillna(0).round(4)
    base["emissao"] = pd.to_datetime(base["emissao"], errors="coerce")
    datas_validas = base["emissao"].dropna()
    if datas_validas.empty:
        st.error("Não há datas de emissão válidas para montar o painel.")
        return

    data_minima = datas_validas.min().date()
    data_maxima = datas_validas.max().date()

    with st.container(border=True):
        st.markdown("#### Filtros")
        periodo_col, codigo_col, pedido_col = st.columns([2, 1.5, 1.4], gap="large")
        periodo = periodo_col.date_input(
            "Período de emissão",
            value=(data_minima, data_maxima),
            min_value=data_minima,
            max_value=data_maxima,
            format="DD/MM/YYYY",
        )
        codigo_busca = codigo_col.text_input("Código do produto", placeholder="Digite o código")
        pedido = pedido_col.text_input("Número do pedido")

        st.write("")
        f1, f2, f3, f4 = st.columns(4, gap="large")
        produtos_escolhidos = f1.multiselect("Produto", _opcoes(base, "produto"))
        locais = f2.multiselect("Loja / local", _opcoes(base, "local"))
        fornecedores = f3.multiselect("Fornecedor", _opcoes(base, "fornecedor"))
        compradores = f4.multiselect("Comprador", _opcoes(base, "comprador"))

    filtrada = base.copy()
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio, fim = periodo
    else:
        inicio = fim = periodo if isinstance(periodo, date) else data_minima
    filtrada = filtrada[
        filtrada["emissao"].dt.date.between(inicio, fim, inclusive="both")
    ]
    if codigo_busca.strip():
        filtrada = filtrada[
            filtrada["codigo_produto"].fillna("").astype(str).str.contains(
                codigo_busca.strip(), case=False, regex=False
            )
        ]
    if pedido.strip():
        filtrada = filtrada[
            filtrada["pedido"].fillna("").astype(str).str.contains(
                pedido.strip(), case=False, regex=False
            )
        ]
    for coluna, escolhas in (
        ("produto", produtos_escolhidos), ("local", locais),
        ("fornecedor", fornecedores), ("comprador", compradores),
    ):
        filtrada = _aplicar_multiselect(filtrada, coluna, escolhas)

    st.write("")
    if filtrada.empty:
        st.warning("Nenhum pedido corresponde aos filtros selecionados.")
        return

    total = float(filtrada["valor_item"].sum())
    quantidade = float(filtrada["quantidade"].sum())
    valor_medio = total / quantidade if quantidade else 0.0
    m1, m2, m3, m4 = st.columns(4, gap="large")
    m1.metric("Valor total", _moeda(total))
    m2.metric("Quantidade de produtos", f"{quantidade:,.0f}".replace(",", "."))
    m3.metric("Valor unitário médio", _moeda(valor_medio))
    m4.metric("Produtos", int(filtrada["codigo_produto"].nunique()))

    st.write("")
    st.divider()
    produtos = (
        filtrada.groupby(["codigo_produto", "produto"], dropna=False, as_index=False)
        .agg(quantidade=("quantidade", "sum"), valor=("valor_item", "sum"))
        .sort_values("valor", ascending=False)
    )
    lojas = (
        filtrada.groupby("local", dropna=False, as_index=False)
        .agg(quantidade=("quantidade", "sum"), valor=("valor_item", "sum"))
        .sort_values("valor", ascending=False)
    )
    grafico_produto, grafico_loja = st.columns(2, gap="large")
    with grafico_produto:
        st.markdown("#### Top 10 valores por produto")
        top_produtos = produtos.head(10).copy()
        top_produtos["Produto"] = top_produtos["codigo_produto"].astype(str) + " · " + top_produtos["produto"].astype(str)
        st.bar_chart(top_produtos.set_index("Produto")["valor"], color="#1FAA70", height=430)
    with grafico_loja:
        st.markdown("#### Valores por loja")
        st.bar_chart(lojas.set_index("local")["valor"], color="#FF5A52", height=430)

    st.write("")
    anual_col, mensal_col = st.columns(2, gap="large")
    temporal = filtrada.dropna(subset=["emissao"]).copy()
    temporal["ano"] = temporal["emissao"].dt.year.astype(str)
    temporal["mes_ordem"] = temporal["emissao"].dt.to_period("M")
    temporal["mês/ano"] = temporal["emissao"].dt.strftime("%m/%Y")
    anual = temporal.groupby("ano", as_index=False)["valor_item"].sum()
    mensal = (
        temporal.groupby(["mes_ordem", "mês/ano"], as_index=False)["valor_item"].sum()
        .sort_values("mes_ordem")
    )
    with anual_col:
        st.markdown("#### Valores por ano")
        st.bar_chart(anual.set_index("ano")["valor_item"], color="#FFB21C", height=380)
    with mensal_col:
        st.markdown("#### Valores por mês/ano")
        st.bar_chart(mensal.set_index("mês/ano")["valor_item"], color="#1E88E5", height=380)

    st.write("")
    st.divider()
    st.markdown("#### Resumo completo por produto")
    resumo_produtos = (
        filtrada[["codigo_produto", "produto", "emissao", "valor_unitario"]]
        .sort_values(["produto", "emissao", "codigo_produto"], kind="stable")
        .copy()
    )
    resumo_exibicao = _pagina_dataframe(resumo_produtos, "resumo_produtos")
    resumo_exibicao["emissao"] = resumo_exibicao["emissao"].dt.strftime("%d/%m/%Y")
    resumo_exibicao["valor_unitario"] = _coluna_moeda(resumo_exibicao["valor_unitario"])
    st.dataframe(
        resumo_exibicao,
        width="stretch",
        hide_index=True,
        column_config={
            "codigo_produto": "Código",
            "produto": "Produto",
            "emissao": "Data",
            "valor_unitario": "Valor unitário",
        },
    )

    st.write("")
    st.markdown("#### Todos os pedidos filtrados")
    tabela = filtrada.drop(columns=["shipment_id", "created_at"], errors="ignore").copy()
    tabela["emissao"] = tabela["emissao"].dt.strftime("%d/%m/%Y")
    tabela_exibicao = _pagina_dataframe(tabela, "todos_pedidos")
    tabela_exibicao["valor_item"] = _coluna_moeda(tabela_exibicao["valor_item"])
    tabela_exibicao["valor_unitario"] = _coluna_moeda(tabela_exibicao["valor_unitario"])
    st.dataframe(
        tabela_exibicao,
        width="stretch",
        hide_index=True,
        height=520,
        column_config={
            "valor_item": "Valor do item",
            "valor_unitario": "Valor unitário",
            "quantidade": st.column_config.NumberColumn("Quantidade", format="%.2f"),
        },
    )
    filtros_pdf = {
        "Código": codigo_busca.strip(),
        "Pedido": pedido.strip(),
        "Produto": ", ".join(produtos_escolhidos),
        "Loja": ", ".join(locais),
        "Fornecedor": ", ".join(fornecedores),
        "Comprador": ", ".join(compradores),
    }
    assinatura_pdf = (
        str(inicio), str(fim), codigo_busca.strip(), pedido.strip(),
        tuple(produtos_escolhidos), tuple(locais), tuple(fornecedores),
        tuple(compradores), len(filtrada), float(filtrada["valor_item"].sum()),
    )
    if st.session_state.get("assinatura_pdf_dashboard") != assinatura_pdf:
        st.session_state.pop("pdf_dashboard", None)
    baixar_csv, preparar_pdf = st.columns([1, 1], gap="medium")
    baixar_csv.download_button(
        "Baixar dados filtrados em CSV",
        tabela.to_csv(index=False).encode("utf-8-sig"),
        "pedidos_filtrados.csv",
        "text/csv",
        width="stretch",
    )
    if preparar_pdf.button("Preparar relatório em PDF", type="primary", width="stretch"):
        with st.spinner("Preparando o PDF com todos os pedidos filtrados..."):
            st.session_state["pdf_dashboard"] = gerar_relatorio_pdf(
                filtrada, inicio, fim, filtros_pdf
            )
            st.session_state["assinatura_pdf_dashboard"] = assinatura_pdf
    if pdf := st.session_state.get("pdf_dashboard"):
        st.download_button(
            "Baixar relatório em PDF",
            pdf,
            f"relatorio_pedidos_{inicio:%Y-%m-%d}_a_{fim:%Y-%m-%d}.pdf",
            "application/pdf",
            type="primary",
            width="stretch",
        )
