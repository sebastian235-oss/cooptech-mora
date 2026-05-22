from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.ml.predictor import predict_from_features
from app.schemas import SocioCreate
from app.services import supabase_client

router = APIRouter(prefix="/socios", tags=["socios"])

# Datos demo en memoria si Supabase no está configurado
_demo_socios: list[dict] = []
_uploaded_socios: list[dict] = []


def set_uploaded_socios(socios: list[dict]) -> None:
    global _uploaded_socios
    _uploaded_socios = socios


def _active_socios() -> list[dict]:
    if _uploaded_socios:
        return _uploaded_socios
    return _demo_socios


def _seed_demo():
    """Sin datos demo: usa Subir Excel o cliente manual."""
    return


@router.get("")
async def list_socios():
    if supabase_client.is_configured():
        data = await supabase_client.list_socios()
        return {"source": "supabase", "socios": data}
    _seed_demo()
    return {"source": "demo", "socios": _demo_socios}


@router.post("")
async def create_socio(body: SocioCreate):
    try:
        pred = predict_from_features(body.to_feature_dict())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    socio_id = str(uuid4())
    record = {
        "id": socio_id,
        "cedula": body.cedula,
        "nombre": body.nombre,
        "agencia": body.agencia,
        "telefono": body.telefono,
        "features": body.features,
        "prediccion": pred,
    }

    if supabase_client.is_configured():
        client = supabase_client.get_supabase()
        client.table("socios").insert(
            {
                "id": socio_id,
                "cedula": body.cedula,
                "nombre": body.nombre,
                "agencia": body.agencia,
                "telefono": body.telefono,
                "features": body.features,
            }
        ).execute()
        await supabase_client.upsert_prediccion(
            {
                "socio_id": socio_id,
                "probabilidad_mora": pred["probabilidad_mora"],
                "nivel_riesgo": pred["nivel_riesgo"],
                "features": pred["features_usadas"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {"source": "supabase", "socio": record}

    if _uploaded_socios:
        _uploaded_socios.append(record)
        return {"source": "upload", "socio": record}
    _seed_demo()
    _demo_socios.append(record)
    return {"source": "demo", "socio": record}


@router.get("/dashboard")
async def dashboard():
    if supabase_client.is_configured() and not _uploaded_socios:
        try:
            stats = await supabase_client.dashboard_stats()
            socios = await supabase_client.list_socios(50)
            return {"source": "supabase", "stats": stats, "socios": socios}
        except Exception:
            # Supabase caído o lento: no bloquear el dashboard
            pass
    _seed_demo()
    socios_list = _active_socios()
    source = "upload" if _uploaded_socios else "demo"
    by_level = {"bajo": 0, "medio": 0, "alto": 0}
    probs = []
    for s in socios_list:
        p = s.get("prediccion", {})
        lvl = p.get("nivel_riesgo", "bajo")
        by_level[lvl] = by_level.get(lvl, 0) + 1
        probs.append(float(p.get("probabilidad_mora", 0)))
    stats = {
        "total_socios": len(socios_list),
        "total_predicciones": len(socios_list),
        "por_nivel": by_level,
        "probabilidad_promedio": round(sum(probs) / len(probs), 4) if probs else 0,
    }
    return {"source": source, "stats": stats, "socios": socios_list}


@router.delete("/upload")
async def clear_upload():
    """Cancela la carga de Excel y vuelve a datos demo."""
    set_uploaded_socios([])
    _seed_demo()
    return {"ok": True, "mensaje": "Carga cancelada. Se restauraron datos de demostración."}
