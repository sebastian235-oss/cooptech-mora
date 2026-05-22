"""Score heurístico cuando el Excel trae pocas columnas (tabla maestra resumida)."""

from __future__ import annotations

from typing import Any

import numpy as np

LOW_COVERAGE_THRESHOLD = 0.35


def tabla_maestra_proxy_score(feats: dict[str, float]) -> float:
    """0–1 a partir de señales típicas de tabla maestra de mora."""
    score = 0.0

    dias = float(feats.get("dias_desde_ultimo_pago_max") or feats.get("dias_mora") or 0)
    score += min(max(dias, 0) / 45.0, 1.0) * 0.35

    saldo = float(
        feats.get("saldo_vencido_actual_total")
        or feats.get("saldo_vencido")
        or feats.get("saldo_mora")
        or 0
    )
    score += min(max(saldo, 0) / 3000.0, 1.0) * 0.25

    ratio = float(feats.get("ratio_egresos_ingresos") or 0)
    if ratio > 0.5:
        score += min((ratio - 0.5) / 0.5, 1.0) * 0.2

    cuotas = float(
        feats.get("hist_cuotas_atrasadas_max")
        or feats.get("cuotas_atrasadas")
        or 0
    )
    score += min(max(cuotas, 0) / 5.0, 1.0) * 0.2

    return float(min(score, 1.0))


def apply_batch_ranking_for_low_coverage(socios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Si la cobertura del modelo es baja, ordena por score heurístico y asigna
    probabilidad de ranking relativa (5%–75%) para que el dashboard diferencie socios.
    Conserva probabilidad_mora_ml original.
    """
    if not socios:
        return socios

    coverages = [
        float(s.get("prediccion", {}).get("feature_coverage", 1)) for s in socios
    ]
    avg_cov = sum(coverages) / len(coverages)
    if avg_cov >= LOW_COVERAGE_THRESHOLD:
        for s in socios:
            pred = s.setdefault("prediccion", {})
            pred["modo_ranking"] = "modelo_ml"
        return socios

    proxies = [tabla_maestra_proxy_score(s.get("features") or {}) for s in socios]
    arr = np.array(proxies, dtype=float)
    if arr.max() == arr.min():
        ranked = np.full(len(arr), 0.25)
    else:
        order = arr.argsort().argsort()
        ranked = 0.05 + (order / max(len(order) - 1, 1)) * 0.70

    for i, s in enumerate(socios):
        pred = s.setdefault("prediccion", {})
        ml_prob = float(pred.get("probabilidad_mora", 0))
        pred["probabilidad_mora_ml"] = ml_prob
        pred["probabilidad_mora"] = round(float(ranked[i]), 6)
        pred["modo_ranking"] = "tabla_maestra_relativo"
        pred["score_proxy"] = round(proxies[i], 4)
        pred["nivel_riesgo"] = _nivel_from_prob(float(ranked[i]))

    return socios


def _nivel_from_prob(prob: float) -> str:
    if prob >= 0.5:
        return "alto"
    if prob >= 0.25:
        return "medio"
    return "bajo"
