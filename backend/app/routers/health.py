from fastapi import APIRouter

from app.config import settings
from app.ml import production_scorer
from app.ml.predictor import get_simple_predictor
from app.services.supabase_client import is_configured

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    prod_ok = production_scorer.production_available()
    demo_ok = False
    demo_error = None
    try:
        get_simple_predictor().load()
        demo_ok = True
    except Exception as exc:
        demo_error = str(exc)

    ok = prod_ok or demo_ok
    return {
        "status": "ok" if ok else "degraded",
        "app": settings.app_name,
        "modelo_produccion": prod_ok,
        "modelo_produccion_error": production_scorer.production_error(),
        "modelo_demo": demo_ok,
        "modelo_demo_error": demo_error,
        "supabase_configured": is_configured(),
        "model_dir": str(settings.model_dir),
    }
