#!/usr/bin/env python3
"""Genera archivos demo con el mismo patrón de nombres CoopTech."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "samples" / "cootech_demo"
N_SOCIOS = 800


def main() -> None:
    random.seed(42)
    np.random.seed(42)
    OUT.mkdir(parents=True, exist_ok=True)

    ids = [f"{100000 + i}" for i in range(N_SOCIOS)]
    nombres = [f"Socio Demo {i}" for i in range(N_SOCIOS)]
    agencias = np.random.choice(["Tulcán", "Mira", "El Ángel"], N_SOCIOS)

    # Crédito — 3 cortes (simula mora futura en ~8% al día)
    for tag, fecha, mora_shift in [
        ("1Mayo2026", "2026-05-01", 0),
        ("11Mayo2026", "2026-05-11", 0),
        ("18Mayo2026", "2026-05-18", 1),
    ]:
        dias = np.zeros(N_SOCIOS, dtype=int)
        if mora_shift:
            at_risk = np.random.choice(N_SOCIOS, size=int(N_SOCIOS * 0.08), replace=False)
            dias[at_risk] = np.random.randint(1, 45, len(at_risk))
        df = pd.DataFrame(
            {
                "NRO_CLIENTE": ids,
                "NOMBRES": nombres,
                "AGENCIA": agencias,
                "DIAS_MORA": dias,
                "CUOTAS_ATRASADAS": (dias > 0).astype(int),
                "SALDO_CAPITAL": np.random.uniform(500, 15000, N_SOCIOS),
                "SALDO_VENCIDO": np.where(dias > 0, np.random.uniform(50, 500, N_SOCIOS), 0),
                "MONTO_CREDITO": np.random.uniform(1000, 20000, N_SOCIOS),
                "ESTADO": "VIGENTE",
                "FECHA_CORTE": fecha,
            }
        )
        path = OUT / f"DataSabanaCred{tag}.xlsx"
        df.to_excel(path, index=False, engine="openpyxl")
        print("wrote", path)

    for mes, fname in [
        ("Marzo", "DatsSabanaAhorroMarzo1_2026.csv"),
        ("Abril", "DatsSabanaAhorroAbril1_2026.csv"),
        ("Mayo", "DatsSabanaAhorroMayo1_2026.csv"),
    ]:
        saldo = np.random.uniform(100, 5000, N_SOCIOS)
        df = pd.DataFrame(
            {
                "NRO_CLIENTE": ids,
                "SALDO_AHORRO": saldo,
                "MONTO": np.random.uniform(10, 200, N_SOCIOS),
                "FECHA": f"2026-{mes[:3]}-15",
            }
        )
        path = OUT / fname
        df.to_csv(path, index=False)
        print("wrote", path)

    for fname in [
        "Trns 01 15 Marzo 2026.csv",
        "Trns 16 31  Marzo 2026.csv",
        "Trns 01 15 Abril 2026.csv",
        "Trns 16 30 Abril 2026.csv",
        "Trns 01 10 Mayo 2026.csv",
        "Trns11 19 Mayo 2026.csv",
    ]:
        n_mov = np.random.poisson(12, N_SOCIOS)
        rows = []
        for i, cid in enumerate(ids):
            for _ in range(max(1, int(n_mov[i] / 6))):
                rows.append(
                    {
                        "NRO_CLIENTE": cid,
                        "MONTO": round(random.uniform(5, 400), 2),
                        "FECHA": "2026-05-10",
                        "TIPO_OPERACION": random.choice(["DEP", "RET", "PAG"]),
                    }
                )
        path = OUT / fname
        pd.DataFrame(rows).to_csv(path, index=False)
        print("wrote", path, len(rows), "filas")


if __name__ == "__main__":
    main()
