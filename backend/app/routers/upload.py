import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.excel_import import import_excel

router = APIRouter(prefix="/socios", tags=["upload"])


@router.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo sin nombre.")

    allowed = (".xlsx", ".xls", ".csv")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Formato no válido. Usa: {', '.join(allowed)}",
        )

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx. 20 MB).")

    try:
        # Evita bloquear el event loop (causa de “cargando infinito” en el front)
        result = await asyncio.to_thread(import_excel, content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error procesando archivo: {exc}"
        ) from exc

    socios = result["socios"]

    from app.routers import socios as socios_router

    socios_router.set_uploaded_socios(socios)

    # Supabase fila a fila bloqueaba la respuesta; desactivado por defecto
    if settings.sync_supabase_on_upload:
        from app.services import supabase_client
        from datetime import datetime, timezone

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

    extra = result.get("mensaje_extra", "")
    trunc = result.get("truncado", 0)
    trunc_txt = f" Se omitieron {trunc} filas por límite." if trunc else ""

    return {
        "ok": True,
        "archivo": file.filename,
        "modo": result["mode"],
        "modelo": result.get("modelo"),
        "total_procesados": result["total"],
        "probabilidad_promedio": result.get("probabilidad_promedio"),
        "columnas_detectadas": result.get("columnas_detectadas", []),
        "mensaje": f"Se analizaron {result['total']} socios con el modelo de producción.{extra}{trunc_txt}",
    }
