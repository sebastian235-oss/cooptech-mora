"""Importa Excel/CSV — scoring rápido con modelo de producción."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from app.config import settings
from app.ml import production_scorer
from app.ml.predictor import predict_dataframe, get_simple_predictor

# Límite para respuesta rápida en MVP (ajustable por env)
MAX_ROWS = int(getattr(settings, "max_upload_rows", 5000))

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

SIMPLE_FEATURE_ALIASES: dict[str, list[str]] = {
    "dias_atraso_promedio": ["dias_atraso_promedio", "dias_atraso", "max_dias_mora_actual"],
    "ratio_pago_cuota": ["ratio_pago_cuota", "ratio_pago"],
    "saldo_promedio_cuenta": ["saldo_promedio_cuenta", "saldo_promedio"],
    "variacion_saldo_30d": ["variacion_saldo_30d"],
    "num_movimientos_30d": ["num_movimientos_30d", "movimientos_30d"],
    "monto_pagos_30d": ["monto_pagos_30d"],
    "antiguedad_socio_meses": ["antiguedad_socio_meses"],
    "monto_credito": ["monto_credito", "monto_op"],
    "cuotas_pagadas": ["cuotas_pagadas"],
    "cuotas_totales": ["cuotas_totales"],
    "ingresos_estimados": ["ingresos_estimados", "ingresos_socio"],
    "gastos_estimados": ["gastos_estimados", "egresos_socio"],
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
        return pd.read_csv(bio)
    raise ValueError("Formato no soportado. Usa .xlsx, .xls o .csv")


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    # Quitar columnas de fuga que confunden al usuario pero no se usan en scoring
    drop = [c for c in df.columns if c in LEAKAGE_COLS]
    if drop:
        df = df.drop(columns=drop, errors="ignore")
    return df


def _has_cliente_id(df: pd.DataFrame) -> bool:
    return any(_norm_col(a) in df.columns for a in ID_ALIASES)


def _limit_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if len(df) <= MAX_ROWS:
        return df, 0
    return df.head(MAX_ROWS).copy(), len(df) - MAX_ROWS


def score_with_simple_model(df: pd.DataFrame) -> list[dict[str, Any]]:
    from uuid import uuid4

    predictor = get_simple_predictor()
    cols = list(df.columns)
    col_map: dict[str, str] = {}

    def pick(aliases: list[str]) -> str | None:
        for a in aliases:
            n = _norm_col(a)
            if n in cols:
                return n
        return None

    for feat, aliases in SIMPLE_FEATURE_ALIASES.items():
        c = pick(aliases)
        if c:
            col_map[feat] = c
    for target, aliases in [("cliente_id", ID_ALIASES)]:
        c = pick(aliases)
        if c:
            col_map[target] = c

    socios = []
    for idx, row in df.iterrows():
        features = {
            feat: float(row[src])
            for feat, src in col_map.items()
            if feat != "cliente_id" and pd.notna(row.get(src))
        }
        cid_col = col_map.get("cliente_id", "cliente_id")
        cid = str(row.get(cid_col, f"FILA-{idx + 2}")).strip()
        pred = predictor.predict_one(features)
        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": f"Socio {cid}",
                "agencia": None,
                "features": features,
                "prediccion": pred,
            }
        )
    return socios


def import_excel(content: bytes, filename: str) -> dict[str, Any]:
    df = _normalize_dataframe(_read_file(content, filename))
    if df.empty:
        raise ValueError("El archivo está vacío.")
    if not _has_cliente_id(df):
        raise ValueError("Incluye columna: cedula, cliente_id o nro_cliente.")

    truncated = 0
    df, truncated = _limit_rows(df)

    mode = "produccion" if production_scorer.production_available() else "simplificado"
    try:
        socios = predict_dataframe(df)
    except Exception as exc:
        if mode == "produccion":
            socios = score_with_simple_model(df)
            mode = "simplificado_respaldo"
        else:
            raise ValueError(f"Error en predicción: {exc}") from exc

    probs = [s["prediccion"]["probabilidad_mora"] for s in socios]
    msg_extra = f" (mostrando primeros {MAX_ROWS} de un archivo más grande)" if truncated else ""

    return {
        "mode": mode,
        "total": len(socios),
        "socios": socios,
        "columnas_detectadas": list(df.columns),
        "probabilidad_promedio": round(sum(probs) / len(probs), 4) if probs else 0,
        "modelo": socios[0]["prediccion"].get("modelo") if socios else None,
        "truncado": truncated,
        "mensaje_extra": msg_extra,
    }
