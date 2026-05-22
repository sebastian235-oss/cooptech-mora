"""Importa Excel/CSV y puntúa con modelo de producción."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from app.ml import production_scorer
from app.ml.predictor import predict_dataframe, get_simple_predictor

ID_ALIASES = ["cliente_id", "nro_cliente", "cedula", "id_cliente", "socio_id", "id_socio"]
NAME_ALIASES = ["nombre", "nombre_socio", "nombre_cliente", "socio", "cliente"]
AGENCY_ALIASES = ["agencia", "sucursal", "oficina", "agencia_nombre"]

SIMPLE_FEATURE_ALIASES: dict[str, list[str]] = {
    "dias_atraso_promedio": ["dias_atraso_promedio", "dias_atraso", "max_dias_mora_actual"],
    "ratio_pago_cuota": ["ratio_pago_cuota", "ratio_pago"],
    "saldo_promedio_cuenta": ["saldo_promedio_cuenta", "saldo_promedio", "saldo_cuenta"],
    "variacion_saldo_30d": ["variacion_saldo_30d", "variacion_saldo"],
    "num_movimientos_30d": ["num_movimientos_30d", "movimientos_30d"],
    "monto_pagos_30d": ["monto_pagos_30d", "pagos_30d"],
    "antiguedad_socio_meses": ["antiguedad_socio_meses", "antiguedad_meses"],
    "monto_credito": ["monto_credito", "monto_op", "saldo_total"],
    "cuotas_pagadas": ["cuotas_pagadas", "n_cuotas_pagadas"],
    "cuotas_totales": ["cuotas_totales", "plazo_meses"],
    "ingresos_estimados": ["ingresos_estimados", "ingresos_socio", "ingresos"],
    "gastos_estimados": ["gastos_estimados", "egresos_socio", "egresos"],
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
    return df


def _has_cliente_id(df: pd.DataFrame) -> bool:
    return any(_norm_col(a) in df.columns for a in ID_ALIASES)


def score_with_simple_model(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Respaldo con modelo demo de 12 variables."""
    from uuid import uuid4

    predictor = get_simple_predictor()
    col_map: dict[str, str] = {}
    cols = list(df.columns)

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
    for target, aliases in [
        ("cliente_id", ID_ALIASES),
        ("nombre", NAME_ALIASES),
        ("agencia", AGENCY_ALIASES),
    ]:
        c = pick(aliases)
        if c:
            col_map[target] = c

    socios = []
    for idx, row in df.iterrows():
        features = {}
        for feat, src in col_map.items():
            if feat in ("cliente_id", "nombre", "agencia"):
                continue
            val = row.get(src)
            if pd.notna(val):
                try:
                    features[feat] = float(val)
                except (TypeError, ValueError):
                    pass
        cid_col = col_map.get("cliente_id")
        cid = (
            str(row[cid_col]).strip()
            if cid_col and pd.notna(row.get(cid_col))
            else f"FILA-{idx + 2}"
        )
        name_col = col_map.get("nombre")
        nombre = (
            str(row[name_col]).strip()
            if name_col and pd.notna(row.get(name_col))
            else f"Socio {cid}"
        )
        ag_col = col_map.get("agencia")
        agencia = (
            str(row[ag_col]).strip() if ag_col and pd.notna(row.get(ag_col)) else None
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
    df = _normalize_dataframe(_read_file(content, filename))
    if df.empty:
        raise ValueError("El archivo está vacío.")

    if not _has_cliente_id(df):
        raise ValueError(
            "El Excel debe incluir columna de identificación: "
            "cedula, cliente_id o nro_cliente."
        )

    mode = "produccion" if production_scorer.production_available() else "simplificado"
    try:
        socios = predict_dataframe(df)
    except Exception as exc:
        if mode == "produccion":
            socios = score_with_simple_model(df)
            mode = "simplificado_respaldo"
        else:
            raise ValueError(f"Error al calcular predicciones: {exc}") from exc

    probs = [s["prediccion"]["probabilidad_mora"] for s in socios]
    return {
        "mode": mode,
        "total": len(socios),
        "socios": socios,
        "columnas_detectadas": list(df.columns),
        "probabilidad_promedio": round(sum(probs) / len(probs), 4) if probs else 0,
        "modelo": socios[0]["prediccion"].get("modelo") if socios else None,
    }
