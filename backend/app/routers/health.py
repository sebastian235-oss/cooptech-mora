from fastapi import APIRouter

from app.config import settings
from app.ml import production_scorer
from app.services.supabase_client import is_configured

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    prod_ok = production_scorer.production_available()
    limite = (
        "sin_limite"
        if settings.max_upload_rows <= 0
        else str(settings.max_upload_rows)
    )
    return {
        "status": "ok" if prod_ok else "degraded",
        "app": settings.app_name,
        "modelo_unico": "modelo_mora_futura.pkl",
        "modelo_cargado": prod_ok,
        "modelo_error": production_scorer.production_error(),
        "max_filas_excel": limite,
        "supabase_configured": is_configured(),
        "model_dir": str(settings.model_dir),
    }
