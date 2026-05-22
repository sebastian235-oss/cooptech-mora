"""Importación bundle CoopTech → socios para dashboard."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import pandas as pd

from app.services.cootech_etl import build_cootech_features
from app.services.cootech_model import predict_df, train_or_load


def _row_to_socio(row: pd.Series) -> dict[str, Any]:
    cid = str(row.get("cliente_id", ""))
    nombre = row.get("nombre")
    if pd.isna(nombre) or not str(nombre).strip():
        nombre = f"Socio {cid}"
    else:
        nombre = str(nombre).strip()

    ag = row.get("agencia")
    agencia = None if pd.isna(ag) else str(ag)

    senales = row.get("senales", [])
    if not isinstance(senales, list):
        senales = []

    prob = float(row.get("probabilidad_mora", 0) or 0)
    nivel = str(row.get("nivel_riesgo", "bajo"))

    feats = {}
    for c in (
        "dias_mora",
        "delta_dias_mora",
        "num_movimientos",
        "variacion_saldo_ahorro",
        "dias_desde_ultimo_mov",
        "saldo_capital",
        "monto_credito",
    ):
        if c in row.index and pd.notna(row[c]):
            feats[c] = float(row[c])

    return {
        "id": str(uuid4()),
        "cedula": cid,
        "nombre": nombre,
        "agencia": agencia,
        "features": feats,
        "prediccion": {
            "probabilidad_mora": round(prob, 4),
            "nivel_riesgo": nivel,
            "modelo": "cootech_preventivo",
            "senales": senales,
            "al_dia": bool(row.get("al_dia_actual", False)),
            "credito_vigente": bool(row.get("credito_vigente", True)),
        },
    }


def import_cootech_bundle(files: list[tuple[str, bytes]]) -> dict[str, Any]:
    t0 = time.perf_counter()
    df, meta = build_cootech_features(files)
    bundle = train_or_load(df)
    scored = predict_df(df, bundle)

    # Dashboard: crédito vigente; ranking preventivo (al día primero)
    vigentes = scored[scored["credito_vigente"] == True]  # noqa: E712
    preventivos = vigentes[vigentes["al_dia_actual"] == True]  # noqa: E712
    display_df = preventivos if len(preventivos) > 0 else vigentes

    socios = [_row_to_socio(display_df.iloc[i]) for i in range(len(display_df))]

    probs_prev = [
        s["prediccion"]["probabilidad_mora"]
        for s in socios
        if s["prediccion"].get("al_dia")
    ]
    by_level = {"bajo": 0, "medio": 0, "alto": 0}
    for s in socios:
        if not s["prediccion"].get("al_dia"):
            continue
        lvl = s["prediccion"]["nivel_riesgo"]
        by_level[lvl] = by_level.get(lvl, 0) + 1

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "mode": "cootech_bundle",
        "modelo": bundle.get("type", "heuristic"),
        "total": len(socios),
        "socios": socios,
        "meta": meta,
        "metricas_modelo": bundle.get("metrics", {}),
        "probabilidad_promedio": round(sum(probs_prev) / len(probs_prev), 4)
        if probs_prev
        else 0,
        "stats_cootech": {
            "total_clientes": meta.get("total_clientes", len(df)),
            "clientes_vigentes": meta.get("clientes_vigentes", 0),
            "clientes_al_dia": meta.get("clientes_al_dia", 0),
            "monitoreados_preventivos": len(preventivos),
            "por_nivel_preventivo": by_level,
            "tiempo_ms": elapsed_ms,
        },
        "mensaje_extra": (
            f" Analizados {len(files)} archivos en {elapsed_ms} ms."
            f" Foco: {len(preventivos)} socios con crédito vigente y al día."
        ),
    }
