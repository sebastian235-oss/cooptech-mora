"""Modelo de riesgo CoopTech (LightGBM + heurística preventiva)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "cootech_risk.pkl"

FEATURE_EXCLUDE = {
    "cliente_id",
    "cedula",
    "nombre",
    "agencia",
    "estado_credito",
    "target_mora_prox",
    "credito_vigente",
    "al_dia_actual",
    "_fc",
}


def _feature_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        if c in FEATURE_EXCLUDE or c.startswith("_"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def heuristic_risk_vector(df: pd.DataFrame) -> np.ndarray:
    """Score 0-1 vectorizado para socios al día."""
    score = np.full(len(df), 0.05, dtype=float)
    dm = df["delta_dias_mora"].fillna(0).to_numpy() if "delta_dias_mora" in df.columns else 0
    if isinstance(dm, (int, float)):
        dm = np.zeros(len(df))
    score += np.where(dm > 0, np.minimum(0.35, dm / 30.0), 0)

    mov = (
        df["num_movimientos"].fillna(0).to_numpy()
        if "num_movimientos" in df.columns
        else np.zeros(len(df))
    )
    score += np.where(mov < 3, 0.15, np.where(mov < 8, 0.08, 0))

    var_ah = (
        df["variacion_saldo_ahorro"].fillna(0).to_numpy()
        if "variacion_saldo_ahorro" in df.columns
        else np.zeros(len(df))
    )
    score += np.where(var_ah < -0.15, np.minimum(0.25, np.abs(var_ah)), 0)

    dias_mov = (
        df["dias_desde_ultimo_mov"].fillna(0).to_numpy()
        if "dias_desde_ultimo_mov" in df.columns
        else np.zeros(len(df))
    )
    score += np.where(dias_mov > 25, 0.12, 0)

    saldo_cap = (
        df["saldo_capital"].fillna(0).to_numpy()
        if "saldo_capital" in df.columns
        else np.zeros(len(df))
    )
    monto = (
        df["monto_credito"].replace(0, np.nan).fillna(1).to_numpy()
        if "monto_credito" in df.columns
        else np.ones(len(df))
    )
    ratio = np.divide(saldo_cap, monto, where=monto > 0, out=np.zeros_like(saldo_cap))
    score += np.where(ratio > 0.85, 0.1, 0)
    return np.minimum(0.92, score)


def _nivel(prob: float) -> str:
    if prob >= 0.45:
        return "alto"
    if prob >= 0.22:
        return "medio"
    return "bajo"


def build_signals(row: pd.Series, prob: float) -> list[str]:
    tags: list[str] = []
    dm = row.get("delta_dias_mora")
    if dm is not None and float(dm) > 0:
        tags.append(f"Mora ↑{int(dm)} días")
    mov = row.get("num_movimientos")
    if mov is not None and float(mov) < 5:
        tags.append("Movimientos ↓")
    var_ah = row.get("variacion_saldo_ahorro")
    if var_ah is not None and float(var_ah) < -0.1:
        tags.append(f"Saldo ↓{int(abs(float(var_ah)) * 100)}%")
    dias_mov = row.get("dias_desde_ultimo_mov")
    if dias_mov is not None and float(dias_mov) > 15:
        tags.append(f"Sin mov. {int(dias_mov)} días")
    if row.get("saldo_vencido", 0) and float(row.get("saldo_vencido", 0)) > 0:
        tags.append("Saldo vencido")
    if prob >= 0.22:
        tags.append(f"Riesgo {prob * 100:.0f}%")
    return tags[:5]


def train_or_load(df: pd.DataFrame) -> dict[str, Any]:
    feat_cols = _feature_columns(df)
    bundle: dict[str, Any] = {
        "type": "heuristic",
        "feature_columns": feat_cols,
        "metrics": {},
    }

    train_df = df[df["al_dia_actual"] == True].copy()  # noqa: E712
    if len(train_df) < 50:
        train_df = df.copy()

    y = train_df["target_mora_prox"].astype(int)
    if y.nunique() >= 2 and len(feat_cols) >= 3:
        try:
            import lightgbm as lgb

            X = train_df[feat_cols].fillna(0).replace([np.inf, -np.inf], 0)
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            model = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                scale_pos_weight=(y_tr == 0).sum() / max((y_tr == 1).sum(), 1),
                random_state=42,
                verbose=-1,
            )
            model.fit(X_tr, y_tr)
            prob_te = model.predict_proba(X_te)[:, 1]
            bundle = {
                "type": "lightgbm",
                "model": model,
                "feature_columns": feat_cols,
                "metrics": {
                    "auc_proxy": float(np.mean((prob_te >= 0.5) == y_te)),
                    "positivos": int(y.sum()),
                    "muestras": len(train_df),
                },
            }
        except Exception:
            pass

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    return bundle


def load_bundle() -> dict[str, Any] | None:
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return None


def predict_df(df: pd.DataFrame, bundle: dict[str, Any] | None = None) -> pd.DataFrame:
    bundle = bundle or load_bundle() or train_or_load(df)
    vigentes = df[df["credito_vigente"] == True].copy()  # noqa: E712
    predict_all = df.copy()

    al_dia_mask = vigentes["al_dia_actual"] == True  # noqa: E712
    scoring_idx = vigentes.index[al_dia_mask]
    scoring = vigentes.loc[scoring_idx]

    probs = np.zeros(len(scoring))
    if (
        bundle.get("type") == "lightgbm"
        and bundle.get("model") is not None
        and len(scoring) > 0
    ):
        cols = bundle["feature_columns"]
        X = scoring.reindex(columns=cols, fill_value=0).fillna(0).replace([np.inf, -np.inf], 0)
        probs = bundle["model"].predict_proba(X)[:, 1]
    elif len(scoring) > 0:
        probs = heuristic_risk_vector(scoring)

    vigentes["probabilidad_mora"] = 0.0
    vigentes["nivel_riesgo"] = "bajo"
    vigentes["senales"] = None
    vigentes.loc[scoring_idx, "probabilidad_mora"] = probs
    vigentes.loc[scoring_idx, "nivel_riesgo"] = [_nivel(p) for p in probs]
    for i, idx in enumerate(scoring.index):
        vigentes.at[idx, "senales"] = build_signals(
            scoring.loc[idx], float(probs[i])
        )

    en_mora_idx = vigentes.index[~al_dia_mask]
    vigentes.loc[en_mora_idx, "probabilidad_mora"] = 0.02
    vigentes.loc[en_mora_idx, "nivel_riesgo"] = "bajo"
    for idx in en_mora_idx:
        vigentes.at[idx, "senales"] = ["Ya en mora actual"]

    predict_all = predict_all.merge(
        vigentes[
            ["cliente_id", "probabilidad_mora", "nivel_riesgo", "senales"]
        ],
        on="cliente_id",
        how="left",
    )
    predict_all["probabilidad_mora"] = predict_all["probabilidad_mora"].fillna(0)
    predict_all["nivel_riesgo"] = predict_all["nivel_riesgo"].fillna("bajo")
    predict_all["senales"] = predict_all["senales"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # Priorizar preventivos (al día) con mayor riesgo
    sort_key = predict_all["al_dia_actual"].astype(int) * 1000 + predict_all[
        "probabilidad_mora"
    ].fillna(0)
    return predict_all.assign(_sort=sort_key).sort_values(
        "_sort", ascending=False
    ).drop(columns="_sort")
