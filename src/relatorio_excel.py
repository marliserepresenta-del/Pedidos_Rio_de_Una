"""Geração de planilha Excel com os pedidos filtrados."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


def _preparar_dados(dados: pd.DataFrame) -> pd.DataFrame:
    planilha = dados.drop(columns=["shipment_id", "created_at"], errors="ignore").copy()
    if "emissao" in planilha.columns:
        planilha["emissao"] = pd.to_datetime(planilha["emissao"], errors="coerce")
    return planilha


def gerar_excel_pedidos_detalhados(dados: pd.DataFrame) -> bytes:
    """Retorna um Excel com tabela delimitada, filtros e formatos."""
    planilha = _preparar_dados(dados)
    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="xlsxwriter",
        datetime_format="dd/mm/yyyy",
        date_format="dd/mm/yyyy",
    ) as writer:
        sheet_name = "Pedidos detalhados"
        planilha.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1, header=False)

        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        header_format = workbook.add_format({
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#075E54",
            "border": 1,
            "border_color": "#D4D8DD",
            "align": "center",
            "valign": "vcenter",
        })
        text_format = workbook.add_format({
            "border": 1,
            "border_color": "#D4D8DD",
            "valign": "top",
        })
        money_format = workbook.add_format({
            "num_format": 'R$ #,##0.00',
            "border": 1,
            "border_color": "#D4D8DD",
        })
        number_format = workbook.add_format({
            "num_format": "#,##0.00",
            "border": 1,
            "border_color": "#D4D8DD",
        })
        date_format = workbook.add_format({
            "num_format": "dd/mm/yyyy",
            "border": 1,
            "border_color": "#D4D8DD",
        })

        rows, cols = planilha.shape
        for col_num, column_name in enumerate(planilha.columns):
            worksheet.write(0, col_num, column_name, header_format)
            serie = planilha[column_name].dropna().astype(str)
            largura = max([len(str(column_name)), *(serie.str.len().head(1000).tolist() or [0])])
            worksheet.set_column(col_num, col_num, min(max(largura + 2, 12), 45), text_format)

        for column_name in ("valor_item", "valor_unitario"):
            if column_name in planilha.columns:
                col_num = planilha.columns.get_loc(column_name)
                worksheet.set_column(col_num, col_num, 15, money_format)

        if "quantidade" in planilha.columns:
            col_num = planilha.columns.get_loc("quantidade")
            worksheet.set_column(col_num, col_num, 12, number_format)

        if "emissao" in planilha.columns:
            col_num = planilha.columns.get_loc("emissao")
            worksheet.set_column(col_num, col_num, 12, date_format)

        if rows and cols:
            worksheet.add_table(
                0,
                0,
                rows,
                cols - 1,
                {
                    "columns": [{"header": str(column)} for column in planilha.columns],
                    "style": "Table Style Medium 4",
                    "autofilter": True,
                },
            )
        worksheet.freeze_panes(1, 0)

    return buffer.getvalue()
