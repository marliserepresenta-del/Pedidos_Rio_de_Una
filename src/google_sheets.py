from __future__ import annotations

from dataclasses import dataclass

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from src.extrator import COLUNAS_EXIBICAO


@dataclass(frozen=True)
class ConfigPlanilha:
    nome_planilha: str
    nome_aba: str
    credenciais: dict


@dataclass(frozen=True)
class ResultadoEnvio:
    inseridos: int
    duplicados: int


def configurar_planilha(secrets) -> ConfigPlanilha:
    if "google_sheets" not in secrets or "gcp_service_account" not in secrets:
        raise ValueError(
            "Configure [google_sheets] e [gcp_service_account] no arquivo .streamlit/secrets.toml."
        )
    destino = dict(secrets["google_sheets"])
    return ConfigPlanilha(
        nome_planilha=destino["spreadsheet_name"],
        nome_aba=destino.get("worksheet_name", "Itens"),
        credenciais=dict(secrets["gcp_service_account"]),
    )


def _abrir_aba(config: ConfigPlanilha):
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credenciais = Credentials.from_service_account_info(config.credenciais, scopes=escopos)
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open(config.nome_planilha)
    try:
        return planilha.worksheet(config.nome_aba)
    except gspread.WorksheetNotFound:
        return planilha.add_worksheet(title=config.nome_aba, rows=1000, cols=len(COLUNAS_EXIBICAO))


def enviar_sem_duplicar(df: pd.DataFrame, config: ConfigPlanilha) -> ResultadoEnvio:
    aba = _abrir_aba(config)
    valores = aba.get_all_values()
    if not valores:
        aba.append_row(COLUNAS_EXIBICAO, value_input_option="RAW")
        ids_existentes: set[str] = set()
    else:
        cabecalho = valores[0]
        if "id_registro" not in cabecalho:
            raise ValueError("A aba já existe, mas não possui a coluna id_registro.")
        indice = cabecalho.index("id_registro")
        ids_existentes = {linha[indice] for linha in valores[1:] if len(linha) > indice}

    novos = df.loc[~df["id_registro"].astype(str).isin(ids_existentes), COLUNAS_EXIBICAO].copy()
    novos = novos.fillna("")
    if not novos.empty:
        aba.append_rows(novos.astype(object).values.tolist(), value_input_option="USER_ENTERED")
    return ResultadoEnvio(inseridos=len(novos), duplicados=len(df) - len(novos))

