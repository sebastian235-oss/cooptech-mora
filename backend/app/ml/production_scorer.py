"""Scoring con modelo_mora_futura.pkl (único modelo de producción)."""

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

# Solo este archivo es el modelo activo
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
        _prod_error = f"Falta {PRODUCTION_MODEL_FILE} en {MODEL_DIR}"
        return None
    try:
        from predict import MoraPredictor  # noqa: PLC0415

        _prod_instance = MoraPredictor(model_path=model_path)
        _prod_error = None
        logger.info(
            "Modelo producción OK: %s (%d features, umbral_f1=%.2f)",
            PRODUCTION_MODEL_FILE,
            len(_prod_instance.features),
            _prod_instance.umbral_f1,
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
        raise ValueError("Falta columna cliente_id / cedula / nro_cliente")
    out["cliente_id"] = out["cliente_id"].astype(str).str.strip()
    return out


def _pick_name_column(df: pd.DataFrame) -> str | None:
    for c in ("nombre", "nombre_socio", "nombre_cliente", "socio"):
        if c in df.columns:
            return c
    return None


def score_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    prod = get_production_predictor()
    if prod is None:
        raise RuntimeError(production_error() or "Modelo no disponible")

    raw = _ensure_cliente_id(df)
    # Una fila por socio (evita duplicados que distorsionan el score)
    raw = raw.drop_duplicates(subset=["cliente_id"], keep="last").reset_index(drop=True)

    scored = prod.score(raw)
    if scored.empty:
        return []

    name_col = _pick_name_column(scored)
    if not name_col:
        name_col = _pick_name_column(raw)
    agency_col = next((c for c in ("agencia", "sucursal", "oficina") if c in raw.columns), None)

    socios: list[dict[str, Any]] = []
    for srow in scored.to_dict("records"):
        cid = str(srow["cliente_id"])
        prob = float(srow["prob_mora_futura"])
        nombre = (
            str(srow.get(name_col or "", "")).strip()
            if name_col and pd.notna(srow.get(name_col))
            else f"Socio {cid}"
        )
        agencia = None
        if agency_col and pd.notna(srow.get(agency_col)):
            agencia = str(srow.get(agency_col)).strip()

        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": nombre,
                "agencia": agencia,
                "features": {},
                "prediccion": {
                    "probabilidad_mora": round(prob, 4),
                    "nivel_riesgo": _nivel_from_prob(prob, prod.umbral_f1, prod.umbral_alto),
                    "nivel_label": str(srow.get("nivel_riesgo", "")),
                    "accion": str(srow.get("accion", "")),
                    "modelo": PRODUCTION_MODEL_FILE,
                },
            }
        )
    return socios
