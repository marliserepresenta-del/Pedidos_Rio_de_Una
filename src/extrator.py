from __future__ import annotations

import hashlib
import re
from typing import BinaryIO, Iterable

import pandas as pd
import pdfplumber


COLUNAS_EXIBICAO = [
    "id_registro", "arquivo", "pagina", "fornecedor", "comprador", "empresa",
    "local", "pedido", "pedido_fornecedor", "emissao", "recebimento",
    "codigo_produto", "produto", "status", "unidade", "embalagem",
    "quantidade", "valor_item",
]


def numero_br(valor: str) -> float:
    return float(valor.strip().replace(".", "").replace(",", "."))


def limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


PADRAO_FORNECEDOR = re.compile(
    r"Fornecedor\s*:\s*(?:\d+)?(?P<fornecedor>.+?)\s+Comprador\s*:\s*(?P<comprador>.+)$",
    re.IGNORECASE,
)
PADRAO_EMPRESA = re.compile(
    r"Empresa\s+(?P<empresa>\d+)\s+(?P<local>\d{3}-[A-Z0-9]+)\s+Local\s+\S+\s+"
    r"Pedido\s+(?P<pedido>\d+)\s+Emiss[aã]o\s+(?P<emissao>\d{2}/\d{2}/\d{4})\s+"
    r"Recebto\s*(?P<recebimento>\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
PADRAO_PEDIDO_FORNECEDOR = re.compile(r"Pedido\s+Fornecedor\s+(?P<numero>\d+)", re.IGNORECASE)
PADRAO_PRODUTO = re.compile(
    r"^(?:A receber\s+)?(?P<codigo>\d{4,6})(?P<produto>.*?)\s+"
    r"(?P<status>[APCB])\s+(?P<unidade>[A-Z]{2,3})\s+"
    r"(?P<embalagem>\d+,\d{3})\s+(?P<quantidade>\d+,\d{2})\s+"
    r"(?P<valor>\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<restante>.*)$",
    re.IGNORECASE,
)
PADRAO_COMPLEMENTO = re.compile(
    r"(?:ORG\s+)?\d+(?:[.,]\d+)?\s*(?:G|KG|ML|L)", re.IGNORECASE
)
PREFIXOS_IGNORADOS = (
    "998 -", "PEDIDOS DE SUPRIMENTOS", "Cod Produto", "Tipo Tran", "Tipo C ",
    "Total ", "Peso total", "Volume Total", "Total Geral", "Status:", "TOTVS ",
)


def _id_registro(registro: dict) -> str:
    campos = (
        registro.get("empresa"), registro.get("pedido"), registro.get("pedido_fornecedor"),
        registro.get("codigo_produto"), registro.get("quantidade"), registro.get("valor_item"),
    )
    base = "|".join("" if valor is None else str(valor) for valor in campos)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]


def extrair_pdf(arquivo: BinaryIO, nome_arquivo: str) -> pd.DataFrame:
    registros: list[dict] = []
    contexto = dict.fromkeys(
        ["fornecedor", "comprador", "empresa", "local", "pedido", "emissao", "recebimento", "pedido_fornecedor"]
    )
    produto_pendente = None

    with pdfplumber.open(arquivo) as pdf:
        for pagina_numero, pagina in enumerate(pdf.pages, 1):
            texto = pagina.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for original in texto.splitlines():
                linha = limpar(original)
                if not linha:
                    continue
                achado = PADRAO_FORNECEDOR.search(linha)
                if achado:
                    contexto.update(achado.groupdict())
                    continue
                achado = PADRAO_EMPRESA.search(linha)
                if achado:
                    contexto.update(achado.groupdict())
                    continue
                achado = PADRAO_PEDIDO_FORNECEDOR.search(linha)
                if achado:
                    contexto["pedido_fornecedor"] = achado.group("numero")
                    continue
                achado = PADRAO_PRODUTO.match(linha)
                if achado:
                    item = achado.groupdict()
                    produto_pendente = {
                        **contexto, "arquivo": nome_arquivo, "pagina": pagina_numero,
                        "codigo_produto": item["codigo"], "produto": limpar(item["produto"]),
                        "status": item["status"].upper(), "unidade": item["unidade"].upper(),
                        "embalagem": numero_br(item["embalagem"]),
                        "quantidade": numero_br(item["quantidade"]),
                        "valor_item": numero_br(item["valor"]),
                    }
                    registros.append(produto_pendente)
                    continue
                if linha.startswith(PREFIXOS_IGNORADOS):
                    produto_pendente = None
                    continue
                if produto_pendente is not None and PADRAO_COMPLEMENTO.fullmatch(linha):
                    produto_pendente["produto"] = limpar(f"{produto_pendente['produto']} {linha}")

    if not registros:
        raise ValueError(f"Nenhum produto foi encontrado em {nome_arquivo}.")
    df = pd.DataFrame(registros)
    df["emissao"] = pd.to_datetime(df["emissao"], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df["recebimento"] = pd.to_datetime(df["recebimento"], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    df.insert(0, "id_registro", df.apply(lambda linha: _id_registro(linha.to_dict()), axis=1))
    return df[COLUNAS_EXIBICAO]


def extrair_varios_pdfs(arquivos: Iterable[BinaryIO]) -> tuple[pd.DataFrame, list[str]]:
    tabelas = []
    avisos = []
    for arquivo in arquivos:
        nome = getattr(arquivo, "name", "arquivo.pdf")
        try:
            if hasattr(arquivo, "seek"):
                arquivo.seek(0)
            tabelas.append(extrair_pdf(arquivo, nome))
        except Exception as erro:
            avisos.append(f"{nome}: {erro}")
    if not tabelas:
        raise ValueError("Nenhum item pôde ser extraído dos arquivos enviados.")
    combinado = pd.concat(tabelas, ignore_index=True)
    antes = len(combinado)
    combinado = combinado.drop_duplicates(subset=["id_registro"], keep="first")
    removidos = antes - len(combinado)
    if removidos:
        avisos.append(f"{removidos} item(ns) repetido(s) no lote foram removidos.")
    return combinado, avisos
