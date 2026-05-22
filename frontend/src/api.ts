import type { DashboardResponse, PredictResponse, Socio } from "./types";

/**
 * Producción (Vercel): define VITE_API_URL=https://TU-API.onrender.com/api
 * Desarrollo: por defecto /api (proxy en vite.config.ts → localhost:8000)
 */
const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") ||
  (import.meta.env.DEV ? "/api" : "http://localhost:8000/api");

const DEFAULT_TIMEOUT_MS = 120000;

async function fetchWithTimeout(
  url: string,
  options?: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(
        `La API tardó más de ${timeoutMs / 1000}s (Render puede estar despertando). Espera e intenta de nuevo.`
      );
    }
    throw e;
  } finally {
    clearTimeout(id);
  }
}

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
    res = await fetchWithTimeout(url, {
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
    const res = await fetchWithTimeout(url, {
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
export interface UploadCootechResponse {
  ok: boolean;
  modo: string;
  modelo?: string;
  archivos: number;
  total_procesados: number;
  mensaje: string;
  probabilidad_promedio?: number;
  stats_cootech?: import("./types").CootechStats;
}

export type CootechUploadProgress = (
  current: number,
  total: number,
  filename: string
) => void;

/** Sube los 12 archivos uno por uno (evita límite de 80 MB del paquete único). */
export async function uploadCootech(
  files: File[],
  onProgress?: CootechUploadProgress
): Promise<UploadCootechResponse> {
  const total = files.length;
  const totalBytes = files.reduce((s, f) => s + f.size, 0);
  const maxBundleMb = 70;
  if (totalBytes <= maxBundleMb * 1024 * 1024 && total <= 3) {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await fetchWithTimeout(
      `${API_URL}/socios/upload-cootech`,
      { method: "POST", body: form },
      300000
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(parseError(err.detail) || `Error ${res.status}`);
    }
    return res.json();
  }

  const sess = await request<{ session_id: string }>(
    "/socios/upload-cootech/session",
    { method: "POST" }
  );
  const sessionId = sess.session_id;

  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    onProgress?.(i + 1, total, f.name);
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("file", f);
    const res = await fetchWithTimeout(
      `${API_URL}/socios/upload-cootech/file`,
      { method: "POST", body: form },
      300000
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(
        parseError(err.detail) || `Error subiendo ${f.name} (${res.status})`
      );
    }
  }

  onProgress?.(total, total, "Analizando…");
  const procForm = new FormData();
  procForm.append("session_id", sessionId);
  const procRes = await fetchWithTimeout(
    `${API_URL}/socios/upload-cootech/process`,
    { method: "POST", body: procForm },
    300000
  );
  if (!procRes.ok) {
    const err = await procRes.json().catch(() => ({ detail: procRes.statusText }));
    throw new Error(parseError(err.detail) || `Error ${procRes.status}`);
  }
  return procRes.json();
}
