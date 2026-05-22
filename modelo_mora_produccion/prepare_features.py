"""Pipeline compartido de features (entrenamiento y scoring)."""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_COL = "target_mora_futura"
ID_COLS = ["cliente_id", "fecha_corte", "fecha_objetivo"]
LEAKAGE = [
    "mora_actual",
    "max_dias_mora_actual",
    "dias_mora_futuro",
    "saldo_vencido_futuro",
    TARGET_COL,
]
CAT_PREV = [
    "tipo_operacion_dominante",
    "actividad_socio_dominante",
    "tipo_plazo_dominante",
    "garantia_dominante",
    "estado_civil",
    "nivel_educa",
    "tipo_vivien",
]
DATE_PREV = ["fecha_corte", "fecha_objetivo"]

PREVENTION_FROM_XT = {
    "ingresos_socio": "xt_ingresos_socio",
    "egresos_socio": "xt_egresos_socio",
    "n_creditos_unicos": "xt_n_operaciones",
}


def norm_cliente_id(value) -> str:
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        s = s[:-2]
    return s


def encode_cats(df: pd.DataFrame, cat_cols: list[str], encoders: dict, prefix: str = "") -> pd.DataFrame:
    for col in cat_cols:
        if col not in df.columns:
            continue
        name = f"{prefix}{col}_cod" if prefix else f"{col}_cod"
        if name not in encoders:
            continue
        s = df[col].astype(str).fillna("NA")
        mapping = {c: i for i, c in enumerate(encoders[name].classes_)}
        df[name] = s.map(mapping).fillna(-1).astype(int)
    return df


def prepare_df(
    df: pd.DataFrame,
    xt_agg: pd.DataFrame,
    encoders: dict,
    ref_date: pd.Timestamp,
    feature_names: list[str],
) -> pd.DataFrame:
    """Misma lógica que el entrenamiento: prevención + xt_agg → matriz del modelo."""
    p = df.copy()
    for col in DATE_PREV:
        if col in p.columns:
            dt = pd.to_datetime(p[col], errors="coerce")
            p[f"{col}_dias"] = (ref_date - dt).dt.days

    exclude = ID_COLS + LEAKAGE + CAT_PREV + DATE_PREV
    Xp = p.drop(columns=[c for c in exclude if c in p.columns], errors="ignore")
    Xp["cliente_id"] = p["cliente_id"].astype(str).str.strip()
    Xp = encode_cats(Xp, CAT_PREV, encoders)

    xt = xt_agg.copy()
    if "cliente_id" in xt.columns:
        xt["cliente_id"] = xt["cliente_id"].astype(str).str.strip()

    X_all = Xp.merge(xt, on="cliente_id", how="left")
    drop_xt = [
        c
        for c in X_all.columns
        if c.startswith("xt_")
        and any(
            lk in c
            for lk in (
                "dias_mora",
                "saldo_vencido",
                "int_mora",
                "TARGET_MORA",
                "val_morad",
                "cuotas_atra",
            )
        )
    ]
    X_all = X_all.drop(columns=drop_xt, errors="ignore")
    X_all = X_all.drop(columns=["cliente_id"], errors="ignore")
    X_all = X_all.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)

    return X_all.reindex(columns=feature_names)
