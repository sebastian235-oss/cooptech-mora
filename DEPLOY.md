# Guía de despliegue (< 2 horas)

## Paso 1 — Subir tu modelo real (opcional pero recomendado)

Desde tu PC (`c:\Users\gt\Desktop\ggg\modelo_mora_produccion`):

```bash
git add modelo_mora_produccion/*.pkl modelo_mora_produccion/feature_columns.json
git commit -m "Modelo producción CoopTech"
git push
```

Archivos esperados: `modelo_mora.pkl`, `scaler.pkl`, `feature_columns.json`.

## Paso 2 — Supabase

1. [supabase.com](https://supabase.com) → New Project
2. SQL Editor → pegar `supabase/migrations/001_schema.sql` → Run
3. Settings → API → copiar:
   - Project URL → `SUPABASE_URL`
   - `service_role` (secret) → `SUPABASE_SERVICE_KEY`
   - `anon` → `VITE_SUPABASE_ANON_KEY`

## Paso 3 — API en Render

1. [dashboard.render.com](https://dashboard.render.com) → New → Web Service
2. Conectar GitHub `sebastian235-oss/cooptech-mora`
3. Runtime: **Docker** (usa `Dockerfile` del repo)
4. Environment:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `CORS_ORIGINS` = URL de Vercel (ej. `https://cooptech-mora.vercel.app`)
5. Deploy → copiar URL (ej. `https://cooptech-mora-api.onrender.com`)

Probar: `https://TU-API.onrender.com/api/health`

## Paso 4 — Frontend en Vercel

1. [vercel.com](https://vercel.com) → Add Project → importar repo
2. **Root Directory:** `frontend`
3. Environment Variable:
   - `VITE_API_URL` = `https://TU-API.onrender.com/api`
4. Deploy

## Paso 5 — Verificación

- Dashboard carga socios y gráficos
- Badge cambia a "Supabase conectado" cuando las variables del backend están bien
- Ejecutar `supabase/seed.sql` si quieres datos iniciales en BD

## Variables resumen

| Variable | Dónde |
|----------|--------|
| `SUPABASE_URL` | Render (backend) |
| `SUPABASE_SERVICE_KEY` | Render (backend) |
| `CORS_ORIGINS` | Render (backend) |
| `VITE_API_URL` | Vercel (frontend) |
