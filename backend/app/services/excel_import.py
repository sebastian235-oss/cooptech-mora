"""Importa Excel/CSV y puntúa solo con modelo_mora_produccion."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from app.config import settings
from app.ml import production_scorer
from app.ml.predictor import predict_dataframe

ID_ALIASES = ["cliente_id", "nro_cliente", "cedula", "id_cliente", "socio_id", "id_socio"]
LEAKAGE_COLS = {
    "mora_actual",
    "max_dias_mora_actual",
    "dias_mora_futuro",
    "saldo_vencido_futuro",
    "target_mora_futura",
    "target_mora",
    "dias_mora",
    "saldo_vencido",
}


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


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    drop = [c for c in df.columns if c in LEAKAGE_COLS]
    if drop:
        df = df.drop(columns=drop, errors="ignore")
    return df


def _has_cliente_id(df: pd.DataFrame) -> bool:
    return any(_norm_col(a) in df.columns for a in ID_ALIASES)


def _apply_row_cap(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """0 = sin límite. Valor positivo = tope de seguridad."""
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

    df = _normalize_dataframe(_read_file(content, filename))
    if df.empty:
        raise ValueError("El archivo está vacío.")
    if not _has_cliente_id(df):
        raise ValueError("Incluye columna: cedula, cliente_id o nro_cliente.")

    total_filas_archivo = len(df)
    df, truncated = _apply_row_cap(df)

    socios = predict_dataframe(df)
    probs = [s["prediccion"]["probabilidad_mora"] for s in socios]
    coverages = [s["prediccion"].get("feature_coverage", 0) for s in socios]
    avg_cov = sum(coverages) / len(coverages) if coverages else 0
    schema_hint = ""
    if avg_cov < 0.35:
        schema_hint = (
            " Advertencia: el archivo tiene pocas columnas del dataset de prevención "
            "(cobertura media {:.0%}). Para probabilidades fiables use "
            "dataset_entrenamiento_prevencion.csv o coloque ese CSV junto al modelo."
        ).format(avg_cov)

    msg_extra = ""
    if truncated:
        msg_extra = f" Se procesaron {len(socios)} de {total_filas_archivo} filas (límite {settings.max_upload_rows})."

    return {
        "mode": "modelo_mora_produccion",
        "total": len(socios),
        "total_archivo": total_filas_archivo,
        "socios": socios,
        "columnas_detectadas": list(df.columns),
        "probabilidad_promedio": round(sum(probs) / len(probs), 4) if probs else 0,
        "modelo": "modelo_mora_futura.pkl",
        "truncado": truncated,
        "mensaje_extra": msg_extra + schema_hint,
        "cobertura_features_promedio": round(avg_cov, 4),
    }
