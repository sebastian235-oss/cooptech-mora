# CoopTech Tulcán — Prevención de Mora (DevIAthon)

MVP web para perfilar el comportamiento transaccional de socios con crédito vigente y estimar el riesgo de caer en mora, usando el modelo entrenado en `modelo_mora_produccion/`.

## Arquitectura

```
Excel / Supabase (socios, predicciones)
        ↓
   FastAPI (backend) ← modelo_mora_produccion/*.pkl
        ↓
   React Dashboard (frontend)
```

## Inicio rápido (local)

### 1. Modelo

Si ya tienes el modelo entrenado, copia los `.pkl` a `modelo_mora_produccion/`. Si no:

```bash
python modelo_mora_produccion/train_demo_model.py
```

### 2. Supabase

1. Crea proyecto en [supabase.com](https://supabase.com)
2. Ejecuta `supabase/migrations/001_schema.sql` en SQL Editor
3. Opcional: `supabase/seed.sql`
4. Copia URL y **service_role key** a `.env`

### 3. Backend

```bash
cp .env.example .env
# Edita SUPABASE_URL y SUPABASE_SERVICE_KEY
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
cp .env.example .env
# VITE_API_URL=http://localhost:8000/api
npm install && npm run dev
```

Abre http://localhost:5173

## Despliegue

| Componente | Plataforma sugerida |
|------------|---------------------|
| API + modelo | [Render](https://render.com) (`render.yaml` + Dockerfile) |
| Dashboard | [Vercel](https://vercel.com) (carpeta `frontend`) |
| Base de datos | Supabase |

### Render (API)

1. Conecta repo `sebastian235-oss/cooptech-mora`
2. New Web Service → Docker
3. Variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CORS_ORIGINS=https://tu-app.vercel.app`

### Vercel (Frontend)

1. Import proyecto, root: `frontend`
2. Variable: `VITE_API_URL=https://tu-api.onrender.com/api`

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del modelo y Supabase |
| GET | `/api/socios/dashboard` | KPIs + lista de socios |
| POST | `/api/predict` | Predicción individual |
| POST | `/api/socios` | Alta de socio + scoring |

## Reto CoopTech

**Pregunta:** ¿Cómo perfilar el comportamiento transaccional para prevenir morosidad?

**Respuesta del MVP:** Se calculan señales (atrasos, ratio de pago, variación de saldo, movimientos) y el modelo ML asigna probabilidad y nivel (bajo/medio/alto) para acciones preventivas de cobranza antes del incumplimiento formal.

## Equipo / notas

- Sube tu modelo real a `modelo_mora_produccion/` y define `feature_columns.json` con las mismas columnas del entrenamiento.
- Sin Supabase, el sistema funciona en **modo demo** con datos de ejemplo.
