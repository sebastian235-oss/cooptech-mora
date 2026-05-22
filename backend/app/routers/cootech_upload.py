import asyncio
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.services.cootech_import import import_cootech_bundle
from app.services.cootech_session import (
    add_file,
    clear_session,
    get_bundle,
    new_session,
    session_info,
)

router = APIRouter(prefix="/socios", tags=["cootech"])


def _response_from_result(result: dict[str, Any], archivos: int) -> dict[str, Any]:
    from app.routers import socios as socios_router

    socios = result["socios"]
    socios_router.set_uploaded_socios(socios)
    socios_router.set_cootech_stats(result.get("stats_cootech"))

    stats = result.get("stats_cootech", {})
    meta = result.get("meta", {})
    errores = meta.get("errores", [])
    err_txt = f" Advertencias: {'; '.join(errores[:3])}" if errores else ""

    return {
        "ok": True,
        "modo": result["mode"],
        "modelo": result.get("modelo"),
        "archivos": archivos,
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


async def _maybe_sync_supabase(socios: list[dict]) -> None:
    if not settings.sync_supabase_on_upload:
        return
    from datetime import datetime, timezone

    from app.services import supabase_client

    if not supabase_client.is_configured():
        return
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


@router.post("/upload-cootech/session")
async def cootech_new_session():
    """Inicia carga por partes (un archivo por petición)."""
    sid = new_session()
    return {"session_id": sid, "mensaje": "Sesión creada. Sube cada archivo y luego procesa."}


@router.post("/upload-cootech/file")
async def cootech_upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Añade un archivo a la sesión (evita límite de tamaño del paquete único)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo sin nombre.")
    content = await file.read()
    try:
        info = add_file(session_id, file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **info}


@router.get("/upload-cootech/session/{session_id}")
async def cootech_session_status(session_id: str):
    return session_info(session_id)


@router.post("/upload-cootech/process")
async def cootech_process(session_id: str = Form(...)):
    """Procesa todos los archivos acumulados en la sesión."""
    try:
        bundle = get_bundle(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await asyncio.to_thread(import_cootech_bundle, bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error procesando paquete CoopTech: {exc}"
        ) from exc
    finally:
        clear_session(session_id)

    await _maybe_sync_supabase(result["socios"])
    return _response_from_result(result, len(bundle))


@router.delete("/upload-cootech/session/{session_id}")
async def cootech_cancel_session(session_id: str):
    clear_session(session_id)
    return {"ok": True, "mensaje": "Sesión cancelada."}


@router.post("/upload-cootech")
async def upload_cootech(files: list[UploadFile] = File(...)):
    """
    Sube el paquete completo en una sola petición (archivos pequeños).
    Para 12 archivos grandes, el front usa carga por sesión (archivo a archivo).
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

    max_bytes = settings.cootech_max_upload_mb * 1024 * 1024
    if total_bytes > max_bytes:
        mb = round(total_bytes / (1024 * 1024), 1)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Paquete demasiado grande ({mb} MB). "
                f"Máximo en una sola petición: {settings.cootech_max_upload_mb} MB. "
                "La app subirá archivo por archivo automáticamente; actualiza el backend en Render."
            ),
        )

    try:
        result = await asyncio.to_thread(import_cootech_bundle, bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error procesando paquete CoopTech: {exc}"
        ) from exc

    await _maybe_sync_supabase(result["socios"])
    return _response_from_result(result, len(bundle))
