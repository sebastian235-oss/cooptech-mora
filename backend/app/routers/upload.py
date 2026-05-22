from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import supabase_client
from app.services.excel_import import import_excel

router = APIRouter(prefix="/socios", tags=["upload"])


@router.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo sin nombre.")

    allowed = (".xlsx", ".xls", ".xlsm", ".csv")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Formato no válido. Usa: {', '.join(allowed)}",
        )

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx. 15 MB).")

    try:
        result = import_excel(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error procesando archivo: {exc}"
        ) from exc

    socios = result["socios"]

    from app.routers import socios as socios_router

    socios_router.set_uploaded_socios(socios)

    if supabase_client.is_configured():
        client = supabase_client.get_supabase()
        for s in socios:
            p = s.get("prediccion", {})
            try:
                client.table("socios").upsert(
                    {
                        "cedula": s["cedula"],
                        "nombre": s["nombre"],
                        "agencia": s.get("agencia"),
                        "features": s.get("features", {}),
                    },
                    on_conflict="cedula",
                ).execute()
            except Exception:
                pass
            try:
                await supabase_client.upsert_prediccion(
                    {
                        "socio_id": s["id"],
                        "probabilidad_mora": p.get("probabilidad_mora", 0),
                        "nivel_riesgo": p.get("nivel_riesgo", "bajo"),
                        "features": p.get("features_usadas", s.get("features", {})),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except Exception:
                pass

    return {
        "ok": True,
        "archivo": file.filename,
        "modo": result["mode"],
        "total_procesados": result["total"],
        "columnas_detectadas": result.get("columnas_detectadas", []),
        "columnas_mapeadas": result.get("columnas_mapeadas"),
        "mensaje": f"Se cargaron {result['total']} socios correctamente.",
    }
