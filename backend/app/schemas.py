from typing import Any

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    socio_id: str | None = None
    features: dict[str, float] = Field(default_factory=dict)


class PredictBatchRequest(BaseModel):
    records: list[dict[str, Any]]


class PredictResponse(BaseModel):
    socio_id: str | None = None
    probabilidad_mora: float
    nivel_riesgo: str
    features_usadas: dict[str, float] = Field(default_factory=dict)
    guardado_en_supabase: bool = False


class SocioCreate(BaseModel):
    cedula: str
    nombre: str
    agencia: str | None = None
    telefono: str | None = None
    features: dict[str, float] = Field(default_factory=dict)
