import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDashboard } from "./api";
import type { DashboardResponse, NivelRiesgo, Socio } from "./types";
import "./App.css";

const RISK_COLORS: Record<NivelRiesgo, string> = {
  bajo: "#22c55e",
  medio: "#f59e0b",
  alto: "#ef4444",
};

function getPrediccion(socio: Socio) {
  if (socio.prediccion) return socio.prediccion;
  const preds = socio.predicciones;
  if (preds?.length) return preds[0];
  return null;
}

function App() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="app loading">Cargando dashboard…</div>;
  if (error) return <div className="app error">Error: {error}</div>;
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
        <div>
          <h1>CoopTech Tulcán — Riesgo de Mora</h1>
          <p>Perfilamiento transaccional preventivo · DevIAthon CoopTech</p>
        </div>
        <span className={`badge ${source}`}>
          {source === "supabase" ? "Supabase conectado" : "Modo demo"}
        </span>
      </header>

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
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {pieData.map((entry) => (
                  <Cell key={entry.nivel} fill={RISK_COLORS[entry.nivel]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-box">
          <h2>Probabilidad de mora por socio (%)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData}>
              <XAxis dataKey="nombre" tick={{ fill: "#8b9cb3", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8b9cb3" }} domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="probabilidad" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="table-wrap">
        <h2>Socios y señales de riesgo</h2>
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
                    <strong>{s.nombre}</strong>
                    <br />
                    <small style={{ color: "var(--muted)" }}>{s.cedula}</small>
                  </td>
                  <td>{s.agencia || "—"}</td>
                  <td>
                    {(prob * 100).toFixed(1)}%
                    <div className="progress-bar">
                      <span
                        style={{
                          width: `${prob * 100}%`,
                          background: RISK_COLORS[nivel],
                        }}
                      />
                    </div>
                  </td>
                  <td className={`risk-${nivel}`}>{nivel}</td>
                  <td>{signals.length ? signals.join(" · ") : "Estable"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default App;
