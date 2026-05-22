import type { DashboardResponse, PredictResponse, Socio } from "./types";

/**
 * Producción (Vercel): define VITE_API_URL=https://TU-API.onrender.com/api
 * Desarrollo: por defecto /api (proxy en vite.config.ts → localhost:8000)
 */
const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") ||
  (import.meta.env.DEV ? "/api" : "http://localhost:8000/api");

function connectionHint(): string {
  if (API_URL.startsWith("/")) {
    return "Inicia el backend: cd backend && PYTHONPATH=. uvicorn app.main:app --reload --port 8000";
  }
  if (API_URL.includes("localhost")) {
    return "El frontend apunta a localhost pero quizá abriste la web en Vercel. En Vercel configura VITE_API_URL con la URL de Render.";
  }
  return `Revisa que la API responda en ${API_URL}/health y CORS_ORIGINS en el servidor.`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
  } catch (e) {
    const msg =
      e instanceof Error && e.message === "Failed to fetch"
        ? `No se pudo conectar con la API (${url}). ${connectionHint()}`
        : e instanceof Error
          ? e.message
          : "Error de red";
    throw new Error(msg);
  }
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
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300000);
  const form = new FormData();
  form.append("file", file);
  const url = `${API_URL}/socios/upload-excel`;
  try {
    const res = await fetch(url, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(parseError(err.detail) || `Error ${res.status}`);
    }
    return res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(
        "El análisis tardó demasiado. Prueba con menos filas o divide el archivo."
      );
    }
    if (e instanceof Error && e.message === "Failed to fetch") {
      throw new Error(
        `No se pudo conectar con la API (${url}). ${connectionHint()}`
      );
    }
    throw e;
  } finally {
    clearTimeout(timeout);
  }
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
