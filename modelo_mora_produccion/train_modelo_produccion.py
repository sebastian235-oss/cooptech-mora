"""
Entrena y exporta el modelo DEFINITIVO de prevención de mora futura.
- Target: target_mora_futura (sin fugas)
- Validación hold-out: dataset_test_temporal.csv (nunca usado en entrenamiento)
"""
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score, brier_score_loss,
    classification_report,
)
from lightgbm import LGBMClassifier

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT.parent

PATH_PREV = DATA_ROOT / "dataset_entrenamiento_prevencion.csv"
PATH_XTRAIN = DATA_ROOT / "datos_entrenamiento_x_train.csv"
PATH_HOLDOUT = DATA_ROOT / "dataset_test_temporal.csv"

OUT_MODEL = ROOT / "modelo_mora_futura.pkl"
OUT_CONFIG = ROOT / "config.json"
OUT_README = ROOT / "README.md"

TARGET = "target_mora_futura"
TARGET_COL = "target_mora_futura"

ID_COLS = ["cliente_id", "fecha_corte", "fecha_objetivo"]
LEAKAGE = [
    "mora_actual", "max_dias_mora_actual", "dias_mora_futuro", "saldo_vencido_futuro",
    TARGET_COL,
]
CAT_PREV = [
    "tipo_operacion_dominante", "actividad_socio_dominante", "tipo_plazo_dominante",
    "garantia_dominante", "estado_civil", "nivel_educa", "tipo_vivien",
]
DATE_PREV = ["fecha_corte", "fecha_objetivo"]
CAT_XTRAIN = [
    "tipo_operacion", "estado_op", "destino_op", "actividad_socio",
    "tipo_cartera", "tipo_plazo", "tgarantia", "calificacion",
    "sexo", "estado_civil", "nivel_educa", "tipo_vivien", "cidudad_orig",
]
DATE_XTRAIN = [
    "qy_fechaproc", "fecha_concesion_op", "fecha_fin_op", "fecha_ult_pag",
    "fecha_garantias", "fech_nacimiento", "fech_ult_viv", "fech_utl_tra",
]
REF_DATE = pd.Timestamp("2026-05-11")


def aggregate_xtrain(df: pd.DataFrame) -> pd.DataFrame:
    skip = {"nro_operacion", "nro_cliente", "TARGET_MORA", "dias_mora", "saldo_vencido",
            "int_mora", "int_vencido", "nro_cuotas_atra", "val_morad", "val_notd"}
    num_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in skip]
    agg = {c: "median" for c in num_cols}
    agg["nro_operacion"] = "count"
    for c in CAT_XTRAIN:
        if c in df.columns:
            agg[c] = "first"
    g = df.groupby("nro_cliente", as_index=False).agg(agg)
    g = g.rename(columns={"nro_cliente": "cliente_id", "nro_operacion": "xt_n_operaciones"})
    return g.rename(columns={
        c: f"xt_{c}" for c in g.columns
        if c not in ["cliente_id", "xt_n_operaciones"] and not c.endswith("_cod")
    })


def encode_cats(df, cat_cols, encoders, fit=False, prefix=""):
    for col in cat_cols:
        if col not in df.columns:
            continue
        name = f"{prefix}{col}_cod" if prefix else f"{col}_cod"
        s = df[col].astype(str).fillna("NA")
        if fit:
            encoders[name] = LabelEncoder()
            df[name] = encoders[name].fit_transform(s)
        else:
            mapping = {c: i for i, c in enumerate(encoders[name].classes_)}
            df[name] = s.map(mapping).fillna(-1).astype(int)
    return df


def prepare_df(df: pd.DataFrame, xt_agg: pd.DataFrame, encoders: dict, fit: bool = False):
    p = df.copy()
    for col in DATE_PREV:
        if col in p.columns:
            dt = pd.to_datetime(p[col], errors="coerce")
            p[f"{col}_dias"] = (REF_DATE - dt).dt.days

    exclude = ID_COLS + LEAKAGE + CAT_PREV + DATE_PREV
    Xp = p.drop(columns=[c for c in exclude if c in p.columns], errors="ignore")
    Xp["cliente_id"] = p["cliente_id"].values
    Xp = encode_cats(Xp, CAT_PREV, encoders, fit=fit)

    xt_agg = xt_agg.copy()
    X_all = Xp.merge(xt_agg, on="cliente_id", how="left")

    drop = [c for c in X_all.columns if any(
        lk in c for lk in ["dias_mora", "saldo_vencido", "int_mora", "TARGET_MORA", "val_morad", "cuotas_atra"]
    ) and c.startswith("xt_")]
    X_all = X_all.drop(columns=drop, errors="ignore")
    X_all = X_all.drop(columns=["cliente_id"], errors="ignore")
    X_all = X_all.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)

    y = df[TARGET_COL].values if TARGET_COL in df.columns else None
    meta = df[ID_COLS].copy() if all(c in df.columns for c in ID_COLS) else df[["cliente_id"]].copy()
    return X_all, y, meta


def main():
    print("Cargando entrenamiento (solo prevención, sin test holdout)...")
    train_df = pd.read_csv(PATH_PREV)
    train_df = train_df.drop_duplicates(subset=["cliente_id", "fecha_corte"])
    print(f"  Train: {len(train_df):,} | mora futura: {train_df[TARGET_COL].mean():.2%}")

    xt = aggregate_xtrain(pd.read_csv(PATH_XTRAIN))
    encoders = {}
    X, y, meta = prepare_df(train_df, xt, encoders, fit=True)
    feature_names = list(X.columns)
    print(f"  Features: {len(feature_names)}")

    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    scale_pos = (y_tr == 0).sum() / max((y_tr == 1).sum(), 1)

    model = LGBMClassifier(
        n_estimators=600, learning_rate=0.05, num_leaves=48, max_depth=7,
        scale_pos_weight=scale_pos, subsample=0.8, colsample_bytree=0.8,
        min_child_samples=20, random_state=42, n_jobs=-1, verbose=-1,
    )
    model.fit(X_tr, y_tr)

    prob_val = model.predict_proba(X_val)[:, 1]
    auc_val = roc_auc_score(y_val, prob_val)
    ap_val = average_precision_score(y_val, prob_val)
    brier_val = brier_score_loss(y_val, prob_val)

    thresholds = np.arange(0.05, 0.95, 0.01)
    f1s = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
    umbral_f1 = float(thresholds[int(np.argmax(f1s))])
    umbral_alto = 0.50

    print(f"\nValidación interna (15%): AUC={auc_val:.4f} AP={ap_val:.4f} Brier={brier_val:.4f}")

    # HOLDOUT real: dataset_test_temporal
    print("\nValidación HOLDOUT (dataset_test_temporal)...")
    hold = pd.read_csv(PATH_HOLDOUT)
    X_h, y_h, meta_h = prepare_df(hold, xt, encoders, fit=False)
    for f in feature_names:
        if f not in X_h.columns:
            X_h[f] = np.nan
    X_h = X_h[feature_names]
    prob_h = model.predict_proba(X_h)[:, 1]
    auc_h = roc_auc_score(y_h, prob_h)
    ap_h = average_precision_score(y_h, prob_h)
    pred_h = (prob_h >= umbral_f1).astype(int)
    prec_h = precision_score(y_h, pred_h, zero_division=0)
    rec_h = recall_score(y_h, pred_h, zero_division=0)
    brier_h = brier_score_loss(y_h, prob_h)

    print(f"  HOLDOUT AUC-ROC: {auc_h:.4f}")
    print(f"  HOLDOUT AUC-PR:  {ap_h:.4f}")
    print(f"  HOLDOUT Brier:   {brier_h:.4f}")
    print(f"  HOLDOUT Prec/Rec @ {umbral_f1:.2f}: {prec_h:.4f} / {rec_h:.4f}")
    print(classification_report(y_h, pred_h, target_names=["No mora", "Mora futura"]))

    preventivo_h = int(((prob_h >= umbral_alto) & (y_h == 0)).sum())
    print(f"  Preventivos holdout (al día + prob>={umbral_alto}): {preventivo_h}")

    # Guardar bundle producción
    prev_latest = train_df.sort_values("fecha_corte").drop_duplicates("cliente_id", keep="last")
    feature_medians = X.median(numeric_only=True).to_dict()

    bundle = {
        "model": model,
        "encoders": encoders,
        "features": feature_names,
        "xt_agg": xt,
        "prev_latest": prev_latest,
        "feature_medians": feature_medians,
        "target": TARGET_COL,
        "umbral_f1": umbral_f1,
        "umbral_alto": umbral_alto,
        "ref_date": str(REF_DATE.date()),
    }
    joblib.dump(bundle, OUT_MODEL)

    config = {
        "modelo": "LightGBM — Prevención mora futura",
        "version": datetime.now().strftime("%Y.%m.%d"),
        "target": TARGET_COL,
        "descripcion": "Predice si un socio CON CRÉDITO VIGENTE y AL DÍA caerá en mora en el período siguiente.",
        "sin_fugas": True,
        "variables_excluidas_leakage": LEAKAGE,
        "no_usar_para_scoring": [
            "dias_mora", "saldo_vencido", "TARGET_MORA", "mora_actual",
            "dias_mora_futuro", "saldo_vencido_futuro",
        ],
        "dataset_entrenamiento": str(PATH_PREV.name),
        "dataset_validacion_holdout": str(PATH_HOLDOUT.name),
        "registros_entrenamiento": len(train_df),
        "features_count": len(feature_names),
        "umbrales": {"f1_optimo": umbral_f1, "alerta_alta": umbral_alto},
        "metricas_validacion_interna": {
            "AUC_ROC": round(auc_val, 4), "AUC_PR": round(ap_val, 4), "Brier": round(brier_val, 4),
        },
        "metricas_holdout_test_temporal": {
            "AUC_ROC": round(auc_h, 4), "AUC_PR": round(ap_h, 4),
            "Brier": round(brier_h, 4), "Precision": round(prec_h, 4), "Recall": round(rec_h, 4),
            "tasa_mora_real": round(float(y_h.mean()), 4),
            "n_preventivos_detectados": preventivo_h,
        },
        "top_features": pd.DataFrame({
            "feature": feature_names,
            "importancia": model.feature_importances_,
        }).sort_values("importancia", ascending=False).head(15).to_dict("records"),
        "schema_requerido": "dataset_entrenamiento_prevencion.csv (162 columnas, sin target en scoring)",
    }
    with open(OUT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nModelo guardado: {OUT_MODEL}")
    print(f"Config: {OUT_CONFIG}")


if __name__ == "__main__":
    main()
