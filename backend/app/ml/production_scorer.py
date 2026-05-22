"""Scoring exclusivo con modelo_mora_futura.pkl (carpeta modelo_mora_produccion)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from app.config import settings
from app.services.column_mapping import (
    extract_features_row,
    heuristic_probability,
    nivel_from_features,
    norm_cliente_id,
)

logger = logging.getLogger(__name__)

MODEL_DIR = settings.model_dir
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

_prod_instance = None
_prod_error: str | None = None

PRODUCTION_MODEL_FILE = "modelo_mora_futura.pkl"


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
    out["cliente_id"] = out["cliente_id"].map(norm_cliente_id)
    return out


def score_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    prod = get_production_predictor()
    if prod is None:
        raise RuntimeError(production_error() or "Modelo no disponible")

    raw = _ensure_cliente_id(df)
    raw = raw.drop_duplicates(subset=["cliente_id"], keep="last").reset_index(drop=True)
    raw_indexed = raw.set_index("cliente_id", drop=False)

    scored = prod.score(raw)
    n = len(scored)
    if n == 0:
        return []

    scored["cliente_id"] = scored["cliente_id"].map(norm_cliente_id)

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
    probs_model = scored["prob_mora_futura"].astype(float).values
    niveles_lbl = scored["nivel_riesgo"].astype(str).values
    acciones = scored["accion"].astype(str).values
    coverages = (
        scored["feature_coverage"].astype(float).values
        if "feature_coverage" in scored.columns
        else [0.0] * n
    )
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
        cid = norm_cliente_id(cids[i])
        prob_ml = float(probs_model[i])
        feats: dict[str, float] = {}
        if cid in raw_indexed.index:
            feats = extract_features_row(raw_indexed.loc[cid])
        cov = float(coverages[i])

        # Tabla maestra: pocos features para ML → combinar con heurística de mora
        if cov < 0.25:
            prob_final = max(prob_ml, heuristic_probability(feats))
            nivel = nivel_from_features(prob_ml, feats, umbral_f1, umbral_alto)
        else:
            prob_final = prob_ml
            if prob_final >= umbral_alto:
                nivel = "alto"
            elif prob_final >= umbral_f1:
                nivel = "medio"
            elif prob_final >= 0.12:
                nivel = "medio"
            else:
                nivel = "bajo"

        ag = agencias[i]
        socios.append(
            {
                "id": str(uuid4()),
                "cedula": cid,
                "nombre": nombres[i] if nombres[i] and nombres[i] != "nan" else f"Socio {cid}",
                "agencia": ag if ag and ag != "nan" else None,
                "features": feats,
                "prediccion": {
                    "probabilidad_mora": round(prob_final, 4),
                    "probabilidad_modelo_ml": round(prob_ml, 6),
                    "nivel_riesgo": nivel,
                    "nivel_label": niveles_lbl[i],
                    "accion": acciones[i],
                    "modelo": PRODUCTION_MODEL_FILE,
                    "feature_coverage": round(cov, 4),
                    "origen_prob": "heuristica_tabla_maestra" if cov < 0.25 else "modelo_ml",
                },
            }
        )
    return socios
