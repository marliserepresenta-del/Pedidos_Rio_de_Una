"""Geração do relatório PDF correspondente aos filtros do painel."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


VERDE = colors.HexColor("#138A72")
VERDE_ESCURO = colors.HexColor("#075E54")
CINZA = colors.HexColor("#F3F5F7")
LOGO = Path(__file__).resolve().parents[1] / "assets" / "comida-saudavel.png"


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _numero(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def _texto(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    return str(valor)


def _tabela(dados: list[list[object]], larguras: list[float], *, repetir: bool = True) -> Table:
    tabela = Table(dados, colWidths=larguras, repeatRows=1 if repetir else 0, hAlign="LEFT")
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D4D8DD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabela


def gerar_relatorio_pdf(
    dados: pd.DataFrame,
    inicio: date,
    fim: date,
    filtros: dict[str, str],
) -> bytes:
    """Retorna um PDF completo, pronto para o botão de download."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=14 * mm,
        title="Rio de Una - Relatório de pedidos",
        author="Rio de Una",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloRioUna", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=23, textColor=VERDE_ESCURO, alignment=TA_LEFT,
        spaceAfter=2 * mm,
    )
    secao = ParagraphStyle(
        "SecaoRioUna", parent=estilos["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=VERDE_ESCURO, spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    normal = ParagraphStyle(
        "NormalRioUna", parent=estilos["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#263238"),
    )
    pequeno = ParagraphStyle(
        "PequenoRioUna", parent=normal, fontSize=7.2, leading=9,
    )

    elementos: list[object] = []
    cabecalho = []
    if LOGO.exists():
        cabecalho.append(Image(str(LOGO), width=18 * mm, height=18 * mm))
    cabecalho.append(Paragraph("Rio de Una - Relatório de pedidos", titulo))
    topo = Table([cabecalho], colWidths=[22 * mm, 240 * mm] if len(cabecalho) == 2 else [262 * mm])
    topo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elementos.extend([topo, Spacer(1, 3 * mm)])
    elementos.append(Paragraph(
        f"Período analisado: <b>{inicio:%d/%m/%Y}</b> até <b>{fim:%d/%m/%Y}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", normal,
    ))
    filtros_ativos = [f"<b>{escape(nome)}:</b> {escape(valor)}" for nome, valor in filtros.items() if valor]
    elementos.append(Paragraph(
        "Filtros: " + (" &nbsp;|&nbsp; ".join(filtros_ativos) if filtros_ativos else "nenhum filtro adicional"),
        normal,
    ))
    elementos.append(Spacer(1, 4 * mm))

    total = float(dados["valor_item"].sum())
    quantidade = float(dados["quantidade"].sum())
    indicadores = [
        ["Valor total", "Quantidade de produtos", "Valor unitário médio", "Produtos diferentes"],
        [_moeda(total), _numero(quantidade), _moeda(total / quantidade if quantidade else 0), str(dados["codigo_produto"].nunique())],
    ]
    elementos.append(_tabela(indicadores, [65.5 * mm] * 4, repetir=False))

    produtos = (
        dados.groupby(["codigo_produto", "produto"], dropna=False, as_index=False)
        .agg(quantidade=("quantidade", "sum"), valor=("valor_item", "sum"))
        .sort_values("valor", ascending=False)
        .head(10)
    )
    elementos.append(Paragraph("Top 10 valores por produto", secao))
    linhas_produtos: list[list[object]] = [["Código", "Produto", "Quantidade", "Valor total"]]
    for item in produtos.itertuples(index=False):
        linhas_produtos.append([
            _texto(item.codigo_produto), Paragraph(escape(_texto(item.produto)), pequeno),
            _numero(float(item.quantidade)), _moeda(float(item.valor)),
        ])
    elementos.append(_tabela(linhas_produtos, [24 * mm, 160 * mm, 35 * mm, 43 * mm]))

    lojas = (
        dados.groupby("local", dropna=False, as_index=False)
        .agg(quantidade=("quantidade", "sum"), valor=("valor_item", "sum"))
        .sort_values("valor", ascending=False)
    )
    elementos.append(Paragraph("Valores por loja", secao))
    linhas_lojas = [["Loja / local", "Quantidade", "Valor total"]]
    for item in lojas.itertuples(index=False):
        linhas_lojas.append([_texto(item.local), _numero(float(item.quantidade)), _moeda(float(item.valor))])
    elementos.append(_tabela(linhas_lojas, [120 * mm, 65 * mm, 77 * mm]))

    temporal = dados.dropna(subset=["emissao"]).copy()
    temporal["mês/ano"] = temporal["emissao"].dt.strftime("%m/%Y")
    temporal["ordem"] = temporal["emissao"].dt.to_period("M")
    meses = temporal.groupby(["ordem", "mês/ano"], as_index=False)["valor_item"].sum().sort_values("ordem")
    elementos.append(Paragraph("Valores por mês/ano", secao))
    linhas_meses = [["Mês/ano", "Valor total"]]
    for _, item in meses.iterrows():
        linhas_meses.append([item["mês/ano"], _moeda(float(item["valor_item"]))])
    elementos.append(_tabela(linhas_meses, [120 * mm, 142 * mm]))

    elementos.extend([PageBreak(), Paragraph("Todos os pedidos filtrados", secao)])
    linhas = [["Data", "Loja", "Pedido", "Código", "Produto", "Qtd.", "Valor unit.", "Valor item"]]
    ordenados = dados.sort_values(["produto", "emissao", "codigo_produto"], kind="stable")
    for item in ordenados.itertuples(index=False):
        emissao = item.emissao.strftime("%d/%m/%Y") if not pd.isna(item.emissao) else "-"
        linhas.append([
            emissao, _texto(item.local), _texto(item.pedido), _texto(item.codigo_produto),
            Paragraph(escape(_texto(item.produto)), pequeno), _numero(float(item.quantidade)),
            _moeda(float(item.valor_unitario)), _moeda(float(item.valor_item)),
        ])
    elementos.append(_tabela(
        linhas,
        [24 * mm, 25 * mm, 24 * mm, 22 * mm, 91 * mm, 18 * mm, 28 * mm, 30 * mm],
    ))

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7DDDF"))
        canvas.line(12 * mm, 10 * mm, 285 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#607D8B"))
        canvas.drawString(12 * mm, 6 * mm, "Rio de Una - Pedidos")
        canvas.drawRightString(285 * mm, 6 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()
