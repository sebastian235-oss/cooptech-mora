"""Predicción: modelo_mora_futura.pkl (producción) o demo/respaldo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.config import settings
from app.ml import production_scorer

RISK_LABELS = {"bajo": (0.0, 0.35), "medio": (0.35, 0.65), "alto": (0.65, 1.01)}

DEMO_DIR = settings.model_dir / "demo"


class SimpleMoraPredictor:
    """Respaldo: RandomForest en demo/modelo_mora.pkl (NO es el modelo del reto)."""

    def __init__(self) -> None:
        self.model = None
        self.scaler = None
        self.feature_columns: list[str] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        model_path = DEMO_DIR / "modelo_mora.pkl"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Demo no encontrado en {model_path}. Ejecuta train_demo_model.py"
            )
        self.model = joblib.load(model_path)
        scaler_path = DEMO_DIR / "scaler.pkl"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
        meta = DEMO_DIR / "feature_columns.json"
        if meta.exists():
            with open(meta, encoding="utf-8") as f:
                self.feature_columns = json.load(f).get("feature_columns", [])
        else:
            self.feature_columns = [
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
        self._loaded = True

    def predict_one(self, features: dict[str, float]) -> dict[str, Any]:
        self.load()
        alias = {
            "ingresos_socio": "ingresos_estimados",
            "egresos_socio": "gastos_estimados",
        }
        row = {
            col: float(features.get(alias.get(col, col), features.get(col, 0.0)))
            for col in self.feature_columns
        }
        df = pd.DataFrame([row], columns=self.feature_columns)
        X = self.scaler.transform(df) if self.scaler else df
        proba = self.model.predict_proba(X)[0]
        prob = float(proba[-1]) if len(proba) > 1 else float(proba[0])
        nivel = "alto" if prob >= 0.65 else "medio" if prob >= 0.35 else "bajo"
        return {
            "probabilidad_mora": round(prob, 4),
            "nivel_riesgo": nivel,
            "features_usadas": row,
            "modelo": "demo/modelo_mora.pkl",
        }


_simple: SimpleMoraPredictor | None = None


def get_simple_predictor() -> SimpleMoraPredictor:
    global _simple
    if _simple is None:
        _simple = SimpleMoraPredictor()
    return _simple


def predict_from_features(features: dict[str, float]) -> dict[str, Any]:
    if production_scorer.production_available():
        row = dict(features)
        row.setdefault("cliente_id", row.get("cedula", "manual"))
        df = pd.DataFrame([row])
        socios = production_scorer.score_dataframe(df)
        if socios:
            return socios[0]["prediccion"]
    return get_simple_predictor().predict_one(features)


def predict_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    if production_scorer.production_available():
        return production_scorer.score_dataframe(df)
    from app.services.excel_import import score_with_simple_model

    return score_with_simple_model(df)


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
