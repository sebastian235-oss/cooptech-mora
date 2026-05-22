from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.ml.predictor import get_predictor, predict_from_features
from app.schemas import PredictBatchRequest, PredictRequest, PredictResponse
from app.services import supabase_client

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
async def predict_single(body: PredictRequest):
    try:
        feats = dict(body.features)
        if body.socio_id:
            feats.setdefault("cliente_id", body.socio_id)
            feats.setdefault("cedula", body.socio_id)
        result = predict_from_features(feats)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en predicción: {exc}") from exc

    guardado = False
    if body.socio_id and supabase_client.is_configured():
        payload = {
            "socio_id": body.socio_id,
            "probabilidad_mora": result["probabilidad_mora"],
            "nivel_riesgo": result["nivel_riesgo"],
            "features": result["features_usadas"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = await supabase_client.upsert_prediccion(payload)
        guardado = saved is not None

    return PredictResponse(
        socio_id=body.socio_id,
        probabilidad_mora=result["probabilidad_mora"],
        nivel_riesgo=result["nivel_riesgo"],
        features_usadas=result.get("features_usadas", body.features),
        guardado_en_supabase=guardado,
        modelo=result.get("modelo"),
    )


@router.post("/batch")
async def predict_batch(body: PredictBatchRequest):
    try:
        results = get_predictor().predict_batch(body.records)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"count": len(results), "results": results}
