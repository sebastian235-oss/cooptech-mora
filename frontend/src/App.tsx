import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  clearUpload,
  createSocioManual,
  fetchDashboard,
  exportCsvUrl,
  uploadExcel,
  type SocioManualPayload,
} from "./api";
import { formatProbPercent, probBarWidth } from "./format";
import { detectRiskSignals } from "./signals";
import type { DashboardResponse, NivelRiesgo, Socio } from "./types";
import "./App.css";

const RISK_COLORS: Record<NivelRiesgo, string> = {
  bajo: "#16a34a",
  medio: "#d97706",
  alto: "#dc2626",
};

const CHART_TOOLTIP = {
  contentStyle: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: "10px",
    boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
    fontSize: "13px",
  },
};

const EMPTY_MANUAL: SocioManualPayload = {
  cedula: "",
  nombre: "",
  ingresos_socio: undefined,
  egresos_socio: undefined,
  mora_actual: 0,
  n_creditos_unicos: 1,
  dias_desde_ultimo_pago_max: undefined,
  ratio_egresos_ingresos: undefined,
  saldo_vencido_actual_total: 0,
  capacidad_pago: undefined,
};

function getPrediccion(socio: Socio) {
  if (socio.prediccion) return socio.prediccion;
  const preds = socio.predicciones;
  if (preds?.length) return preds[0];
  return null;
}

function sourceLabel(source: string) {
  if (source === "supabase") return "Supabase conectado";
  if (source === "upload") return "Datos cargados";
  return "Sin datos";
}

function App() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [showManual, setShowManual] = useState(false);
  const [manual, setManual] = useState<SocioManualPayload>({ ...EMPTY_MANUAL });
  const [savingManual, setSavingManual] = useState(false);
  const [search, setSearch] = useState("");
  const [uploadMeta, setUploadMeta] = useState<{
    cobertura?: number;
    modoRanking?: string;
    columnasMapeadas?: string[];
  } | null>(null);

  const refresh = useCallback(() => {
    return fetchDashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const handleFile = async (file: File) => {
    setUploading(true);
    setUploadMsg(null);
    setError(null);
    try {
      const res = await uploadExcel(file);
      setUploadMeta({
        cobertura: res.cobertura_features,
        modoRanking: res.modo_ranking,
        columnasMapeadas: res.columnas_mapeadas,
      });
      const covTxt =
        res.cobertura_features != null
          ? ` · Cobertura ${(res.cobertura_features * 100).toFixed(0)}%`
          : "";
      const rankTxt =
        res.modo_ranking === "tabla_maestra_relativo"
          ? " · Ranking relativo (tabla maestra)"
          : "";
      setUploadMsg(
        `${res.mensaje} · Modelo: ${res.modo}${covTxt}${rankTxt}${res.probabilidad_promedio != null ? ` · Prom. ${(res.probabilidad_promedio * 100).toFixed(1)}%` : ""}`
      );
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al subir archivo");
    } finally {
      setUploading(false);
    }
  };

  const handleCancelUpload = async () => {
    setError(null);
    try {
      const res = await clearUpload();
      setUploadMsg(res.mensaje);
      setUploadMeta(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cancelar");
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manual.cedula.trim() || !manual.nombre.trim()) {
      setError("Cédula y nombre son obligatorios");
      return;
    }
    setSavingManual(true);
    setError(null);
    try {
      await createSocioManual(manual);
      setUploadMsg(`Socio ${manual.nombre} agregado y evaluado.`);
      setShowManual(false);
      setManual({ ...EMPTY_MANUAL });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSavingManual(false);
    }
  };

  const sociosFiltered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return data.socios;
    return data.socios.filter((s) => {
      const nombre = (s.nombre || "").toLowerCase();
      const cedula = (s.cedula || "").toLowerCase();
      return nombre.includes(q) || cedula.includes(q);
    });
  }, [data, search]);

  if (loading) return <div className="app loading">Cargando dashboard…</div>;
  if (error && !data) return <div className="app error">Error: {error}</div>;
  if (!data) return null;

  const { stats, socios, source } = data;
  const hasUpload = source === "upload";
  const largeDataset = socios.length > 5000;

  const pieData = Object.entries(stats.por_nivel).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    nivel: name as NivelRiesgo,
  }));

  const barSource = socios.length > 200 ? socios.slice(0, 200) : socios;
  const barData = barSource.map((s) => {
    const p = getPrediccion(s);
    return {
      nombre: s.nombre.split(" ")[0],
      probabilidad: p ? Math.round(p.probabilidad_mora * 100) : 0,
    };
  });

  return (
    <div className="app">
      <header>
        <span className="header-accent" aria-hidden />
        <div>
          <h1>CoopTech Tulcán — Riesgo de Mora</h1>
          <p>Perfilamiento transaccional preventivo · DevIAthon CoopTech</p>
        </div>
        <div className="header-actions">
          <div className="upload-zone">
            <label className={`upload-btn${uploading ? " disabled" : ""}`}>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                disabled={uploading}
                onChange={(ev) => {
                  const f = ev.target.files?.[0];
                  if (f) handleFile(f);
                  ev.target.value = "";
                }}
              />
              {uploading ? "Procesando…" : "Subir Excel"}
            </label>
            {hasUpload && (
              <>
                <a className="btn-secondary" href={exportCsvUrl()} download>
                  Exportar CSV
                </a>
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={handleCancelUpload}
                >
                  Cancelar carga
                </button>
              </>
            )}
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setShowManual(true)}
            >
              + Cliente manual
            </button>
            <span className="upload-hint">.xlsx, .xls o .csv</span>
          </div>
          <span className={`badge ${source}`}>{sourceLabel(source)}</span>
        </div>
      </header>

      {uploadMsg && <p className="upload-success">{uploadMsg}</p>}
      {uploadMeta?.modoRanking === "tabla_maestra_relativo" && (
        <p className="upload-hint coverage-hint">
          Tu archivo tiene pocas columnas del modelo ({uploadMeta.cobertura != null ? `${(uploadMeta.cobertura * 100).toFixed(0)}%` : "baja"} cobertura).
          Las probabilidades mostradas son un ranking relativo dentro del archivo para priorizar seguimiento.
          Para scoring ML completo, exporta el dataset de prevención con ~162 columnas.
        </p>
      )}
      {uploadMeta?.columnasMapeadas && uploadMeta.columnasMapeadas.length > 0 && (
        <p className="upload-hint">
          Columnas renombradas: {uploadMeta.columnasMapeadas.join(", ")}
        </p>
      )}
      {largeDataset && (
        <p className="upload-success">
          Analizados {socios.length.toLocaleString()} socios. La tabla puede tardar unos segundos.
        </p>
      )}
      {socios.length === 0 && (
        <p className="upload-hint empty-hint">
          Sube un Excel (formato entrenamiento) o agrega un cliente manual.
        </p>
      )}
      {error && data && <p className="upload-error">{error}</p>}

      {showManual && (
        <div className="modal-overlay" onClick={() => setShowManual(false)}>
          <form
            className="modal"
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleManualSubmit}
          >
            <h2>Agregar cliente manualmente</h2>
            <p className="modal-hint">
              Usa los mismos datos del Excel de entrenamiento para mejores predicciones.
            </p>
            <div className="form-grid">
              <label>
                Cédula / ID *
                <input
                  required
                  value={manual.cedula}
                  onChange={(e) =>
                    setManual({ ...manual, cedula: e.target.value })
                  }
                />
              </label>
              <label>
                Nombre *
                <input
                  required
                  value={manual.nombre}
                  onChange={(e) =>
                    setManual({ ...manual, nombre: e.target.value })
                  }
                />
              </label>
              <label>
                Ingresos socio
                <input
                  type="number"
                  step="0.01"
                  value={manual.ingresos_socio ?? ""}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      ingresos_socio: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    })
                  }
                />
              </label>
              <label>
                Egresos socio
                <input
                  type="number"
                  step="0.01"
                  value={manual.egresos_socio ?? ""}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      egresos_socio: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    })
                  }
                />
              </label>
              <label>
                Mora actual
                <input
                  type="number"
                  step="1"
                  value={manual.mora_actual ?? 0}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      mora_actual: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Días desde último pago
                <input
                  type="number"
                  value={manual.dias_desde_ultimo_pago_max ?? ""}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      dias_desde_ultimo_pago_max: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    })
                  }
                />
              </label>
              <label>
                Ratio egresos / ingresos
                <input
                  type="number"
                  step="0.01"
                  max={2}
                  value={manual.ratio_egresos_ingresos ?? ""}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      ratio_egresos_ingresos: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    })
                  }
                />
              </label>
              <label>
                Nº créditos
                <input
                  type="number"
                  value={manual.n_creditos_unicos ?? 1}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      n_creditos_unicos: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Saldo vencido
                <input
                  type="number"
                  step="0.01"
                  value={manual.saldo_vencido_actual_total ?? 0}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      saldo_vencido_actual_total: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Capacidad de pago
                <input
                  type="number"
                  step="0.01"
                  value={manual.capacidad_pago ?? ""}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      capacidad_pago: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    })
                  }
                />
              </label>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setShowManual(false)}
              >
                Cerrar
              </button>
              <button type="submit" className="upload-btn" disabled={savingManual}>
                {savingManual ? "Calculando…" : "Guardar y evaluar"}
              </button>
            </div>
          </form>
        </div>
      )}

      <section className="cards">
        <div className="card">
          <h3>Socios monitoreados</h3>
          <div className="value">{stats.total_socios}</div>
        </div>
        <div className="card">
          <h3>Probabilidad promedio</h3>
          <div className="value">
            {formatProbPercent(stats.probabilidad_promedio)}
          </div>
        </div>
        <div className="card">
          <h3>Riesgo alto</h3>
          <div className="value risk-alto">{stats.por_nivel.alto ?? 0}</div>
        </div>
        <div className="card">
          <h3>Riesgo medio</h3>
          <div className="value risk-medio">{stats.por_nivel.medio ?? 0}</div>
        </div>
      </section>

      <section className="charts">
        <div className="chart-box">
          <h2>Distribución por nivel de riesgo</h2>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={78}
                paddingAngle={3}
                label={({ name, percent }) =>
                  `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                }
                labelLine={{ stroke: "#94a3b8", strokeWidth: 1 }}
              >
                {pieData.map((entry) => (
                  <Cell key={entry.nivel} fill={RISK_COLORS[entry.nivel]} />
                ))}
              </Pie>
              <Tooltip {...CHART_TOOLTIP} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-box">
          <h2>Probabilidad de mora por socio (%)</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={barData} barCategoryGap="28%">
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e2e8f0"
                vertical={false}
              />
              <XAxis
                dataKey="nombre"
                tick={{ fill: "#64748b", fontSize: 12, fontWeight: 500 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                domain={[0, 100]}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip {...CHART_TOOLTIP} />
              <Bar
                dataKey="probabilidad"
                fill="#0d9488"
                radius={[6, 6, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="table-wrap">
        <div className="table-toolbar">
          <h2>Socios y señales de riesgo</h2>
          <div className="search-box">
            <input
              type="search"
              placeholder="Buscar por nombre o cédula…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Buscar socio"
            />
            {search && (
              <span className="search-count">
                {sociosFiltered.length} de {socios.length}
              </span>
            )}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Socio</th>
                <th>Prob. mora</th>
                <th>Nivel</th>
                <th>Señales detectadas</th>
              </tr>
            </thead>
            <tbody>
              {sociosFiltered.length === 0 ? (
                <tr>
                  <td colSpan={4} className="no-results">
                    No hay socios que coincidan con la búsqueda.
                  </td>
                </tr>
              ) : (
                sociosFiltered.map((s) => {
                  const p = getPrediccion(s);
                  const prob = p?.probabilidad_mora ?? 0;
                  const coverage = p?.feature_coverage ?? 1;
                  const nivel = p?.nivel_riesgo ?? "bajo";
                  const lowCoverage = coverage < 0.35;
                  const feats =
                    s.features ||
                    p?.features_usadas ||
                    (p as { features?: Record<string, number> })?.features ||
                    {};
                  const signalTags =
                    (p?.senales?.length ? p.senales : null) ??
                    detectRiskSignals(feats);

                  return (
                    <tr key={s.id}>
                      <td>
                        <span className="socio-name">{s.nombre}</span>
                        {s.cedula && (
                          <span className="socio-cedula">{s.cedula}</span>
                        )}
                      </td>
                      <td>
                        <span className="prob-value" title={lowCoverage ? `Cobertura de datos: ${(coverage * 100).toFixed(0)}%` : undefined}>
                          {formatProbPercent(prob)}
                        </span>
                        {lowCoverage && (
                          <span className="coverage-warn">Datos incompletos</span>
                        )}
                        <div className="progress-bar">
                          <span
                            style={{
                              width: `${probBarWidth(prob)}%`,
                              background: RISK_COLORS[nivel],
                            }}
                          />
                        </div>
                      </td>
                      <td>
                        <span className={`risk-pill ${nivel}`}>{nivel}</span>
                      </td>
                      <td>
                        {signalTags.length > 0 ? (
                          <div className="signals-panel">
                            <div className="signal-tags">
                              {signalTags.map((tag) => (
                                <span key={tag} className="signal-tag">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <span className="signals-stable">Sin alertas</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default App;
