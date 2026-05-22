"""Scoring exclusivo con modelo_mora_futura.pkl (carpeta modelo_mora_produccion)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.config import settings
from app.ml.signals_builder import build_risk_signals, enrich_features_from_xt

logger = logging.getLogger(__name__)

MODEL_DIR = settings.model_dir
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

_prod_instance = None
_prod_error: str | None = None

PRODUCTION_MODEL_FILE = "modelo_mora_futura.pkl"

# Columnas prioritarias para señales en UI (se añaden todas las numéricas del Excel)
SIGNAL_KEYS = (
    "variacion_saldo_30d",
    "variacion_saldo",
    "variacion_movimientos_30d",
    "variacion_movimientos",
    "pct_var_movimientos",
    "num_movimientos_30d",
    "dias_desde_ultimo_pago_max",
    "dias_desde_ultimo_pago_prom",
    "dias_atraso_promedio",
    "max_dias_mora_actual",
    "ratio_pago_cuota",
    "ratio_egresos_ingresos",
    "saldo_vencido_actual_total",
    "capacidad_pago",
    "ingresos_socio",
    "egresos_socio",
    "xt_n_operaciones",
    "hist_cuotas_atrasadas_max",
    "hist_cuotas_atrasadas_total",
    "saldo_promedio_cuenta",
    "n_creditos_unicos",
)

SIGNAL_ALIASES: dict[str, tuple[str, ...]] = {
    "variacion_saldo_30d": ("var_saldo_30d", "pct_saldo_30d", "variacion_saldo"),
    "variacion_movimientos_30d": (
        "variacion_movimientos",
        "pct_var_movimientos",
        "var_movimientos_30d",
    ),
    "dias_desde_ultimo_pago_max": (
        "dias_atraso_promedio",
        "dias_atraso",
        "dias_mora",
        "max_dias_mora",
    ),
    "num_movimientos_30d": ("n_movimientos_30d", "movimientos_30d"),
}

SKIP_SIGNAL_COLS = {
    "cliente_id",
    "fecha_corte",
    "fecha_objetivo",
    "target_mora_futura",
    "target_mora",
    "mora_actual",
    "max_dias_mora_actual",
    "dias_mora_futuro",
    "saldo_vencido_futuro",
}


def _norm_cliente_id(value: Any) -> str:
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        s = s[:-2]
    return s


def _nivel_from_label(label: str, prob: float, umbral_f1: float, umbral_alto: float) -> str:
    low = (label or "").lower()
    if "muy alto" in low or prob >= umbral_alto:
        return "alto"
    if low == "alto" or prob >= umbral_f1:
        return "alto" if prob >= umbral_alto else "medio"
    if "medio" in low and prob >= 0.2:
        return "medio"
    return "bajo"


def _canonicalize_features(feats: dict[str, float]) -> dict[str, float]:
    out = dict(feats)
    for canonical, aliases in SIGNAL_ALIASES.items():
        if canonical in out:
            continue
        for alias in aliases:
            if alias in out:
                out[canonical] = out[alias]
                break
    return out


def get_production_predictor():
    global _prod_instance, _prod_error
    if _prod_instance is not None:
        return _prod_instance
    model_path = MODEL_DIR / PRODUCTION_MODEL_FILE
    if not model_path.exists():
        _prod_error = (
            f"Falta {PRODUCTION_MODEL_FILE}. Copia tu carpeta entrenada "
            f"modelo_mora_produccion/ al proyecto (debe incluir .pkl y config.json)."
        )
        return None
    try:
        from predict import MoraPredictor  # noqa: PLC0415

        _prod_instance = MoraPredictor(model_path=model_path)
        _prod_error = None
        logger.info(
            "Modelo activo: %s (%d features)",
            PRODUCTION_MODEL_FILE,
            len(_prod_instance.features),
        )
        return _prod_instance
    except Exception as exc:
        _prod_error = str(exc)
        logger.exception("Error cargando modelo: %s", exc)
        return None


def production_available() -> bool:
    return get_production_predictor() is not None


def production_error() -> str | None:
    get_production_predictor()
    return _prod_error


def _ensure_cliente_id(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "cliente_id" not in out.columns:
        for alias in ("nro_cliente", "cedula", "id_cliente", "socio_id"):
            if alias in out.columns:
                out = out.rename(columns={alias: "cliente_id"})
                break
    if "cliente_id" not in out.columns:
        raise ValueError("Falta columna: cedula, cliente_id o nro_cliente.")
    out["cliente_id"] = out["cliente_id"].map(_norm_cliente_id)
    return out


def _extract_signal_features(raw: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Toma todas las columnas numéricas útiles del Excel para las señales en UI."""
    work = raw.copy()
    work["cliente_id"] = work["cliente_id"].map(_norm_cliente_id)
    numeric_cols = [
        c
        for c in work.select_dtypes(include=[np.number]).columns
        if c not in SKIP_SIGNAL_COLS and not str(c).startswith("target")
    ]
    # Priorizar columnas conocidas + resto numéricas (máx. 40 por socio)
    ordered = [c for c in SIGNAL_KEYS if c in numeric_cols]
    ordered += [c for c in numeric_cols if c not in ordered][: max(0, 40 - len(ordered))]

    sub = work[["cliente_id", *ordered]].drop_duplicates("cliente_id", keep="last")
    result: dict[str, dict[str, float]] = {}
    for row in sub.itertuples(index=False):
        cid = _norm_cliente_id(row[0])
        feats: dict[str, float] = {}
        for col, val in zip(ordered, row[1:], strict=False):
            if pd.notna(val):
                try:
                    feats[col] = float(val)
                except (TypeError, ValueError):
                    pass
        if feats:
            result[cid] = _canonicalize_features(feats)
        else:
            result[cid] = {}
    return result



def score_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    prod = get_production_predictor()
    if prod is None:
        raise RuntimeError(production_error() or "Modelo no disponible")

    raw = _ensure_cliente_id(df)
    raw = raw.drop_duplicates(subset=["cliente_id"], keep="last").reset_index(drop=True)
    feat_by_id = _extract_signal_features(raw)

    scored = prod.score(raw)
    n = len(scored)
    if n == 0:
        return []

    scored["cliente_id"] = scored["cliente_id"].map(_norm_cliente_id)

    name_col = next(
        (c for c in ("nombre", "nombre_socio", "nombre_cliente", "socio") if c in scored.columns),
        None,
    )
    if not name_col:
        name_col = next(
            (c for c in ("nombre", "nombre_socio", "nombre_cliente", "socio") if c in raw.columns),
            None,
        )
    if name_col and name_col not in scored.columns and name_col in raw.columns:
        scored = scored.merge(
            raw[["cliente_id", name_col]].drop_duplicates("cliente_id"),
            on="cliente_id",
            how="left",
        )

    cids = scored["cliente_id"].astype(str).values
    probs = scored["prob_mora_futura"].astype(float).values
    niveles_lbl = scored["nivel_riesgo"].astype(str).values
    acciones = scored["accion"].astype(str).values
    nombres = (
        scored[name_col].astype(str).values
        if name_col and name_col in scored.columns
        else [f"Socio {c}" for c in cids]
    )

    umbral_f1, umbral_alto = prod.umbral_f1, prod.umbral_alto
    socios: list[dict[str, Any]] = []
    for i in range(n):
        cid = _norm_cliente_id(cids[i])
        prob = float(probs[i])
        nombre = nombres[i]
        if not nombre or nombre == "nan":
            nombre = f"Socio {cid}"
        feats = enrich_features_from_xt(
            cid, feat_by_id.get(cid, {}), prod._xt_agg
        )
        senales = build_risk_signals(feats)
        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": nombre,
                "features": feats,
                "prediccion": {
                    "probabilidad_mora": round(prob, 6),
                    "nivel_riesgo": _nivel_from_label(niveles_lbl[i], prob, umbral_f1, umbral_alto),
                    "nivel_label": niveles_lbl[i],
                    "accion": acciones[i],
                    "modelo": PRODUCTION_MODEL_FILE,
                    "features_usadas": feats,
                    "senales": senales,
                },
            }
        )

    return socios
