"""Genera señales legibles para la UI (mismo estilo que la referencia del dashboard)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SIGNAL_ALIASES: dict[str, tuple[str, ...]] = {
    "variacion_saldo_30d": ("var_saldo_30d", "pct_saldo_30d", "variacion_saldo"),
    "variacion_movimientos_30d": (
        "variacion_movimientos",
        "pct_var_movimientos",
        "var_movimientos_30d",
    ),
    "dias_desde_ultimo_pago_max": (
        "dias_atraso_promedio",
        "dias_atraso",
        "dias_mora",
        "max_dias_mora",
    ),
    "num_movimientos_30d": ("n_movimientos_30d", "movimientos_30d"),
}


def _norm_cliente_id(value: Any) -> str:
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        s = s[:-2]
    return s


def _canonicalize_features(feats: dict[str, float]) -> dict[str, float]:
    out = dict(feats)
    for canonical, aliases in SIGNAL_ALIASES.items():
        if canonical in out:
            continue
        for alias in aliases:
            if alias in out:
                out[canonical] = out[alias]
                break
    return out


def _pct_label(value: float) -> str:
    return f"{round(abs(value) * 100)}%"


def _pick(feats: dict[str, float], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        val = feats.get(key)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            return float(val)
    return None


def enrich_features_from_xt(
    cliente_id: str,
    feats: dict[str, float],
    xt_agg: pd.DataFrame,
) -> dict[str, float]:
    """Completa features desde histórico transaccional cuando el Excel solo trae el ID."""
    out = dict(feats)
    if xt_agg is None or xt_agg.empty:
        return _canonicalize_features(out)

    cid = _norm_cliente_id(cliente_id)
    ids = xt_agg["cliente_id"].astype(str).map(_norm_cliente_id)
    rows = xt_agg.loc[ids == cid]
    if rows.empty:
        return _canonicalize_features(out)

    row = rows.iloc[-1]
    med = xt_agg.median(numeric_only=True)

    for col in row.index:
        if col == "cliente_id":
            continue
        val = row[col]
        if pd.notna(val) and isinstance(val, (int, float, np.floating, np.integer)):
            out[str(col)] = float(val)

    def pct_vs_median(col: str) -> float | None:
        if col not in row.index or col not in med.index:
            return None
        val = float(row[col])
        m = float(med[col])
        if m == 0 or np.isnan(m):
            return None
        return (val - m) / abs(m)

    if _pick(out, ("variacion_saldo_30d", "variacion_saldo")) is None:
        for col in ("xt_saldo_ahorro_actual", "xt_saldo_ahorro_promedio", "xt_total_volumen_depositado"):
            p = pct_vs_median(col)
            if p is not None and p < -0.05:
                out["variacion_saldo_30d"] = p
                break

    if _pick(out, ("variacion_movimientos_30d", "variacion_movimientos")) is None:
        p = pct_vs_median("xt_n_operaciones")
        if p is not None and p < -0.05:
            out["variacion_movimientos_30d"] = p

    if "num_movimientos_30d" not in out and "xt_n_operaciones" in out:
        out["num_movimientos_30d"] = out["xt_n_operaciones"]

    if "ratio_egresos_ingresos" not in out:
        ing = out.get("ingresos_socio") or out.get("xt_ingresos_socio")
        egr = out.get("egresos_socio") or out.get("xt_egresos_socio")
        if ing and float(ing) > 0 and egr is not None:
            out["ratio_egresos_ingresos"] = float(egr) / float(ing)

    if "dias_desde_ultimo_pago_max" not in out and "xt_dia_pago" in out:
        dia = float(out["xt_dia_pago"])
        if dia > 0:
            out["dias_desde_ultimo_pago_max"] = dia

    return _canonicalize_features(out)


def build_risk_signals(feats: dict[str, float]) -> list[str]:
    """Etiquetas tipo: Movimientos ↓62%, Saldo ↓41%, Retrasos menores."""
    signals: list[str] = []

    variacion_saldo = _pick(
        feats,
        ("variacion_saldo_30d", "variacion_saldo", "var_saldo_30d", "pct_saldo_30d"),
    )
    if variacion_saldo is not None and variacion_saldo < -0.05:
        signals.append(f"Saldo ↓{_pct_label(variacion_saldo)}")

    variacion_mov = _pick(
        feats,
        ("variacion_movimientos_30d", "variacion_movimientos", "pct_var_movimientos"),
    )
    if variacion_mov is not None and variacion_mov < -0.05:
        signals.append(f"Movimientos ↓{_pct_label(variacion_mov)}")
    else:
        mov30 = _pick(feats, ("num_movimientos_30d", "n_movimientos_30d"))
        if mov30 is not None and mov30 < 5:
            signals.append("Movimientos ↓")
        else:
            ops = _pick(feats, ("xt_n_operaciones", "n_operaciones_credito"))
            if ops is not None and ops < 3:
                signals.append("Poca actividad")

    dias_atraso = _pick(
        feats,
        (
            "dias_desde_ultimo_pago_max",
            "dias_desde_ultimo_pago_prom",
            "dias_atraso_promedio",
            "dias_atraso",
            "hist_cuotas_atrasadas_max",
        ),
    )
    if dias_atraso is not None and dias_atraso > 0:
        if dias_atraso <= 15:
            signals.append("Retrasos menores")
        elif dias_atraso <= 45:
            signals.append(f"Retrasos {int(round(dias_atraso))} días")
        else:
            signals.append(f"Atraso {int(round(dias_atraso))} días")

    ratio_pago = _pick(feats, ("ratio_pago_cuota",))
    if ratio_pago is not None and ratio_pago < 0.85:
        signals.append(f"Pagos ↓{_pct_label(1 - ratio_pago)}")

    ratio_egr = _pick(feats, ("ratio_egresos_ingresos",))
    if ratio_egr is not None and ratio_egr > 0.8:
        signals.append("Egresos altos")

    saldo_venc = _pick(
        feats,
        ("saldo_vencido_actual_total", "saldo_vencido", "hist_cuotas_atrasadas_total"),
    )
    if saldo_venc is not None and saldo_venc > 0:
        signals.append("Saldo vencido")

    capacidad = _pick(feats, ("capacidad_pago",))
    if capacidad is not None and capacidad < 0:
        signals.append("Capacidad pago negativa")

    cuotas = _pick(feats, ("hist_cuotas_atrasadas_max",))
    if cuotas is not None and cuotas > 0 and not any("Retraso" in s or "Atraso" in s for s in signals):
        signals.append("Cuotas atrasadas")

    # Quitar duplicados manteniendo orden
    seen: set[str] = set()
    unique: list[str] = []
    for s in signals:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:5]
