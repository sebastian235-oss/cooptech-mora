"""Importa Excel/CSV de socios y genera predicciones."""

from __future__ import annotations

import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.config import settings
from app.ml.predictor import get_predictor

MODEL_DIR = settings.model_dir
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

FEATURE_ALIASES: dict[str, list[str]] = {
    "dias_atraso_promedio": [
        "dias_atraso_promedio",
        "dias_atraso",
        "max_dias_mora_actual",
        "dias_desde_ultimo_pago_max",
    ],
    "ratio_pago_cuota": ["ratio_pago_cuota", "ratio_pago", "pct_pago_cuota"],
    "saldo_promedio_cuenta": [
        "saldo_promedio_cuenta",
        "saldo_promedio",
        "saldo_cuenta",
        "xt_saldo_promedio",
    ],
    "variacion_saldo_30d": ["variacion_saldo_30d", "variacion_saldo", "var_saldo_30d"],
    "num_movimientos_30d": [
        "num_movimientos_30d",
        "movimientos_30d",
        "n_movimientos",
        "xt_n_operaciones",
    ],
    "monto_pagos_30d": ["monto_pagos_30d", "pagos_30d", "monto_pagos"],
    "antiguedad_socio_meses": [
        "antiguedad_socio_meses",
        "antiguedad_meses",
        "meses_socio",
    ],
    "monto_credito": ["monto_credito", "monto_op", "val_credito", "saldo_total"],
    "cuotas_pagadas": ["cuotas_pagadas", "cuotas_pag", "n_cuotas_pagadas"],
    "cuotas_totales": ["cuotas_totales", "plazo_meses", "n_cuotas"],
    "ingresos_estimados": [
        "ingresos_estimados",
        "ingresos_socio",
        "ingresos",
        "total_ingresos",
    ],
    "gastos_estimados": [
        "gastos_estimados",
        "egresos_socio",
        "egresos",
        "total_egresos",
    ],
}

ID_ALIASES = ["cliente_id", "nro_cliente", "cedula", "id_cliente", "socio_id", "id_socio"]
NAME_ALIASES = ["nombre", "nombre_socio", "nombre_cliente", "socio", "cliente"]
AGENCY_ALIASES = ["agencia", "sucursal", "oficina", "agencia_nombre"]


def _norm_col(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def _build_col_map(columns: list[str]) -> dict[str, str]:
    normalized = {_norm_col(c): c for c in columns}
    mapping: dict[str, str] = {}

    def pick(aliases: list[str]) -> str | None:
        for alias in aliases:
            key = _norm_col(alias)
            if key in normalized:
                return normalized[key]
        return None

    for feature, aliases in FEATURE_ALIASES.items():
        col = pick(aliases)
        if col:
            mapping[feature] = col

    for target, aliases in [
        ("cliente_id", ID_ALIASES),
        ("nombre", NAME_ALIASES),
        ("agencia", AGENCY_ALIASES),
    ]:
        col = pick(aliases)
        if col:
            mapping[target] = col

    return mapping


def _read_file(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    bio = BytesIO(content)
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(bio, engine="openpyxl")
    if name.endswith(".csv"):
        return pd.read_csv(bio)
    raise ValueError("Formato no soportado. Usa .xlsx, .xls o .csv")


def _nivel_simple(prob: float) -> str:
    if prob >= 0.65:
        return "alto"
    if prob >= 0.35:
        return "medio"
    return "bajo"


def _nivel_from_label(label: str, prob: float) -> str:
    low = str(label).lower()
    if "muy" in low and "alto" in low:
        return "alto"
    if "alto" in low:
        return "alto" if prob >= 0.5 else "medio"
    if "medio" in low:
        return "medio"
    return "bajo"


def _try_production_score(df: pd.DataFrame) -> list[dict[str, Any]] | None:
    model_path = MODEL_DIR / "modelo_mora_futura.pkl"
    if not model_path.exists():
        return None
    if "cliente_id" not in df.columns:
        for alias in ("nro_cliente", "cedula", "id_cliente", "socio_id"):
            if alias in df.columns:
                df = df.rename(columns={alias: "cliente_id"})
                break
    if "cliente_id" not in df.columns:
        return None
    try:
        from predict import MoraPredictor as ProdPredictor  # noqa: PLC0415

        prod = ProdPredictor()
        scored = prod.score(df)
        socios: list[dict[str, Any]] = []
        for _, row in scored.iterrows():
            prob = float(row["prob_mora_futura"])
            nivel_label = str(row.get("nivel_riesgo", ""))
            cid = str(row.get("cliente_id", uuid4()))
            socios.append(
                {
                    "id": str(uuid4()),
                    "cedula": cid,
                    "nombre": f"Socio {cid}",
                    "agencia": None,
                    "features": {},
                    "prediccion": {
                        "probabilidad_mora": round(prob, 4),
                        "nivel_riesgo": _nivel_from_label(nivel_label, prob),
                        "accion": str(row.get("accion", "")),
                        "nivel_label": nivel_label,
                    },
                }
            )
        return socios
    except Exception:
        return None


def _score_simple_rows(df: pd.DataFrame, col_map: dict[str, str]) -> list[dict[str, Any]]:
    predictor = get_predictor()
    socios: list[dict[str, Any]] = []

    id_col = col_map.get("cliente_id")
    name_col = col_map.get("nombre")
    agency_col = col_map.get("agencia")

    for idx, row in df.iterrows():
        features: dict[str, float] = {}
        for feat, src_col in col_map.items():
            if feat in ("cliente_id", "nombre", "agencia"):
                continue
            val = row.get(src_col)
            if pd.notna(val):
                try:
                    features[feat] = float(val)
                except (TypeError, ValueError):
                    pass

        cid = (
            str(row[id_col]).strip()
            if id_col and pd.notna(row.get(id_col))
            else f"FILA-{idx + 2}"
        )
        nombre = (
            str(row[name_col]).strip()
            if name_col and pd.notna(row.get(name_col))
            else f"Socio {cid}"
        )
        agencia = (
            str(row[agency_col]).strip()
            if agency_col and pd.notna(row.get(agency_col))
            else None
        )

        pred = predictor.predict_one(features)
        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": nombre,
                "agencia": agencia,
                "features": features,
                "prediccion": pred,
            }
        )
    return socios


def import_excel(content: bytes, filename: str) -> dict[str, Any]:
    df = _read_file(content, filename)
    if df.empty:
        raise ValueError("El archivo está vacío.")

    df.columns = [_norm_col(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]

    prod = _try_production_score(df)
    if prod:
        return {
            "mode": "produccion",
            "total": len(prod),
            "socios": prod,
            "columnas_detectadas": list(df.columns),
        }

    col_map = _build_col_map(list(df.columns))
    if not any(k in col_map for k in FEATURE_ALIASES):
        raise ValueError(
            "No se reconocieron columnas de features. "
            "Incluye al menos: cliente_id/cedula y variables como dias_atraso, "
            "ratio_pago_cuota, saldo_promedio, etc."
        )

    socios = _score_simple_rows(df, col_map)
    return {
        "mode": "simplificado",
        "total": len(socios),
        "socios": socios,
        "columnas_mapeadas": {k: v for k, v in col_map.items()},
        "columnas_detectadas": list(df.columns),
    }
