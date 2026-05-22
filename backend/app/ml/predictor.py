"""Carga el modelo entrenado desde modelo_mora_produccion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import settings

RISK_LABELS = {
    "bajo": (0.0, 0.35),
    "medio": (0.35, 0.65),
    "alto": (0.65, 1.01),
}


class MoraPredictor:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or settings.model_dir
        self.model = None
        self.scaler = None
        self.feature_columns: list[str] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        model_path = self._find_file(
            ["modelo_mora.pkl", "model.pkl", "modelo.pkl", "best_model.pkl"]
        )
        scaler_path = self._find_file(
            ["scaler.pkl", "preprocessor.pkl", "scaler_model.pkl"]
        )
        meta_path = self._find_file(
            ["feature_columns.json", "features.json", "metadata.json"]
        )

        if model_path is None:
            raise FileNotFoundError(
                f"No se encontró modelo en {self.model_dir}. "
                "Coloca modelo_mora.pkl o model.pkl en modelo_mora_produccion/"
            )

        self.model = joblib.load(model_path)
        if scaler_path:
            self.scaler = joblib.load(scaler_path)

        if meta_path and meta_path.suffix == ".json":
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            self.feature_columns = meta.get("feature_columns") or meta.get("features") or []
        else:
            self.feature_columns = self._default_features()

        self._loaded = True

    def _find_file(self, names: list[str]) -> Path | None:
        for name in names:
            path = self.model_dir / name
            if path.exists():
                return path
        for path in self.model_dir.glob("*.pkl"):
            lower = path.name.lower()
            if any(k in lower for k in ["model", "mora", "rf", "xgb", "lgb"]):
                if "scaler" not in lower and "preprocessor" not in lower:
                    return path
        for path in self.model_dir.glob("*.pkl"):
            if "scaler" in path.name.lower() or "preprocessor" in path.name.lower():
                continue
        return None

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
        row = {col: float(features.get(col, 0.0)) for col in self.feature_columns}
        df = pd.DataFrame([row], columns=self.feature_columns)
        X = df
        if self.scaler is not None:
            X = self.scaler.transform(df)

        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X)[0]
            prob_mora = float(proba[-1]) if len(proba) > 1 else float(proba[0])
        else:
            pred = self.model.predict(X)[0]
            prob_mora = float(pred)

        nivel = self._risk_level(prob_mora)
        return {
            "probabilidad_mora": round(prob_mora, 4),
            "nivel_riesgo": nivel,
            "features_usadas": row,
        }

    def predict_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for rec in records:
            socio_id = rec.get("socio_id") or rec.get("id_socio")
            feats = rec.get("features") or rec
            out = self.predict_one(feats)
            out["socio_id"] = socio_id
            results.append(out)
        return results

    @staticmethod
    def _risk_level(probability: float) -> str:
        for label, (lo, hi) in RISK_LABELS.items():
            if lo <= probability < hi:
                return label
        return "alto"


_predictor: MoraPredictor | None = None


def get_predictor() -> MoraPredictor:
    global _predictor
    if _predictor is None:
        _predictor = MoraPredictor()
    return _predictor
