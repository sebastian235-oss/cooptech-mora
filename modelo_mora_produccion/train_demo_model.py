"""
Genera un modelo de demostración compatible con la API.
Si ya tienes modelo entrenado, coloca:
  - modelo_mora.pkl (o model.pkl)
  - scaler.pkl (opcional)
  - feature_columns.json
"""
from pathlib import Path

import joblib
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
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

OUT_DIR = Path(__file__).parent


def synthetic_data(n: int = 2000) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        {
            "dias_atraso_promedio": rng.integers(0, 45, n),
            "ratio_pago_cuota": rng.uniform(0.3, 1.05, n),
            "saldo_promedio_cuenta": rng.uniform(50, 8000, n),
            "variacion_saldo_30d": rng.uniform(-0.7, 0.4, n),
            "num_movimientos_30d": rng.integers(0, 40, n),
            "monto_pagos_30d": rng.uniform(0, 3000, n),
            "antiguedad_socio_meses": rng.integers(1, 180, n),
            "monto_credito": rng.uniform(500, 50000, n),
            "cuotas_pagadas": rng.integers(0, 48, n),
            "cuotas_totales": rng.integers(12, 60, n),
            "ingresos_estimados": rng.uniform(300, 6000, n),
            "gastos_estimados": rng.uniform(200, 5500, n),
        }
    )
    score = (
        df["dias_atraso_promedio"] / 40
        + (1 - df["ratio_pago_cuota"].clip(0, 1))
        + (-df["variacion_saldo_30d"].clip(-1, 0))
        + (1 - df["num_movimientos_30d"] / 40)
        + (df["gastos_estimados"] / (df["ingresos_estimados"] + 1))
    )
    y = (score > score.quantile(0.65)).astype(int).values
    return df, y


def main():
    X, y = synthetic_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=120, max_depth=10, random_state=42, class_weight="balanced"
    )
    model.fit(X_train_s, y_train)
    acc = model.score(X_test_s, y_test)
    print(f"Accuracy demo: {acc:.3f}")

    joblib.dump(model, OUT_DIR / "modelo_mora.pkl")
    joblib.dump(scaler, OUT_DIR / "scaler.pkl")
    with open(OUT_DIR / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump({"feature_columns": FEATURE_COLUMNS}, f, indent=2)
    print(f"Modelo guardado en {OUT_DIR}")


if __name__ == "__main__":
    main()
