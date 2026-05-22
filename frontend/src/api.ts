import type { DashboardResponse, PredictResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
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

export type { PredictResponse };

export interface UploadExcelResponse {
  ok: boolean;
  archivo: string;
  modo: string;
  total_procesados: number;
  mensaje: string;
  columnas_detectadas?: string[];
  columnas_mapeadas?: Record<string, string>;
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
    const detail = err.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join(", ")
          : res.statusText;
    throw new Error(msg || `Error ${res.status}`);
  }
  return res.json();
}
