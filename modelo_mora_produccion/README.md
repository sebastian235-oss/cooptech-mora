# modelo_mora_produccion — Modelo entrenado CoopTech

## Archivos obligatorios (copiar desde tu PC)

Copia **toda** tu carpeta entrenada, por ejemplo desde:

`C:\Users\gt\Desktop\ggg\modelo_mora_produccion`

| Archivo | Requerido |
|---------|-----------|
| **modelo_mora_futura.pkl** | Sí — modelo LightGBM |
| **config.json** | Sí — umbrales y configuración |
| **predict.py** | Sí — lógica de scoring |

Opcional: `datos_entrenamiento_x_train.csv` (solo si el .pkl no trae `xt_agg` embebido).

## No usar en esta carpeta

- No agregues `modelo_mora.pkl` ni `scaler.pkl` sueltos (eran del demo viejo).
- Solo debe existir **un** modelo activo: `modelo_mora_futura.pkl`.

## Probar localmente

```bash
python predict.py ruta_a_tu_archivo.csv
```

## En la API web

El backend carga automáticamente `modelo_mora_futura.pkl` y procesa Excel/CSV **sin límite de filas** (20.000+).
