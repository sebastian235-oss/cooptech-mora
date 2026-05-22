"""Sesiones temporales para subir el paquete CoopTech archivo por archivo."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

# session_id -> {filename: bytes}
_STORE: dict[str, dict[str, bytes]] = {}
_TTL_SEC = 3600
_MAX_FILES = 24
_MAX_FILE_BYTES = 200 * 1024 * 1024  # 200 MB por archivo


def _gc() -> None:
    now = time.time()
    stale = [sid for sid, files in _STORE.items() if not files]
    for sid in stale:
        _STORE.pop(sid, None)
    if len(_STORE) > 50:
        oldest = list(_STORE.keys())[:10]
        for sid in oldest:
            _STORE.pop(sid, None)


def new_session() -> str:
    _gc()
    sid = str(uuid4())
    _STORE[sid] = {}
    return sid


def add_file(session_id: str, filename: str, content: bytes) -> dict[str, Any]:
    if session_id not in _STORE:
        raise ValueError("Sesión expirada o inválida. Vuelve a iniciar la carga.")
    if len(content) > _MAX_FILE_BYTES:
        mb = round(len(content) / (1024 * 1024), 1)
        raise ValueError(f"Archivo {filename} demasiado grande ({mb} MB). Máx. 200 MB por archivo.")
    files = _STORE[session_id]
    if filename not in files and len(files) >= _MAX_FILES:
        raise ValueError(f"Máximo {_MAX_FILES} archivos por sesión.")
    files[filename] = content
    return {
        "session_id": session_id,
        "archivo": filename,
        "bytes": len(content),
        "archivos_en_sesion": len(files),
        "nombres": sorted(files.keys()),
    }


def get_bundle(session_id: str) -> list[tuple[str, bytes]]:
    if session_id not in _STORE:
        raise ValueError("Sesión expirada. Vuelve a subir los archivos.")
    files = _STORE[session_id]
    if not files:
        raise ValueError("No hay archivos en la sesión.")
    return [(name, data) for name, data in files.items()]


def clear_session(session_id: str) -> None:
    _STORE.pop(session_id, None)


def session_info(session_id: str) -> dict[str, Any]:
    files = _STORE.get(session_id, {})
    total = sum(len(b) for b in files.values())
    return {
        "session_id": session_id,
        "archivos": sorted(files.keys()),
        "cantidad": len(files),
        "total_bytes": total,
        "total_mb": round(total / (1024 * 1024), 2),
    }
