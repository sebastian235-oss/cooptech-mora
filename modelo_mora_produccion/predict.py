"""
API de scoring — Modelo de prevención de mora futura.
Uso:
    from predict import MoraPredictor
    pred = MoraPredictor()
    resultado = pred.score_csv("mi_archivo.csv")
"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "modelo_mora_futura.pkl"
DEFAULT_CONFIG = ROOT / "config.json"
DEFAULT_XTRAIN = ROOT.parent / "datos_entrenamiento_x_train.csv"

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


def _aggregate_xtrain(df: pd.DataFrame) -> pd.DataFrame:
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


def _encode(df, cat_cols, encoders, prefix=""):
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


class MoraPredictor:
    """Predictor de mora futura sin variables de fuga."""

    def __init__(self, model_path=None, config_path=None, xtrain_path=None):
        model_path = Path(model_path or DEFAULT_MODEL)
        config_path = Path(config_path or DEFAULT_CONFIG)
        self.bundle = joblib.load(model_path)
        self.model = self.bundle["model"]
        self.encoders = self.bundle["encoders"]
        self.features = self.bundle["features"]
        self.umbral_f1 = self.bundle.get("umbral_f1", 0.38)
        self.umbral_alto = self.bundle.get("umbral_alto", 0.50)
        self.ref_date = pd.Timestamp(self.bundle.get("ref_date", "2026-05-11"))

        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

        if "xt_agg" in self.bundle:
            self._xt_agg = self.bundle["xt_agg"]
        else:
            xt_path = Path(xtrain_path or DEFAULT_XTRAIN)
            self._xt_agg = _aggregate_xtrain(pd.read_csv(xt_path))

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = df.copy()
        for col in DATE_PREV:
            if col in p.columns:
                dt = pd.to_datetime(p[col], errors="coerce")
                p[f"{col}_dias"] = (self.ref_date - dt).dt.days

        exclude = ID_COLS + LEAKAGE + CAT_PREV + DATE_PREV
        Xp = p.drop(columns=[c for c in exclude if c in p.columns], errors="ignore")
        Xp["cliente_id"] = p["cliente_id"].values
        Xp = _encode(Xp, CAT_PREV, self.encoders)
        X = Xp.merge(self._xt_agg, on="cliente_id", how="left")
        X = X.drop(columns=["cliente_id"], errors="ignore")
        X = X.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)
        for f in self.features:
            if f not in X.columns:
                X[f] = np.nan
        return X[self.features]

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recibe DataFrame con schema de dataset_entrenamiento_prevencion.
        Retorna cliente_id, prob_mora_futura, nivel_riesgo, accion.
        """
        for col in LEAKAGE:
            if col in df.columns and col != TARGET_COL:
                pass  # se ignoran en prepare
        X = self._prepare(df)
        prob = self.model.predict_proba(X)[:, 1]

        out = df[ID_COLS].copy() if all(c in df.columns for c in ID_COLS) else df[["cliente_id"]].copy()
        if "n_creditos_unicos" in df.columns:
            out["n_creditos_unicos"] = df["n_creditos_unicos"]
        if "ingresos_socio" in df.columns:
            out["ingresos_socio"] = df["ingresos_socio"]
            out["egresos_socio"] = df.get("egresos_socio", np.nan)

        out["prob_mora_futura"] = np.round(prob, 4)
        out["pred_mora_futura"] = (prob >= self.umbral_f1).astype(int)
        out["nivel_riesgo"] = np.select(
            [prob >= self.umbral_alto, prob >= self.umbral_f1, prob >= 0.2],
            ["Muy alto", "Alto", "Medio"],
            default="Bajo",
        )
        out["accion"] = np.select(
            [prob >= self.umbral_alto, prob >= self.umbral_f1],
            ["Contacto preventivo urgente", "Seguimiento de pagos"],
            default="Monitoreo rutinario",
        )
        out["rank_riesgo"] = out["prob_mora_futura"].rank(ascending=False, method="min").astype(int)
        return out.sort_values("prob_mora_futura", ascending=False)

    def score_csv(self, path: str) -> pd.DataFrame:
        return self.score(pd.read_csv(path))

    def score_preventivo(self, df: pd.DataFrame) -> pd.DataFrame:
        """Solo socios al día (mora_actual=0) con riesgo alto."""
        scored = self.score(df)
        if "mora_actual" in df.columns:
            scored = scored[df["mora_actual"].values == 0]
        return scored[scored["prob_mora_futura"] >= self.umbral_alto]


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent / "dataset_test_temporal.csv")
    pred = MoraPredictor()
    res = pred.score_csv(path)
    print(res.head(10))
    print(f"\nTotal: {len(res)} | Pred mora: {res['pred_mora_futura'].sum()}")
