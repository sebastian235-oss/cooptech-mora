"""Scoring exclusivo con modelo_mora_futura.pkl (carpeta modelo_mora_produccion)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_DIR = settings.model_dir
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

_prod_instance = None
_prod_error: str | None = None

PRODUCTION_MODEL_FILE = "modelo_mora_futura.pkl"


def _nivel_from_prob(prob: float, umbral_f1: float, umbral_alto: float) -> str:
    if prob >= umbral_alto:
        return "alto"
    if prob >= umbral_f1:
        return "medio"
    if prob >= 0.2:
        return "medio"
    return "bajo"


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
    out["cliente_id"] = out["cliente_id"].astype(str).str.strip()
    return out


def score_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    prod = get_production_predictor()
    if prod is None:
        raise RuntimeError(production_error() or "Modelo no disponible")

    raw = _ensure_cliente_id(df)
    raw = raw.drop_duplicates(subset=["cliente_id"], keep="last").reset_index(drop=True)

    scored = prod.score(raw)
    n = len(scored)
    if n == 0:
        return []

    name_col = next(
        (c for c in ("nombre", "nombre_socio", "nombre_cliente", "socio") if c in scored.columns),
        None,
    )
    if not name_col:
        name_col = next(
            (c for c in ("nombre", "nombre_socio", "nombre_cliente", "socio") if c in raw.columns),
            None,
        )
    agency_col = next(
        (c for c in ("agencia", "sucursal", "oficina") if c in scored.columns or c in raw.columns),
        None,
    )

    if name_col and name_col not in scored.columns and name_col in raw.columns:
        scored = scored.merge(
            raw[["cliente_id", name_col]].drop_duplicates("cliente_id"),
            on="cliente_id",
            how="left",
        )
    if agency_col and agency_col not in scored.columns and agency_col in raw.columns:
        scored = scored.merge(
            raw[["cliente_id", agency_col]].drop_duplicates("cliente_id"),
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
    agencias = (
        scored[agency_col].astype(str).values
        if agency_col and agency_col in scored.columns
        else [None] * n
    )

    umbral_f1, umbral_alto = prod.umbral_f1, prod.umbral_alto
    socios: list[dict[str, Any]] = []
    for i in range(n):
        prob = float(probs[i])
        ag = agencias[i]
        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cids[i],
                "nombre": nombres[i] if nombres[i] and nombres[i] != "nan" else f"Socio {cids[i]}",
                "agencia": ag if ag and ag != "nan" else None,
                "features": {},
                "prediccion": {
                    "probabilidad_mora": round(prob, 4),
                    "nivel_riesgo": _nivel_from_prob(prob, umbral_f1, umbral_alto),
                    "nivel_label": niveles_lbl[i],
                    "accion": acciones[i],
                    "modelo": PRODUCTION_MODEL_FILE,
                },
            }
        )
    return socios
