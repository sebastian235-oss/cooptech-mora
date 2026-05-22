from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client | None:
    global _client
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


def is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


async def list_socios(limit: int = 100) -> list[dict[str, Any]]:
    client = get_supabase()
    if not client:
        return []
    res = (
        client.table("socios")
        .select("*, predicciones(*)")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


async def upsert_prediccion(payload: dict[str, Any]) -> dict[str, Any] | None:
    client = get_supabase()
    if not client:
        return None
    res = client.table("predicciones").upsert(payload).execute()
    return (res.data or [None])[0]


async def dashboard_stats() -> dict[str, Any]:
    client = get_supabase()
    if not client:
        return {}
    socios = client.table("socios").select("id", count="exact").execute()
    preds = client.table("predicciones").select("nivel_riesgo, probabilidad_mora").execute()
    rows = preds.data or []
    by_level: dict[str, int] = {"bajo": 0, "medio": 0, "alto": 0}
    for r in rows:
        lvl = r.get("nivel_riesgo", "bajo")
        by_level[lvl] = by_level.get(lvl, 0) + 1
    avg_prob = (
        sum(float(r.get("probabilidad_mora", 0)) for r in rows) / len(rows)
        if rows
        else 0.0
    )
    return {
        "total_socios": socios.count or 0,
        "total_predicciones": len(rows),
        "por_nivel": by_level,
        "probabilidad_promedio": round(avg_prob, 4),
    }
