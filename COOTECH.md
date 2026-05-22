# Flujo CoopTech (sábana crédito + ahorro + transacciones)

## Archivos esperados (misma carpeta `Datos`)

| Prefijo | Ejemplo | Rol |
|---------|---------|-----|
| `DataSabanaCred` | `DataSabanaCred18Mayo2026.xls` | **Pivote** — créditos vigentes, días de mora |
| `DatsSabanaAhorro` | `DatsSabanaAhorroMayo1_2026.csv` | Saldos y variación de ahorro |
| `Trns` | `Trns 01 10 Mayo 2026.csv` | Movimientos y actividad |

Sube **todos** a la vez con **Paquete CoopTech** en el dashboard (o `POST /api/socios/upload-cootech`).

## Qué predice

- **Población:** socios con crédito vigente, foco en los **al día** (preventivo).
- **Objetivo:** probabilidad de **caer en mora el próximo mes** (proxy: nuevos días de mora entre cortes de crédito).
- Socios **ya en mora** aparecen con riesgo bajo y señal *Ya en mora actual*.

## Demo local

```bash
python3 scripts/generate_cootech_demo.py
cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8000
# En otra terminal: cd frontend && npm run dev
# Subir todos los archivos de samples/cootech_demo/
```

## API

- `POST /api/socios/upload-cootech` — multipart, campo `files` (repetido por archivo).
- Respuesta incluye `stats_cootech.tiempo_ms` (objetivo < 5 s con ~100k filas de transacciones.

Límite de subida por defecto: **512 MB** (`COOTECH_MAX_UPLOAD_MB` en el backend).

## Datos reales

Copia tus archivos de `DATOS DE COOTECH/Datos/` a `datos_cootech/` en el repo (o súbelos por la UI). Si faltan columnas, amplía `backend/app/services/cootech_schema.py` (`COLUMN_ALIASES`).
