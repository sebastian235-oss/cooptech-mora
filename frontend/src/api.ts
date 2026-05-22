import type { DashboardResponse, PredictResponse, Socio } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(parseError(err.detail) || `Error ${res.status}`);
  }
  return res.json();
}

function parseError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg).join(", ");
  }
  return "";
}

export function fetchDashboard(): Promise<DashboardResponse> {
  return request("/socios/dashboard");
}

export function predictSocio(
  socio_id: string,
  features: Record<string, number>
): Promise<PredictResponse> {
  return request("/predict", {
    method: "POST",
    body: JSON.stringify({ socio_id, features }),
  });
}

export interface UploadExcelResponse {
  ok: boolean;
  archivo: string;
  modo: string;
  total_procesados: number;
  mensaje: string;
  modelo?: string;
  probabilidad_promedio?: number;
}

export async function uploadExcel(file: File): Promise<UploadExcelResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/socios/upload-excel`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(parseError(err.detail) || `Error ${res.status}`);
  }
  return res.json();
}

export async function clearUpload(): Promise<{ ok: boolean; mensaje: string }> {
  return request("/socios/upload", { method: "DELETE" });
}

export interface SocioManualPayload {
  cedula: string;
  nombre: string;
  agencia?: string;
  ingresos_socio?: number;
  egresos_socio?: number;
  mora_actual?: number;
  n_creditos_unicos?: number;
  dias_desde_ultimo_pago_max?: number;
  ratio_egresos_ingresos?: number;
  saldo_vencido_actual_total?: number;
  capacidad_pago?: number;
}

export async function createSocioManual(
  payload: SocioManualPayload
): Promise<{ socio: Socio; source: string }> {
  return request("/socios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type { PredictResponse };
