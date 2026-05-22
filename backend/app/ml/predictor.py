"""Capa unificada de predicción: producción primero, demo como respaldo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.config import settings
from app.ml import production_scorer

RISK_LABELS = {
    "bajo": (0.0, 0.35),
    "medio": (0.35, 0.65),
    "alto": (0.65, 1.01),
}


class SimpleMoraPredictor:
    """Modelo demo (RandomForest 12 features) — respaldo."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or settings.model_dir
        self.model = None
        self.scaler = None
        self.feature_columns: list[str] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        model_path = self.model_dir / "modelo_mora.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"No se encontró {model_path}")
        self.model = joblib.load(model_path)
        scaler_path = self.model_dir / "scaler.pkl"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
        meta_path = self.model_dir / "feature_columns.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            self.feature_columns = meta.get("feature_columns") or meta.get("features") or []
        else:
            self.feature_columns = self._default_features()
        self._loaded = True

    @staticmethod
    def _default_features() -> list[str]:
        return [
            "dias_atraso_promedio",
            "ratio_pago_cuota",
            "saldo_promedio_cuenta",
            "variacion_saldo_30d",
            "num_movimientos_30d",
            "monto_pagos_30d",
            "antiguedad_socio_meses",
            "monto_credito",
            "cuotas_pagadas",
            "cuotas_totales",
            "ingresos_estimados",
            "gastos_estimados",
        ]

    def predict_one(self, features: dict[str, float]) -> dict[str, Any]:
        self.load()
        alias_map = {
            "ingresos_socio": "ingresos_estimados",
            "egresos_socio": "gastos_estimados",
            "dias_atraso": "dias_atraso_promedio",
            "max_dias_mora_actual": "dias_atraso_promedio",
        }
        normalized: dict[str, float] = {}
        for k, v in features.items():
            key = alias_map.get(k, k)
            normalized[key] = float(v)

        row = {col: float(normalized.get(col, 0.0)) for col in self.feature_columns}
        df = pd.DataFrame([row], columns=self.feature_columns)
        X = self.scaler.transform(df) if self.scaler is not None else df

        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X)[0]
            prob_mora = float(proba[-1]) if len(proba) > 1 else float(proba[0])
        else:
            prob_mora = float(self.model.predict(X)[0])

        nivel = self._risk_level(prob_mora)
        return {
            "probabilidad_mora": round(prob_mora, 4),
            "nivel_riesgo": nivel,
            "features_usadas": row,
            "modelo": "modelo_mora_demo",
        }

    @staticmethod
    def _risk_level(probability: float) -> str:
        for label, (lo, hi) in RISK_LABELS.items():
            if lo <= probability < hi:
                return label
        return "alto"


_simple: SimpleMoraPredictor | None = None


def get_simple_predictor() -> SimpleMoraPredictor:
    global _simple
    if _simple is None:
        _simple = SimpleMoraPredictor()
    return _simple


def predict_from_features(features: dict[str, float]) -> dict[str, Any]:
    """Una fila de features → predicción (producción vía DataFrame o demo)."""
    if production_scorer.production_available():
        row = dict(features)
        if "cliente_id" not in row and "cedula" in row:
            row["cliente_id"] = row["cedula"]
        if "cliente_id" not in row:
            row["cliente_id"] = "manual"
        df = pd.DataFrame([row])
        socios = production_scorer.score_dataframe(df)
        if socios:
            return socios[0]["prediccion"]
    return get_simple_predictor().predict_one(features)


def predict_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Batch: siempre intenta modelo de producción primero."""
    if production_scorer.production_available():
        return production_scorer.score_dataframe(df)
    from app.services.excel_import import score_with_simple_model

    return score_with_simple_model(df)


# Compatibilidad con código existente
class MoraPredictor:
    def predict_one(self, features: dict[str, float]) -> dict[str, Any]:
        return predict_from_features(features)

    def predict_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for rec in records:
            feats = rec.get("features") or rec
            out = predict_from_features(feats)
            out["socio_id"] = rec.get("socio_id") or rec.get("cedula")
            results.append(out)
        return results


_predictor: MoraPredictor | None = None


def get_predictor() -> MoraPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MoraPredictor()
    return _predictor
