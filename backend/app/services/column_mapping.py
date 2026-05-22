"""Mapeo de columnas típicas de tabla maestra de mora → esquema del modelo."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Tras normalizar: minúsculas, guiones bajos, sin tildes ni signos
TABLA_MAESTRA_ALIASES: dict[str, str] = {
    # Identificación
    "codigo_cliente": "nro_cliente",
    "cod_cliente": "nro_cliente",
    "idcliente": "nro_cliente",
    "id_cliente": "nro_cliente",
    "cliente": "nro_cliente",
    "socio": "nro_cliente",
    "numero_cliente": "nro_cliente",
    "nro_socio": "nro_cliente",
    "identificacion": "cedula",
    "identificacin": "cedula",
    "cedula_socio": "cedula",
    "ruc": "cedula",
    "dni": "cedula",
    # Nombre
    "nombres": "nombre",
    "nombre_socio": "nombre",
    "nombre_cliente": "nombre",
    "nombre_completo": "nombre",
    "razon_social": "nombre",
    # Mora / pagos (tabla maestra suele traer dias_mora)
    "dias_mora": "dias_desde_ultimo_pago_max",
    "dias_de_mora": "dias_desde_ultimo_pago_max",
    "dia_mora": "dias_desde_ultimo_pago_max",
    "dias_atraso": "dias_atraso_promedio",
    "dias_atrasados": "dias_atraso_promedio",
    "max_dias_mora": "dias_desde_ultimo_pago_max",
    "cuotas_atrasadas": "hist_cuotas_atrasadas_max",
    "nro_cuotas_atrasadas": "hist_cuotas_atrasadas_max",
    "cuotas_atra": "hist_cuotas_atrasadas_max",
    # Saldos
    "saldo_vencido": "saldo_vencido_actual_total",
    "saldo_vencido_total": "saldo_vencido_actual_total",
    "saldo_mora": "saldo_vencido_actual_total",
    "saldo_capital": "saldo_vencido_actual_total",
    "saldo_deuda": "saldo_vencido_actual_total",
    "saldo_promedio": "saldo_promedio_cuenta",
    "saldo_ahorro": "saldo_promedio_cuenta",
    # Ingresos / egresos
    "ingreso": "ingresos_socio",
    "ingresos": "ingresos_socio",
    "egreso": "egresos_socio",
    "egresos": "egresos_socio",
    "capacidad_de_pago": "capacidad_pago",
    # Créditos / movimientos
    "num_creditos": "n_creditos_unicos",
    "nro_creditos": "n_creditos_unicos",
    "operaciones": "n_operaciones_credito",
    "nro_operaciones": "n_operaciones_credito",
    "movimientos": "num_movimientos_30d",
    "nro_movimientos": "num_movimientos_30d",
    "variacion_saldo": "variacion_saldo_30d",
    "var_saldo": "variacion_saldo_30d",
    "ratio_pago": "ratio_pago_cuota",
    "ratio_egreso_ingreso": "ratio_egresos_ingresos",
    "num_movimientos_30d": "num_movimientos_30d",
    "n_movimientos_30d": "num_movimientos_30d",
    "movimientos_30d": "num_movimientos_30d",
}

# Solo columnas que nunca deben entrar al modelo (target / fuga)
LEAKAGE_ONLY = {
    "target_mora_futura",
    "target_mora",
    "dias_mora_futuro",
    "saldo_vencido_futuro",
    "mora_actual",
    "max_dias_mora_actual",
}


def norm_col(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def apply_tabla_maestra_aliases(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Renombra columnas conocidas de tabla maestra. Devuelve (df, mensajes)."""
    out = df.copy()
    out.columns = [norm_col(c) for c in out.columns]
    messages: list[str] = []
    renames: dict[str, str] = {}
    used_targets: set[str] = set()

    for col in list(out.columns):
        target = TABLA_MAESTRA_ALIASES.get(col)
        if not target or col == target:
            continue
        if target in out.columns and target not in used_targets:
            # Ya existe la columna destino; no sobrescribir
            continue
        renames[col] = target
        used_targets.add(target)
        messages.append(f"{col} → {target}")

    if renames:
        out = out.rename(columns=renames)
    out = out.loc[:, ~out.columns.duplicated()]
    out = enrich_derived_columns(out)
    return out, messages


def enrich_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula ratios/capacidad si la tabla maestra trae ingresos y egresos."""
    out = df.copy()
    if "ingresos_socio" in out.columns and "egresos_socio" in out.columns:
        ing = pd.to_numeric(out["ingresos_socio"], errors="coerce")
        egr = pd.to_numeric(out["egresos_socio"], errors="coerce")
        if "ratio_egresos_ingresos" not in out.columns:
            out["ratio_egresos_ingresos"] = (egr / ing.replace(0, np.nan)).fillna(0)
        if "capacidad_pago" not in out.columns:
            out["capacidad_pago"] = (ing - egr).fillna(0)
    return out


def diagnose_columns(columns: list[str], model_features: list[str]) -> dict:
    """Informe de compatibilidad con el modelo."""
    normed = [norm_col(c) for c in columns]
    mapped = set()
    for c in normed:
        mapped.add(TABLA_MAESTRA_ALIASES.get(c, c))
    overlap = [f for f in model_features if f in mapped]
    alias_hits = [c for c in normed if c in TABLA_MAESTRA_ALIASES]
    return {
        "columnas_archivo": normed,
        "columnas_mapeadas": alias_hits,
        "coinciden_modelo": overlap,
        "coinciden_modelo_count": len(overlap),
        "features_modelo_total": len(model_features),
        "cobertura_esperada_pct": round(len(overlap) / max(len(model_features), 1) * 100, 1),
    }
