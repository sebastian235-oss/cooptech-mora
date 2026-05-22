export type NivelRiesgo = "bajo" | "medio" | "alto";

export interface Prediccion {
  probabilidad_mora: number;
  nivel_riesgo: NivelRiesgo;
  features_usadas?: Record<string, number>;
  accion?: string;
  nivel_label?: string;
  modelo?: string;
  senales?: string[];
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
}
