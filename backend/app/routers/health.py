from fastapi import APIRouter

from app.config import settings
from app.ml.predictor import get_predictor
from app.services.supabase_client import is_configured

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    model_ok = False
    model_error = None
    try:
        get_predictor().load()
        model_ok = True
    except Exception as exc:
        model_error = str(exc)

    return {
        "status": "ok" if model_ok else "degraded",
        "app": settings.app_name,
        "model_loaded": model_ok,
        "model_error": model_error,
        "supabase_configured": is_configured(),
        "model_dir": str(settings.model_dir),
    }
