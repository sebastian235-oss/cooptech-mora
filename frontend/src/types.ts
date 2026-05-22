export type NivelRiesgo = "bajo" | "medio" | "alto";

export interface Prediccion {
  probabilidad_mora: number;
  nivel_riesgo: NivelRiesgo;
  features_usadas?: Record<string, number>;
  accion?: string;
  nivel_label?: string;
  modelo?: string;
  senales?: string[];
  al_dia?: boolean;
  credito_vigente?: boolean;
}

export interface Socio {
  id: string;
  cedula?: string;
  nombre: string;
  agencia?: string;
  features?: Record<string, number>;
  prediccion?: Prediccion;
  predicciones?: Prediccion[];
}

export interface DashboardStats {
  total_socios: number;
  total_predicciones: number;
  por_nivel: Record<NivelRiesgo, number>;
  probabilidad_promedio: number;
  cootech?: CootechStats;
}

export interface DashboardResponse {
  source: string;
  stats: DashboardStats;
  socios: Socio[];
}

export interface PredictResponse {
  socio_id?: string;
  probabilidad_mora: number;
  nivel_riesgo: NivelRiesgo;
  features_usadas: Record<string, number>;
  guardado_en_supabase: boolean;
  modelo?: string;
  senales?: string[];
  al_dia?: boolean;
  credito_vigente?: boolean;
}


export interface CootechStats {
  total_clientes?: number;
  clientes_vigentes?: number;
  clientes_al_dia?: number;
  monitoreados_preventivos?: number;
  tiempo_ms?: number;
  por_nivel_preventivo?: Record<NivelRiesgo, number>;
}
