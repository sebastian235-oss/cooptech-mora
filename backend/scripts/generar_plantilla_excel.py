#!/usr/bin/env python3
"""Genera samples/plantilla_tabla_maestra.xlsx para carga en el dashboard."""

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[2] / "samples" / "plantilla_tabla_maestra.xlsx"

COLUMNS = [
    "NRO_CLIENTE",
    "NOMBRE",
    "DIAS_MORA",
    "SALDO_VENCIDO",
    "INGRESOS",
    "EGRESOS",
    "CUOTAS_ATRASADAS",
    "NUM_MOVIMIENTOS_30D",
    "VARIACION_SALDO",
    "RATIO_PAGO",
]

EXAMPLE = [
    {
        "NRO_CLIENTE": "1001",
        "NOMBRE": "Ejemplo Socio A",
        "DIAS_MORA": 0,
        "SALDO_VENCIDO": 0,
        "INGRESOS": 1200,
        "EGRESOS": 800,
        "CUOTAS_ATRASADAS": 0,
        "NUM_MOVIMIENTOS_30D": 12,
        "VARIACION_SALDO": 0.05,
        "RATIO_PAGO": 1.0,
    },
    {
        "NRO_CLIENTE": "1002",
        "NOMBRE": "Ejemplo Socio B",
        "DIAS_MORA": 12,
        "SALDO_VENCIDO": 450,
        "INGRESOS": 900,
        "EGRESOS": 850,
        "CUOTAS_ATRASADAS": 2,
        "NUM_MOVIMIENTOS_30D": 3,
        "VARIACION_SALDO": -0.15,
        "RATIO_PAGO": 0.7,
    },
]

INSTRUCCIONES = pd.DataFrame(
    {
        "Campo": COLUMNS,
        "Descripción": [
            "ID único del socio (obligatorio)",
            "Nombre del socio",
            "Días de mora o desde último pago",
            "Saldo vencido actual",
            "Ingresos mensuales del socio",
            "Egresos mensuales",
            "Cuotas atrasadas máximas",
            "Movimientos últimos 30 días (opcional)",
            "Variación de saldo -1 a 1 (opcional)",
            "Ratio pago cuota 0-1 (opcional)",
        ],
    }
)


def main() -> None:
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        pd.DataFrame(EXAMPLE).to_excel(writer, sheet_name="Datos", index=False)
        INSTRUCCIONES.to_excel(writer, sheet_name="Instrucciones", index=False)
    print(f"Plantilla creada: {OUT}")


if __name__ == "__main__":
    main()
