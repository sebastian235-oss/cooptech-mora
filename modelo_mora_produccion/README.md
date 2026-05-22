# Modelo de producción — CoopTech Mora

## Archivo activo (único para predicciones)

| Archivo | Uso |
|---------|-----|
| **modelo_mora_futura.pkl** | Modelo LightGBM entrenado (185 features) |
| **config.json** | Umbrales y métricas |
| **predict.py** | Lógica de scoring |

## Carpeta `demo/` (solo respaldo)

| Archivo | Uso |
|---------|-----|
| demo/modelo_mora.pkl | RandomForest demo — **no usar en producción** |
| demo/scaler.pkl | Escalador del demo |
| demo/feature_columns.json | 12 variables del demo |

> **Importante:** No dejes `modelo_mora.pkl` en la raíz de esta carpeta. Eso confundía al sistema. Solo debe existir `modelo_mora_futura.pkl` aquí.

## Generar demo (opcional)

```bash
python train_demo_model.py
```

Guarda artefactos en `demo/`.

## Uso

```python
from predict import MoraPredictor
pred = MoraPredictor()
resultado = pred.score(mi_dataframe)
```
