from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
from google.oauth2.credentials import Credentials

from src.extrator import COLUNAS_EXIBICAO


@dataclass(frozen=True)
class ResultadoCriacao:
    nome: str
    url: str
    itens: int


def _nome_usuario(email: str) -> str:
    nome = email.split("@", 1)[0]
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or "usuario"


def criar_planilha_do_envio(
    df: pd.DataFrame,
    dados_credenciais: dict,
    email_usuario: str,
) -> ResultadoCriacao:
    credenciais = Credentials(**dados_credenciais)
    cliente = gspread.authorize(credenciais)
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    nome = f"Pedidos_{agora:%Y-%m-%d_%H-%M}_{_nome_usuario(email_usuario)}"
    planilha = cliente.create(nome)
    aba = planilha.sheet1
    aba.update_title("Itens")

    tabela = df[COLUNAS_EXIBICAO].drop_duplicates(subset=["id_registro"]).fillna("")
    valores = [COLUNAS_EXIBICAO] + tabela.astype(object).values.tolist()
    aba.update(range_name="A1", values=valores, value_input_option="USER_ENTERED")
    aba.freeze(rows=1)
    aba.set_basic_filter()
    aba.resize(rows=max(len(valores) + 20, 100), cols=len(COLUNAS_EXIBICAO))
    return ResultadoCriacao(nome=nome, url=planilha.url, itens=len(tabela))
