#!/usr/bin/env python3
"""Analiza un Excel de tabla maestra (columnas vs modelo). Uso:
  cd backend && PYTHONPATH=. python scripts/analyze_excel.py ruta/al/archivo.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.services.column_mapping import apply_tabla_maestra_aliases, diagnose_columns
from app.services.excel_import import _read_file, import_excel, prod_features


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/analyze_excel.py <archivo.xlsx>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No existe: {path}")
        sys.exit(1)
    raw = _read_file(path.read_bytes(), path.name)
    df, msgs = apply_tabla_maestra_aliases(raw)
    diag = diagnose_columns(list(df.columns), prod_features())
    print(f"Archivo: {path.name} ({len(df)} filas)")
    print(f"Columnas originales ({len(raw.columns)}):", list(raw.columns)[:20], "...")
    print("Renombres:", msgs or "(ninguno)")
    print("Tras mapeo:", list(df.columns))
    print("Diagnóstico:", diag)
    res = import_excel(path.read_bytes(), path.name)
    print(f"Cobertura real modelo: {res.get('cobertura_features_promedio', 0):.1%}")
    print(f"Prob. promedio: {res.get('probabilidad_promedio', 0):.6f}")


if __name__ == "__main__":
    main()
