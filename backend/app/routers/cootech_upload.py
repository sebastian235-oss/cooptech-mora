import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.cootech_import import import_cootech_bundle

router = APIRouter(prefix="/socios", tags=["cootech"])


@router.post("/upload-cootech")
async def upload_cootech(files: list[UploadFile] = File(...)):
    """
    Sube el paquete CoopTech: DataSabanaCred* (obligatorio),
    DatsSabanaAhorro* y Trns* (opcionales, mejoran el score).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Selecciona al menos un archivo.")

    bundle: list[tuple[str, bytes]] = []
    total_bytes = 0
    for f in files:
        if not f.filename:
            continue
        content = await f.read()
        total_bytes += len(content)
        bundle.append((f.filename, content))

    if not bundle:
        raise HTTPException(status_code=400, detail="Ningún archivo válido.")

    if total_bytes > 80 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Paquete demasiado grande (máx. 80 MB).")

    try:
        result = await asyncio.to_thread(import_cootech_bundle, bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error procesando paquete CoopTech: {exc}"
        ) from exc

    socios = result["socios"]
    from app.routers import socios as socios_router

    socios_router.set_uploaded_socios(socios)
    socios_router.set_cootech_stats(result.get("stats_cootech"))

    if settings.sync_supabase_on_upload:
        from datetime import datetime, timezone

        from app.services import supabase_client

        if supabase_client.is_configured():
            for s in socios[:100]:
                p = s.get("prediccion", {})
                try:
                    await supabase_client.upsert_prediccion(
                        {
                            "socio_id": s["id"],
                            "probabilidad_mora": p.get("probabilidad_mora", 0),
                            "nivel_riesgo": p.get("nivel_riesgo", "bajo"),
                            "features": {},
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                except Exception:
                    pass

    stats = result.get("stats_cootech", {})
    meta = result.get("meta", {})
    errores = meta.get("errores", [])
    err_txt = f" Advertencias: {'; '.join(errores[:3])}" if errores else ""

    return {
        "ok": True,
        "modo": result["mode"],
        "modelo": result.get("modelo"),
        "archivos": len(bundle),
        "total_procesados": result["total"],
        "probabilidad_promedio": result.get("probabilidad_promedio"),
        "stats_cootech": stats,
        "metricas_modelo": result.get("metricas_modelo"),
        "mensaje": (
            f"CoopTech: {result['total']} socios en riesgo preventivo "
            f"({stats.get('clientes_al_dia', 0)} al día de "
            f"{stats.get('clientes_vigentes', 0)} vigentes). "
            f"Carga en {stats.get('tiempo_ms', 0)} ms.{err_txt}"
        ),
    }
