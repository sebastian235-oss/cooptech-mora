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
    modelo: str | None = None


class SocioCreate(BaseModel):
    cedula: str
    nombre: str
    agencia: str | None = None
    telefono: str | None = None
    # Campos alineados al dataset de prevención / modelo producción
    ingresos_socio: float | None = None
    egresos_socio: float | None = None
    mora_actual: float | None = 0
    n_creditos_unicos: float | None = None
    dias_desde_ultimo_pago_max: float | None = None
    ratio_egresos_ingresos: float | None = None
    saldo_vencido_actual_total: float | None = None
    capacidad_pago: float | None = None
    features: dict[str, float] = Field(default_factory=dict)

    def to_feature_dict(self) -> dict[str, float]:
        data = dict(self.features)
        for key in (
            "ingresos_socio",
            "egresos_socio",
            "mora_actual",
            "n_creditos_unicos",
            "dias_desde_ultimo_pago_max",
            "ratio_egresos_ingresos",
            "saldo_vencido_actual_total",
            "capacidad_pago",
        ):
            val = getattr(self, key, None)
            if val is not None:
                data[key] = float(val)
        data["cedula"] = self.cedula
        data["cliente_id"] = self.cedula
        return data
