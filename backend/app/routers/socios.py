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
    if _demo_socios:
        return
    samples = [
        {
            "id": str(uuid4()),
            "cedula": "1723456789",
            "nombre": "María González",
            "agencia": "Tulcán Centro",
            "features": {
                "dias_atraso_promedio": 2,
                "ratio_pago_cuota": 0.95,
                "saldo_promedio_cuenta": 1200,
                "variacion_saldo_30d": -0.15,
                "num_movimientos_30d": 8,
            },
        },
        {
            "id": str(uuid4()),
            "cedula": "1712345678",
            "nombre": "Carlos Pérez",
            "agencia": "Tulcán Norte",
            "features": {
                "dias_atraso_promedio": 12,
                "ratio_pago_cuota": 0.55,
                "saldo_promedio_cuenta": 180,
                "variacion_saldo_30d": -0.45,
                "num_movimientos_30d": 2,
            },
        },
        {
            "id": str(uuid4()),
            "cedula": "1709876543",
            "nombre": "Ana Rivadeneira",
            "agencia": "Tulcán Sur",
            "features": {
                "dias_atraso_promedio": 0,
                "ratio_pago_cuota": 1.0,
                "saldo_promedio_cuenta": 3500,
                "variacion_saldo_30d": 0.05,
                "num_movimientos_30d": 15,
            },
        },
    ]
    for s in samples:
        try:
            pred = predict_from_features(s["features"])
            s["prediccion"] = pred
        except Exception:
            s["prediccion"] = {"probabilidad_mora": 0, "nivel_riesgo": "bajo"}
        _demo_socios.append(s)


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
        stats = await supabase_client.dashboard_stats()
        socios = await supabase_client.list_socios(50)
        return {"source": "supabase", "stats": stats, "socios": socios}
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
