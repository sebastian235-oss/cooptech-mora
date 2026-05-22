# Modelo de Prevención de Mora Futura

Modelo **LightGBM** para predecir si un socio con **crédito vigente y al día** caerá en **mora en el período siguiente**.

## Por qué este modelo (y no los otros)

| Modelo | Target | Problema |
|--------|--------|----------|
| `modelo_x_train_mora.pkl` | `TARGET_MORA` (mora **actual**) | Fuga conceptual: casi todos con prob alta **ya están en mora** |
| **`modelo_mora_futura.pkl`** | **`target_mora_futura`** | Correcto para **prevención** — predice mora **antes** de que ocurra |

### Variables excluidas (sin fuga)

No usar en scoring ni entrenamiento:

- `mora_actual`, `max_dias_mora_actual`
- `dias_mora_futuro`, `saldo_vencido_futuro`
- `TARGET_MORA`, `dias_mora`, `saldo_vencido` (datasets x_train)

## Métricas realistas (holdout `dataset_test_temporal`)

Ver `config.json` → `metricas_holdout_test_temporal`

## Archivos

```
modelo_mora_produccion/
├── modelo_mora_futura.pkl   # Modelo + encoders + features
├── config.json              # Métricas, umbrales, documentación
├── predict.py               # Clase MoraPredictor para integrar
├── train_modelo_produccion.py
├── requirements.txt
└── README.md
```

## Instalación

```bash
pip install -r requirements.txt
```

Copia la carpeta **`modelo_mora_produccion/`** completa a tu proyecto. El archivo `.pkl` ya incluye las features agregadas de crédito (`xt_agg`); no requiere archivos extra.

## Uso en Python

```python
from predict import MoraPredictor

predictor = MoraPredictor()
resultado = predictor.score_csv("dataset_test_temporal.csv")

# Lista preventiva (al día + riesgo muy alto)
preventivos = predictor.score_preventivo(pd.read_csv("dataset_test_temporal.csv"))
print(f"Socios a contactar: {len(preventivos)}")
print(preventivos[["cliente_id", "prob_mora_futura", "accion"]].head())
```

## Schema de entrada

Mismo formato que `dataset_entrenamiento_prevencion.csv` (162 columnas).

**Crédito vigente:** `n_creditos_unicos > 0` o `n_operaciones_credito > 0`.

## Umbrales (config.json)

- `f1_optimo` (~0.38): clasificación binaria mora / no mora
- `alerta_alta` (0.50): cola de riesgo para acción preventiva

## Reentrenar

```bash
cd modelo_mora_produccion
python train_modelo_produccion.py
```
