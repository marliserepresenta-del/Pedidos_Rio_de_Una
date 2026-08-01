"""Painel analítico dos pedidos armazenados no Supabase."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from supabase import Client


COLUNAS_NUMERICAS = ("embalagem", "quantidade", "valor_item", "valor_unitario")


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
    if "valor_unitario" not in base:
        base["valor_unitario"] = base["valor_item"].div(base["quantidade"].replace(0, pd.NA)).fillna(0)
    base["emissao"] = pd.to_datetime(base["emissao"], errors="coerce")
    datas_validas = base["emissao"].dropna()
    if datas_validas.empty:
        st.error("Não há datas de emissão válidas para montar o painel.")
        return

    data_minima = datas_validas.min().date()
    data_maxima = datas_validas.max().date()

    with st.container(border=True):
        st.markdown("#### Filtros")
        periodo_col, busca_col, pedido_col = st.columns([2, 2, 1.4], gap="large")
        periodo = periodo_col.date_input(
            "Período de emissão",
            value=(data_minima, data_maxima),
            min_value=data_minima,
            max_value=data_maxima,
            format="DD/MM/YYYY",
        )
        busca = busca_col.text_input("Produto ou código", placeholder="Digite parte do nome ou código")
        pedido = pedido_col.text_input("Número do pedido")

        st.write("")
        f1, f2, f3, f4 = st.columns(4, gap="large")
        locais = f1.multiselect("Loja / local", _opcoes(base, "local"))
        empresas = f2.multiselect("Empresa", _opcoes(base, "empresa"))
        fornecedores = f3.multiselect("Fornecedor", _opcoes(base, "fornecedor"))
        compradores = f4.multiselect("Comprador", _opcoes(base, "comprador"))

        f5, f6, f7 = st.columns(3, gap="large")
        status = f5.multiselect("Status", _opcoes(base, "status"))
        unidades = f6.multiselect("Unidade", _opcoes(base, "unidade"))
        arquivos = f7.multiselect("Arquivo de origem", _opcoes(base, "arquivo"))

    filtrada = base.copy()
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio, fim = periodo
    else:
        inicio = fim = periodo if isinstance(periodo, date) else data_minima
    filtrada = filtrada[
        filtrada["emissao"].dt.date.between(inicio, fim, inclusive="both")
    ]
    if busca.strip():
        termo = busca.strip()
        produto = filtrada["produto"].fillna("").astype(str)
        codigo = filtrada["codigo_produto"].fillna("").astype(str)
        filtrada = filtrada[
            produto.str.contains(termo, case=False, regex=False)
            | codigo.str.contains(termo, case=False, regex=False)
        ]
    if pedido.strip():
        filtrada = filtrada[
            filtrada["pedido"].fillna("").astype(str).str.contains(
                pedido.strip(), case=False, regex=False
            )
        ]
    for coluna, escolhas in (
        ("local", locais), ("empresa", empresas), ("fornecedor", fornecedores),
        ("comprador", compradores), ("status", status), ("unidade", unidades),
        ("arquivo", arquivos),
    ):
        filtrada = _aplicar_multiselect(filtrada, coluna, escolhas)

    st.write("")
    if filtrada.empty:
        st.warning("Nenhum pedido corresponde aos filtros selecionados.")
        return

    total = float(filtrada["valor_item"].sum())
    quantidade = float(filtrada["quantidade"].sum())
    valor_medio = total / quantidade if quantidade else 0.0
    m1, m2, m3, m4, m5 = st.columns(5, gap="large")
    m1.metric("Valor total", _moeda(total))
    m2.metric("Quantidade", f"{quantidade:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    m3.metric("Valor unitário médio", _moeda(valor_medio))
    m4.metric("Produtos", int(filtrada["codigo_produto"].nunique()))
    m5.metric("Pedidos", int(filtrada["pedido"].nunique()))

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
        st.markdown("#### Valores por produto")
        top_produtos = produtos.head(20).copy()
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
        st.line_chart(mensal.set_index("mês/ano")["valor_item"], color="#1E88E5", height=380)

    st.write("")
    st.divider()
    st.markdown("#### Resumo completo por produto")
    produtos["valor_unitario_medio"] = produtos["valor"].div(produtos["quantidade"].replace(0, pd.NA))
    st.dataframe(
        produtos,
        use_container_width=True,
        hide_index=True,
        column_config={
            "quantidade": st.column_config.NumberColumn("Quantidade", format="%.2f"),
            "valor": st.column_config.NumberColumn("Valor total", format="R$ %.2f"),
            "valor_unitario_medio": st.column_config.NumberColumn("Valor unitário médio", format="R$ %.4f"),
        },
    )

    st.write("")
    st.markdown("#### Todos os pedidos filtrados")
    tabela = filtrada.drop(columns=["shipment_id", "created_at"], errors="ignore").copy()
    tabela["emissao"] = tabela["emissao"].dt.strftime("%d/%m/%Y")
    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config={
            "valor_item": st.column_config.NumberColumn("Valor do item", format="R$ %.2f"),
            "valor_unitario": st.column_config.NumberColumn("Valor unitário", format="R$ %.4f"),
            "quantidade": st.column_config.NumberColumn("Quantidade", format="%.2f"),
        },
    )
    st.download_button(
        "Baixar dados filtrados em CSV",
        tabela.to_csv(index=False).encode("utf-8-sig"),
        "pedidos_filtrados.csv",
        "text/csv",
    )
