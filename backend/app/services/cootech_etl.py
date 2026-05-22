"""ETL CoopTech: integra sábana crédito (pivote), ahorro y transacciones."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd

from app.services.cootech_schema import (
    CREDITO_VIGENTE_STATES,
    CootechFileKind,
    canonicalize_columns,
    detect_file_kind,
    norm_col,
)


def _read_bytes(content: bytes, filename: str) -> pd.DataFrame:
    bio = BytesIO(content)
    low = filename.lower()
    if low.endswith(".csv"):
        return pd.read_csv(bio, low_memory=False)
    if low.endswith(".xls"):
        return pd.read_excel(bio, engine="xlrd")
    if low.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(bio, engine="openpyxl")
    raise ValueError(f"Formato no soportado: {filename}")


def _apply_renames(df: pd.DataFrame) -> pd.DataFrame:
    renames = canonicalize_columns(list(df.columns))
    if renames:
        df = df.rename(columns=renames)
    df.columns = [norm_col(c) for c in df.columns]
    return df.loc[:, ~df.columns.duplicated()]


def _ensure_cliente_id(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ("cliente_id", "cedula", "nro_cuenta", "cuenta"):
        if c in out.columns:
            out["cliente_id"] = out[c].astype(str).str.strip()
            out.loc[out["cliente_id"].str.endswith(".0"), "cliente_id"] = (
                out.loc[out["cliente_id"].str.endswith(".0"), "cliente_id"].str[:-2]
            )
            return out
    raise ValueError("No se encontró columna de cliente (nro_cliente, cedula, etc.)")


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _is_vigente(estado: Any) -> bool:
    if pd.isna(estado):
        return True
    s = str(estado).strip().lower()
    if not s or s in ("nan", "none"):
        return True
    return any(v in s for v in CREDITO_VIGENTE_STATES) or "vigent" in s


def load_cootech_file(content: bytes, filename: str) -> tuple[CootechFileKind, pd.DataFrame]:
    kind = detect_file_kind(filename)
    df = _apply_renames(_read_bytes(content, filename))
    if df.empty:
        return kind, df
    df = _ensure_cliente_id(df)
    return kind, df


def _agg_credito(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Última foto de crédito por cliente + variación entre cortes."""
    tagged: list[pd.DataFrame] = []
    for i, df in enumerate(frames):
        w = df.copy()
        if "fecha_corte" in w.columns:
            w["_fc"] = _parse_dates(w["fecha_corte"])
        else:
            w["_fc"] = pd.Timestamp("2026-05-01") + pd.Timedelta(days=i)
        tagged.append(w)

    all_cred = pd.concat(tagged, ignore_index=True)
    all_cred = all_cred.sort_values(["cliente_id", "_fc"])

    last = all_cred.groupby("cliente_id", as_index=False).last()
    num_cols = [
        "dias_mora",
        "cuotas_atrasadas",
        "saldo_capital",
        "saldo_vencido",
        "monto_credito",
        "plazo",
        "tasa",
    ]
    agg_last = {c: "last" for c in num_cols if c in last.columns}
    if "nombre" in last.columns:
        agg_last["nombre"] = "last"
    if "agencia" in last.columns:
        agg_last["agencia"] = "last"
    if "estado_credito" in last.columns:
        agg_last["estado_credito"] = "last"

    base = last.groupby("cliente_id", as_index=False).agg(agg_last)

    # Variación dias_mora entre primer y último corte
    if "dias_mora" in all_cred.columns:
        piv = all_cred.groupby("cliente_id")["dias_mora"].agg(["first", "last"]).reset_index()
        piv["delta_dias_mora"] = piv["last"] - piv["first"]
        base = base.merge(piv[["cliente_id", "delta_dias_mora"]], on="cliente_id", how="left")

    base["credito_vigente"] = (
        base["estado_credito"].apply(_is_vigente) if "estado_credito" in base.columns else True
    )
    base["al_dia_actual"] = (
        (base.get("dias_mora", 0).fillna(0) <= 0)
        & (base.get("cuotas_atrasadas", 0).fillna(0) <= 0)
        & (base.get("saldo_vencido", 0).fillna(0) <= 0)
    )
    return base


def _agg_ahorro(frames: list[pd.DataFrame]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for i, df in enumerate(frames):
        w = df.copy()
        w["_period"] = i
        if "fecha" in w.columns:
            w["_fecha"] = _parse_dates(w["fecha"])
        parts.append(w)

    all_a = pd.concat(parts, ignore_index=True)
    g = all_a.groupby("cliente_id")
    out = pd.DataFrame({"cliente_id": g.size().index})
    out["ahorro_movimientos"] = g.size().values

    if "saldo_ahorro" in all_a.columns:
        saldo = all_a.groupby("cliente_id")["saldo_ahorro"].agg(["last", "mean", "min", "max"])
        out["saldo_ahorro_ultimo"] = saldo["last"].values
        out["saldo_ahorro_prom"] = saldo["mean"].values
        if len(frames) >= 2:
            first_last = all_a.groupby("cliente_id")["saldo_ahorro"].agg(["first", "last"])
            fl = first_last["last"] - first_last["first"]
            denom = first_last["first"].replace(0, np.nan)
            out["variacion_saldo_ahorro"] = (fl / denom.abs()).fillna(0).values

    if "monto" in all_a.columns:
        out["ahorro_monto_total"] = g["monto"].sum().values
    return out


def _agg_transacciones(frames: list[pd.DataFrame]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for df in frames:
        w = df.copy()
        if "fecha" in w.columns:
            w["_fecha"] = _parse_dates(w["fecha"])
        parts.append(w)

    all_t = pd.concat(parts, ignore_index=True)
    g = all_t.groupby("cliente_id")
    out = pd.DataFrame({"cliente_id": g.size().index})
    out["num_movimientos"] = g.size().values

    if "monto" in all_t.columns:
        m = all_t.groupby("cliente_id")["monto"]
        out["mov_monto_total"] = m.sum().values
        out["mov_monto_prom"] = m.mean().values
        out["mov_monto_std"] = m.std().fillna(0).values

    if "_fecha" in all_t.columns:
        out["dias_desde_ultimo_mov"] = (
            pd.Timestamp("2026-05-19") - g["_fecha"].max()
        ).dt.days.values

    if "tipo_operacion" in all_t.columns:
        out["tipos_operacion_unicos"] = g["tipo_operacion"].nunique().values

    return out


def build_cootech_features(files: list[tuple[str, bytes]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Recibe lista (nombre_archivo, contenido).
    Retorna matriz 1 fila por cliente_id + metadatos.
    """
    cred_frames: list[pd.DataFrame] = []
    ahorro_frames: list[pd.DataFrame] = []
    trns_frames: list[pd.DataFrame] = []
    meta: dict[str, Any] = {"archivos": [], "errores": []}

    for filename, content in files:
        try:
            kind, df = load_cootech_file(content, filename)
            meta["archivos"].append({"archivo": filename, "tipo": kind.value, "filas": len(df)})
            if kind == CootechFileKind.CREDITO:
                cred_frames.append(df)
            elif kind == CootechFileKind.AHORRO:
                ahorro_frames.append(df)
            elif kind == CootechFileKind.TRANSACCION:
                trns_frames.append(df)
            else:
                meta["errores"].append(f"{filename}: tipo no reconocido, omitido")
        except Exception as exc:
            meta["errores"].append(f"{filename}: {exc}")

    if not cred_frames:
        raise ValueError("Falta al menos un archivo DataSabanaCred (créditos).")

    base = _agg_credito(cred_frames)
    if ahorro_frames:
        ah = _agg_ahorro(ahorro_frames)
        base = base.merge(ah, on="cliente_id", how="left")
    if trns_frames:
        tr = _agg_transacciones(trns_frames)
        base = base.merge(tr, on="cliente_id", how="left")

    # Target proxy para entrenamiento: nuevos en mora entre cortes
    if len(cred_frames) >= 2 and "dias_mora" in cred_frames[-1].columns:
        early = cred_frames[0].groupby("cliente_id")["dias_mora"].max().reset_index()
        early.columns = ["cliente_id", "dias_mora_ini"]
        late = cred_frames[-1].groupby("cliente_id")["dias_mora"].max().reset_index()
        late.columns = ["cliente_id", "dias_mora_fin"]
        trans = early.merge(late, on="cliente_id")
        trans["target_mora_prox"] = (
            (trans["dias_mora_fin"] > 0) & (trans["dias_mora_ini"] <= 0)
        ).astype(int)
        base = base.merge(trans[["cliente_id", "target_mora_prox"]], on="cliente_id", how="left")
        base["target_mora_prox"] = base["target_mora_prox"].fillna(0).astype(int)
    else:
        base["target_mora_prox"] = (base.get("dias_mora", 0).fillna(0) > 0).astype(int)

    meta["total_clientes"] = len(base)
    meta["clientes_vigentes"] = int(base["credito_vigente"].sum())
    meta["clientes_al_dia"] = int(base["al_dia_actual"].sum())
    return base, meta
