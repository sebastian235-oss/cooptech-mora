"""Importa Excel/CSV y puntúa solo con modelo_mora_produccion."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from app.config import settings
from app.ml import production_scorer
from app.ml.predictor import predict_dataframe
from app.services.column_mapping import apply_tabla_maestra_aliases

ID_ALIASES = [
    "cliente_id",
    "nro_cliente",
    "cedula",
    "id_cliente",
    "socio_id",
    "id_socio",
    "codigo_cliente",
]


def _norm_col(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"[^a-z0-9_]", "", s)


def _read_file(content: bytes, filename: str) -> pd.DataFrame:
    bio = BytesIO(content)
    low = filename.lower()
    if low.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(bio, engine="openpyxl")
    if low.endswith(".csv"):
        return pd.read_csv(bio, low_memory=False)
    raise ValueError("Formato no soportado. Usa .xlsx, .xls o .csv")


def _has_cliente_id(df: pd.DataFrame) -> bool:
    return any(_norm_col(a) in df.columns for a in ID_ALIASES)


def _apply_row_cap(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cap = settings.max_upload_rows
    if cap <= 0 or len(df) <= cap:
        return df, 0
    return df.iloc[:cap].copy(), len(df) - cap


def import_excel(content: bytes, filename: str) -> dict[str, Any]:
    if not production_scorer.production_available():
        raise ValueError(
            f"No se pudo cargar el modelo entrenado: {production_scorer.production_error()}. "
            "Copia tu carpeta modelo_mora_produccion/ completa al proyecto."
        )

    df, alias_msgs = apply_tabla_maestra_aliases(_read_file(content, filename))
    if df.empty:
        raise ValueError("El archivo está vacío.")
    if not _has_cliente_id(df):
        raise ValueError("Incluye columna: cedula, cliente_id o nro_cliente.")

    total_filas_archivo = len(df)
    df, truncated = _apply_row_cap(df)

    socios = predict_dataframe(df)
    probs = [s["prediccion"]["probabilidad_mora"] for s in socios]
    niveles = [s["prediccion"]["nivel_riesgo"] for s in socios]

    msg_extra = ""
    if truncated:
        msg_extra = f" Se procesaron {len(socios)} de {total_filas_archivo} filas (límite {settings.max_upload_rows})."
    if alias_msgs:
        msg_extra += f" Columnas mapeadas: {', '.join(alias_msgs[:5])}."
    if niveles.count("bajo") == len(niveles) and len(niveles) > 0:
        msg_extra += (
            " Si todo sale 'bajo', verifica que el Excel tenga DIAS_MORA/SALDO_VENCIDO "
            "o usa el dataset completo de prevención."
        )

    return {
        "mode": "modelo_mora_produccion",
        "total": len(socios),
        "total_archivo": total_filas_archivo,
        "socios": socios,
        "columnas_detectadas": list(df.columns),
        "columnas_mapeadas": alias_msgs,
        "probabilidad_promedio": round(sum(probs) / len(probs), 4) if probs else 0,
        "modelo": "modelo_mora_futura.pkl",
        "truncado": truncated,
        "mensaje_extra": msg_extra,
    }
