"""Integración con modelo_mora_produccion/predict.py (LightGBM mora futura)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_DIR = settings.model_dir
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

_prod_instance = None
_prod_error: str | None = None


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
    model_path = MODEL_DIR / "modelo_mora_futura.pkl"
    if not model_path.exists():
        _prod_error = "No existe modelo_mora_futura.pkl"
        return None
    try:
        from predict import MoraPredictor  # noqa: PLC0415

        _prod_instance = MoraPredictor()
        _prod_error = None
        logger.info("Modelo producción cargado (%s features)", len(_prod_instance.features))
        return _prod_instance
    except Exception as exc:
        _prod_error = str(exc)
        logger.exception("Error cargando modelo producción: %s", exc)
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
        out["cliente_id"] = [f"FILA-{i + 1}" for i in range(len(out))]
    out["cliente_id"] = out["cliente_id"].astype(str).str.strip()
    return out


def score_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    prod = get_production_predictor()
    if prod is None:
        raise RuntimeError(
            production_error() or "Modelo de producción no disponible"
        )

    raw = _ensure_cliente_id(df)
    name_col = next(
        (c for c in ("nombre", "nombre_socio", "nombre_cliente") if c in raw.columns),
        None,
    )
    agency_col = next((c for c in ("agencia", "sucursal", "oficina") if c in raw.columns), None)

    scored = prod.score(raw)
    socios: list[dict[str, Any]] = []

    for i, srow in scored.reset_index(drop=True).iterrows():
        cid = str(srow["cliente_id"])
        orig = raw[raw["cliente_id"] == cid]
        orow = orig.iloc[0] if len(orig) else raw.iloc[i] if i < len(raw) else raw.iloc[0]

        nombre = (
            str(orow[name_col]).strip()
            if name_col and pd.notna(orow.get(name_col))
            else f"Socio {cid}"
        )
        agencia = (
            str(orow[agency_col]).strip()
            if agency_col and pd.notna(orow.get(agency_col))
            else None
        )

        prob = float(srow["prob_mora_futura"])
        features = {}
        for col in raw.columns:
            if col in ("cliente_id", name_col, agency_col):
                continue
            val = orow.get(col)
            if pd.notna(val):
                try:
                    features[col] = float(val)
                except (TypeError, ValueError):
                    pass

        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": nombre,
                "agencia": agencia,
                "features": features,
                "prediccion": {
                    "probabilidad_mora": round(prob, 4),
                    "nivel_riesgo": _nivel_from_prob(
                        prob, prod.umbral_f1, prod.umbral_alto
                    ),
                    "nivel_label": str(srow.get("nivel_riesgo", "")),
                    "accion": str(srow.get("accion", "")),
                    "modelo": "modelo_mora_futura",
                },
            }
        )
    return socios
