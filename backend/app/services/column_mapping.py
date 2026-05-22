"""Mapeo tabla maestra de mora → columnas del modelo."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

TABLA_MAESTRA_ALIASES: dict[str, str] = {
    "codigo_cliente": "nro_cliente",
    "cod_cliente": "nro_cliente",
    "id_cliente": "nro_cliente",
    "cliente": "nro_cliente",
    "nro_socio": "nro_cliente",
    "identificacion": "cedula",
    "cedula_socio": "cedula",
    "nombres": "nombre",
    "nombre_socio": "nombre",
    "nombre_cliente": "nombre",
    "dias_mora": "dias_desde_ultimo_pago_max",
    "dias_de_mora": "dias_desde_ultimo_pago_max",
    "dias_atraso": "dias_atraso_promedio",
    "dias_atrasados": "dias_atraso_promedio",
    "saldo_vencido": "saldo_vencido_actual_total",
    "saldo_vencido_total": "saldo_vencido_actual_total",
    "saldo_mora": "saldo_vencido_actual_total",
    "ingreso": "ingresos_socio",
    "ingresos": "ingresos_socio",
    "egreso": "egresos_socio",
    "egresos": "egresos_socio",
    "cuotas_atrasadas": "hist_cuotas_atrasadas_max",
    "nro_cuotas_atrasadas": "hist_cuotas_atrasadas_max",
    "variacion_saldo": "variacion_saldo_30d",
    "ratio_pago": "ratio_pago_cuota",
}

LEAKAGE_ONLY = {
    "target_mora_futura",
    "target_mora",
    "mora_actual",
    "max_dias_mora_actual",
    "dias_mora_futuro",
    "saldo_vencido_futuro",
}


def norm_col(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"[^a-z0-9_]", "", s)


def norm_cliente_id(value) -> str:
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        s = s[:-2]
    return s


def enrich_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ingresos_socio" in out.columns and "egresos_socio" in out.columns:
        ing = pd.to_numeric(out["ingresos_socio"], errors="coerce")
        egr = pd.to_numeric(out["egresos_socio"], errors="coerce")
        if "ratio_egresos_ingresos" not in out.columns:
            out["ratio_egresos_ingresos"] = (egr / ing.replace(0, np.nan)).fillna(0)
        if "capacidad_pago" not in out.columns:
            out["capacidad_pago"] = (ing - egr).fillna(0)
    return out


def apply_tabla_maestra_aliases(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    out.columns = [norm_col(c) for c in out.columns]
    messages: list[str] = []
    renames: dict[str, str] = {}
    for col in list(out.columns):
        target = TABLA_MAESTRA_ALIASES.get(col)
        if target and target != col and target not in out.columns:
            renames[col] = target
            messages.append(f"{col} → {target}")
    if renames:
        out = out.rename(columns=renames)
    out = out.loc[:, ~out.columns.duplicated()]
    out = enrich_derived_columns(out)
    drop = [c for c in out.columns if c in LEAKAGE_ONLY]
    if drop:
        out = out.drop(columns=drop, errors="ignore")
    return out, messages


def extract_features_row(row: pd.Series) -> dict[str, float]:
    skip = {"cliente_id", "nombre", "agencia", "sucursal", "oficina"}
    feats: dict[str, float] = {}
    for col in row.index:
        if col in skip or str(col).startswith("target"):
            continue
        val = row[col]
        if pd.notna(val) and isinstance(val, (int, float, np.integer, np.floating)):
            feats[str(col)] = float(val)
    return feats


def heuristic_probability(feats: dict[str, float]) -> float:
    """Estimación cuando el modelo ML recibe datos incompletos (tabla maestra)."""
    dias = feats.get("dias_desde_ultimo_pago_max") or feats.get("dias_atraso_promedio") or 0
    saldo = feats.get("saldo_vencido_actual_total") or 0
    cuotas = feats.get("hist_cuotas_atrasadas_max") or 0
    ratio_egr = feats.get("ratio_egresos_ingresos") or 0
    ratio_pago = feats.get("ratio_pago_cuota") or 1.0

    score = 0.0
    if dias > 0:
        score += min(0.4, dias / 90.0)
    if saldo > 0:
        score += min(0.3, saldo / 12000.0)
    if cuotas > 0:
        score += min(0.2, cuotas / 6.0)
    if ratio_egr > 0.85:
        score += 0.12
    if ratio_pago < 0.75:
        score += 0.1
    return min(0.85, score)


def nivel_from_features(prob_model: float, feats: dict[str, float], umbral_f1: float, umbral_alto: float) -> str:
    prob = max(prob_model, heuristic_probability(feats))
    if prob >= umbral_alto:
        return "alto"
    if prob >= umbral_f1:
        return "medio"
    if prob >= 0.12:
        return "medio"
    dias = feats.get("dias_desde_ultimo_pago_max") or feats.get("dias_atraso_promedio") or 0
    saldo = feats.get("saldo_vencido_actual_total") or 0
    if dias >= 45 or saldo >= 2500:
        return "alto"
    if dias >= 8 or saldo > 0:
        return "medio"
    return "bajo"
