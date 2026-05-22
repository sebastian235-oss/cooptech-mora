"""Único motor de predicción: modelo_mora_produccion (modelo_mora_futura.pkl)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml import production_scorer


def _require_production():
    if not production_scorer.production_available():
        raise RuntimeError(
            production_scorer.production_error()
            or "Coloca modelo_mora_futura.pkl en la carpeta modelo_mora_produccion/"
        )


def predict_from_features(features: dict[str, float]) -> dict[str, Any]:
    _require_production()
    row = dict(features)
    row.setdefault("cliente_id", str(row.get("cedula", "manual")))
    df = pd.DataFrame([row])
    socios = production_scorer.score_dataframe(df)
    if not socios:
        raise RuntimeError("El modelo no devolvió predicción para este registro.")
    return socios[0]["prediccion"]


def predict_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    _require_production()
    return production_scorer.score_dataframe(df)


class MoraPredictor:
    def predict_one(self, features: dict[str, float]) -> dict[str, Any]:
        return predict_from_features(features)

    def predict_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**predict_from_features(r.get("features") or r), "socio_id": r.get("socio_id")}
            for r in records
        ]


_predictor: MoraPredictor | None = None


def get_predictor() -> MoraPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MoraPredictor()
    return _predictor
