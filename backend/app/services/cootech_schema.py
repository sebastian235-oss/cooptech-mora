"""Esquema y detección de archivos CoopTech (sábana crédito, ahorro, transacciones)."""

from __future__ import annotations

import re
from enum import Enum


class CootechFileKind(str, Enum):
    CREDITO = "credito"
    AHORRO = "ahorro"
    TRANSACCION = "transaccion"
    UNKNOWN = "unknown"


def norm_col(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"[^a-z0-9_]", "", s)


def detect_file_kind(filename: str) -> CootechFileKind:
    low = filename.lower().replace(" ", "")
    if "datasabanacred" in low or "sabanacred" in low:
        return CootechFileKind.CREDITO
    if "sabanaahorro" in low or "datssabanaahorro" in low or (
        "ahorro" in low and "cred" not in low
    ):
        return CootechFileKind.AHORRO
    if low.startswith("trns") or "trns" in low[:8] or "transacc" in low:
        return CootechFileKind.TRANSACCION
    return CootechFileKind.UNKNOWN


COLUMN_ALIASES: dict[str, str] = {
    "nrocliente": "cliente_id",
    "nro_cliente": "cliente_id",
    "codigo_cliente": "cliente_id",
    "cod_cliente": "cliente_id",
    "nro_socio": "cliente_id",
    "socio": "cliente_id",
    "identificacion": "cedula",
    "cedula": "cedula",
    "ruc": "cedula",
    "nombres": "nombre",
    "nombre_socio": "nombre",
    "nombre_cliente": "nombre",
    "razon_social": "nombre",
    "agencia": "agencia",
    "sucursal": "agencia",
    "oficina": "agencia",
    "diasmora": "dias_mora",
    "dias_mora": "dias_mora",
    "dias_de_mora": "dias_mora",
    "diasatraso": "dias_mora",
    "cuotasatrasadas": "cuotas_atrasadas",
    "nro_cuotas_atrasadas": "cuotas_atrasadas",
    "saldocapital": "saldo_capital",
    "saldo_capital": "saldo_capital",
    "saldo_vencido": "saldo_vencido",
    "saldo_vencido_total": "saldo_vencido",
    "montocredito": "monto_credito",
    "monto_credito": "monto_credito",
    "monto": "monto",
    "valor": "monto",
    "estado": "estado_credito",
    "estado_credito": "estado_credito",
    "estado_op": "estado_credito",
    "plazo": "plazo",
    "tasa": "tasa",
    "fecha": "fecha",
    "fechacorte": "fecha_corte",
    "fecha_corte": "fecha_corte",
    "fechatransaccion": "fecha",
    "fech_utl_tra": "fecha",
    "saldoahorro": "saldo_ahorro",
    "saldo_ahorro": "saldo_ahorro",
    "saldo": "saldo_ahorro",
    "tipooperacion": "tipo_operacion",
    "tipo_operacion": "tipo_operacion",
    "tipotransaccion": "tipo_operacion",
}


CREDITO_VIGENTE_STATES = {
    "vigente",
    "vig",
    "activo",
    "active",
    "al dia",
    "aldia",
    "corriente",
}


def canonicalize_columns(columns: list[str]) -> dict[str, str]:
    renames: dict[str, str] = {}
    for col in columns:
        n = norm_col(col)
        if n in COLUMN_ALIASES:
            renames[col] = COLUMN_ALIASES[n]
    return renames
