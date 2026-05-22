import { useCallback, useEffect, useState } from "react";
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
import { fetchDashboard, uploadExcel } from "./api";
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

function getPrediccion(socio: Socio) {
  if (socio.prediccion) return socio.prediccion;
  const preds = socio.predicciones;
  if (preds?.length) return preds[0];
  return null;
}

function sourceLabel(source: string) {
  if (source === "supabase") return "Supabase conectado";
  if (source === "upload") return "Datos cargados";
  return "Modo demo";
}

function App() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

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
      setUploadMsg(res.mensaje);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al subir archivo");
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <div className="app loading">Cargando dashboard…</div>;
  if (error && !data) return <div className="app error">Error: {error}</div>;
  if (!data) return null;

  const { stats, socios, source } = data;
  const pieData = Object.entries(stats.por_nivel).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    nivel: name as NivelRiesgo,
  }));

  const barData = socios.map((s) => {
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
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                  e.target.value = "";
                }}
              />
              {uploading ? "Procesando…" : "Subir Excel"}
            </label>
            <span className="upload-hint">.xlsx, .xls o .csv</span>
          </div>
          <span className={`badge ${source}`}>{sourceLabel(source)}</span>
        </div>
      </header>

      {uploadMsg && <p className="upload-success">{uploadMsg}</p>}
      {error && <p className="upload-error">{error}</p>}

      <section className="cards">
        <div className="card">
          <h3>Socios monitoreados</h3>
          <div className="value">{stats.total_socios}</div>
        </div>
        <div className="card">
          <h3>Probabilidad promedio</h3>
          <div className="value">
            {(stats.probabilidad_promedio * 100).toFixed(1)}%
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
        <h2>Socios y señales de riesgo</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Socio</th>
                <th>Agencia</th>
                <th>Prob. mora</th>
                <th>Nivel</th>
                <th>Señales</th>
              </tr>
            </thead>
            <tbody>
              {socios.map((s) => {
                const p = getPrediccion(s);
                const prob = p?.probabilidad_mora ?? 0;
                const nivel = p?.nivel_riesgo ?? "bajo";
                const feats = s.features || p?.features_usadas || {};
                const signals = [
                  feats.dias_atraso_promedio > 5 && "Atrasos",
                  feats.variacion_saldo_30d < -0.2 && "Saldo ↓",
                  feats.ratio_pago_cuota < 0.7 && "Pagos bajos",
                  feats.num_movimientos_30d < 4 && "Poca actividad",
                ].filter(Boolean);

                return (
                  <tr key={s.id}>
                    <td>
                      <span className="socio-name">{s.nombre}</span>
                      {s.cedula && (
                        <span className="socio-cedula">{s.cedula}</span>
                      )}
                    </td>
                    <td>{s.agencia || "—"}</td>
                    <td>
                      <span className="prob-value">
                        {(prob * 100).toFixed(1)}%
                      </span>
                      <div className="progress-bar">
                        <span
                          style={{
                            width: `${prob * 100}%`,
                            background: RISK_COLORS[nivel],
                          }}
                        />
                      </div>
                    </td>
                    <td>
                      <span className={`risk-pill ${nivel}`}>{nivel}</span>
                    </td>
                    <td>
                      <span
                        className={
                          signals.length ? "signals" : "signals signals-stable"
                        }
                      >
                        {signals.length ? signals.join(" · ") : "Estable"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default App;
