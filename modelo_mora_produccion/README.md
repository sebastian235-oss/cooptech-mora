# Modelo de producción — Mora CoopTech

Coloca aquí los artefactos de tu modelo entrenado:

| Archivo | Descripción |
|---------|-------------|
| `modelo_mora.pkl` o `model.pkl` | Modelo sklearn/joblib |
| `scaler.pkl` | Escalador/preprocesador (opcional) |
| `feature_columns.json` | Lista de columnas de entrada |

## Usar tu modelo existente

1. Copia tus archivos `.pkl` desde tu carpeta local `modelo_mora_produccion`.
2. Crea `feature_columns.json` con las columnas exactas que usó el entrenamiento:

```json
{
  "feature_columns": ["col1", "col2", "..."]
}
```

3. Reinicia el backend.

## Modelo demo (si aún no subes el tuyo)

```bash
python modelo_mora_produccion/train_demo_model.py
```
