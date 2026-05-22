"""
API de scoring — Modelo de prevención de mora futura (único modelo activo: modelo_mora_futura.pkl).
"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

from prepare_features import prepare_df

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "modelo_mora_futura.pkl"
DEFAULT_CONFIG = ROOT / "config.json"
DEFAULT_XTRAIN = ROOT.parent / "datos_entrenamiento_x_train.csv"

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
CAT_XTRAIN = [
    "tipo_operacion",
    "estado_op",
    "destino_op",
    "actividad_socio",
    "tipo_cartera",
    "tipo_plazo",
    "tgarantia",
    "calificacion",
    "sexo",
    "estado_civil",
    "nivel_educa",
    "tipo_vivien",
    "cidudad_orig",
]


def _aggregate_xtrain(df: pd.DataFrame) -> pd.DataFrame:
    skip = {
        "nro_operacion",
        "nro_cliente",
        "TARGET_MORA",
        "dias_mora",
        "saldo_vencido",
        "int_mora",
        "int_vencido",
        "nro_cuotas_atra",
        "val_morad",
        "val_notd",
    }
    num_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in skip]
    agg = {c: "median" for c in num_cols}
    agg["nro_operacion"] = "count"
    for c in CAT_XTRAIN:
        if c in df.columns:
            agg[c] = "first"
    g = df.groupby("nro_cliente", as_index=False).agg(agg)
    g = g.rename(columns={"nro_cliente": "cliente_id", "nro_operacion": "xt_n_operaciones"})
    return g.rename(
        columns={
            c: f"xt_{c}"
            for c in g.columns
            if c not in ["cliente_id", "xt_n_operaciones"] and not c.endswith("_cod")
        }
    )


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
    """Predictor de mora futura — LightGBM empaquetado en modelo_mora_futura.pkl."""

    def __init__(self, model_path=None, config_path=None, xtrain_path=None):
        model_path = Path(model_path or DEFAULT_MODEL)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modelo no encontrado: {model_path}. "
                "Use solo modelo_mora_futura.pkl en esta carpeta."
            )
        config_path = Path(config_path or DEFAULT_CONFIG)
        self.bundle = joblib.load(model_path)
        self.model = self.bundle["model"]
        self.encoders = self.bundle["encoders"]
        self.features = list(self.bundle["features"])
        self.umbral_f1 = float(self.bundle.get("umbral_f1", 0.38))
        self.umbral_alto = float(self.bundle.get("umbral_alto", 0.50))
        self.ref_date = pd.Timestamp(self.bundle.get("ref_date", "2026-05-11"))

        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

        if "xt_agg" in self.bundle:
            self._xt_agg = self.bundle["xt_agg"].copy()
            self._xt_agg["cliente_id"] = self._xt_agg["cliente_id"].astype(str).str.strip()
        else:
            xt_path = Path(xtrain_path or DEFAULT_XTRAIN)
            if xt_path.exists():
                self._xt_agg = _aggregate_xtrain(pd.read_csv(xt_path))
                self._xt_agg["cliente_id"] = self._xt_agg["cliente_id"].astype(str).str.strip()
            else:
                self._xt_agg = pd.DataFrame({"cliente_id": pd.Series(dtype=str)})

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        return prepare_df(df, self._xt_agg, self.encoders, self.ref_date, self.features)

    def _feature_medians(self) -> pd.Series:
        if "feature_medians" in self.bundle:
            return pd.Series(self.bundle["feature_medians"]).reindex(self.features)
        if len(self._xt_agg) == 0:
            return pd.Series(0.0, index=self.features)
        ids = self._xt_agg["cliente_id"].head(min(800, len(self._xt_agg))).tolist()
        batch = pd.DataFrame({"cliente_id": ids})
        X = prepare_df(batch, self._xt_agg, self.encoders, self.ref_date, self.features)
        med = X.median(numeric_only=True)
        return pd.Series({f: float(med[f]) if f in med.index and pd.notna(med[f]) else 0.0 for f in self.features})

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        work = df.copy()
        work["cliente_id"] = work["cliente_id"].astype(str).str.strip()
        X = self._prepare(work)
        coverage = (X.notna().sum(axis=1) / len(self.features)).astype(float)
        X = X.fillna(self._feature_medians())
        prob = self.model.predict_proba(X)[:, 1]

        if all(c in work.columns for c in ID_COLS):
            out = work[ID_COLS].copy()
        else:
            out = work[["cliente_id"]].copy()

        for col in ("nombre", "nombre_socio", "agencia", "n_creditos_unicos", "ingresos_socio", "egresos_socio"):
            if col in work.columns:
                out[col] = work[col].values

        out["feature_coverage"] = np.round(coverage.values, 4)
        out["prob_mora_futura"] = np.round(prob, 6)
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
        return out.sort_values("prob_mora_futura", ascending=False).reset_index(drop=True)

    def score_csv(self, path: str) -> pd.DataFrame:
        return self.score(pd.read_csv(path))

    def score_preventivo(self, df: pd.DataFrame) -> pd.DataFrame:
        scored = self.score(df)
        if "mora_actual" in df.columns:
            mask = df["mora_actual"].fillna(0).values == 0
            scored = scored.loc[mask].copy()
        return scored[scored["prob_mora_futura"] >= self.umbral_alto]


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent / "dataset_test_temporal.csv")
    pred = MoraPredictor()
    res = pred.score_csv(path)
    print(res.head(10))
    print(f"\nTotal: {len(res)} | Pred mora: {res['pred_mora_futura'].sum()}")
