# CoopTech Tulcán — Guía DevIAthon (Prevención de Mora)

## Reto

**Pregunta:** ¿Cómo perfilar el comportamiento transaccional de los socios con crédito vigente para **prevenir** la morosidad?

**Respuesta del MVP:** Dashboard web que carga datos (Excel o manual), calcula probabilidad de caer en mora en el siguiente período, muestra señales (atrasos, saldo vencido, egresos altos, etc.) y clasifica en riesgo bajo / medio / alto para acciones de cobranza preventiva.

Vertical del evento: **Inclusión financiera (Fintech)** — Cooperativas de ahorro y crédito.

## Estructura del proyecto

| Carpeta | Contenido |
|---------|-----------|
| `frontend/` | Dashboard React (Vite) |
| `backend/` | API FastAPI |
| `modelo_mora_produccion/` | Modelo LightGBM (`modelo_mora_futura.pkl`) |
| `samples/` | Excel de prueba (`tabla_maestra_mora_test.xlsx`) |
| `supabase/` | Esquema opcional para persistencia |

## Tu archivo de muestra (tabla maestra)

Columnas detectadas en `tabla_maestra_mora_test.xlsx`:

| Columna Excel | Se mapea a |
|---------------|------------|
| NRO_CLIENTE | nro_cliente |
| NOMBRE | nombre |
| DIAS_MORA | dias_desde_ultimo_pago_max |
| SALDO_VENCIDO | saldo_vencido_actual_total |
| INGRESOS / EGRESOS | ingresos_socio / egresos_socio |
| CUOTAS_ATRASADAS | hist_cuotas_atrasadas_max |

El modelo fue entrenado con **185 features**. Con solo 7 columnas la cobertura es ~4%. El sistema:

1. Ejecuta el modelo ML (con imputación por medianas).
2. Si cobertura &lt; 35%, activa **ranking relativo** por señales de tabla maestra para ordenar socios en el dashboard.

Para predicciones ML más fieles, usa el export completo `dataset_entrenamiento_prevencion.csv` (162 columnas) en la carpeta del modelo.

## Inicio rápido (Windows)

Copia tu Excel a `samples\`:

```cmd
copy "C:\Users\gt\Desktop\tabla_maestra_mora,test.xlsx" samples\tabla_maestra_mora_test.xlsx
```

### Backend

```cmd
cd backend
pip install -r requirements.txt
set PYTHONPATH=.
uvicorn app.main:app --reload --port 8000
```

### Frontend

```cmd
cd frontend
npm install
set VITE_API_URL=http://localhost:8000/api
npm run dev
```

Abre http://localhost:5173 → **Subir Excel** → revisar tabla y **Exportar CSV**.

### Diagnóstico del Excel (sin cargar dashboard)

```cmd
cd backend
set PYTHONPATH=.
python scripts\analyze_excel.py ..\samples\tabla_maestra_mora_test.xlsx
```

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del modelo |
| GET | `/api/socios/dashboard` | KPIs + socios |
| POST | `/api/socios/upload-excel` | Carga y scoring |
| POST | `/api/socios/analyze-excel` | Solo diagnóstico de columnas |
| GET | `/api/socios/export-csv` | Descarga resultados |
| POST | `/api/socios` | Cliente manual |

## Despliegue

Ver `DEPLOY.md` (Render + Vercel + Supabase opcional).

## Equipo / entrega hackathon

1. Demo en vivo: subir `tabla_maestra_mora_test.xlsx` y mostrar ranking + señales.
2. Explicar que el modelo predice **mora futura** en socios al día (sin fugas de datos).
3. Mencionar métricas holdout en `modelo_mora_produccion/config.json` (AUC, recall preventivo).
4. Opcional: conectar Supabase para historial.
