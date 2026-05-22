/** Genera etiquetas de señales de riesgo a partir de features del socio. */

const PCT = (v: number) => `${Math.round(Math.abs(v) * 100)}%`;

function pick(
  feats: Record<string, number>,
  keys: string[]
): number | undefined {
  for (const k of keys) {
    const v = feats[k];
    if (v != null && !Number.isNaN(v)) return v;
  }
  return undefined;
}

export function detectRiskSignals(
  feats: Record<string, number>,
  probabilidad: number
): string[] {
  const signals: string[] = [];

  const variacionSaldo = pick(feats, [
    "variacion_saldo_30d",
    "variacion_saldo",
    "var_saldo_30d",
    "pct_saldo_30d",
  ]);
  if (variacionSaldo != null && variacionSaldo < -0.05) {
    signals.push(`Saldo ↓${PCT(variacionSaldo)}`);
  }

  const variacionMov = pick(feats, [
    "variacion_movimientos_30d",
    "variacion_movimientos",
    "pct_var_movimientos",
  ]);
  if (variacionMov != null && variacionMov < -0.05) {
    signals.push(`Movimientos ↓${PCT(variacionMov)}`);
  } else {
    const mov30 = pick(feats, ["num_movimientos_30d", "n_movimientos_30d"]);
    if (mov30 != null && mov30 < 5) {
      signals.push("Movimientos ↓");
    } else {
      const ops = pick(feats, ["xt_n_operaciones", "n_operaciones_credito"]);
      if (ops != null && ops < 3) signals.push("Poca actividad");
    }
  }

  const diasAtraso = pick(feats, [
    "dias_desde_ultimo_pago_max",
    "dias_desde_ultimo_pago_prom",
    "dias_atraso_promedio",
    "dias_atraso",
    "max_dias_mora_actual",
    "hist_cuotas_atrasadas_max",
  ]);
  if (diasAtraso != null && diasAtraso > 0) {
    if (diasAtraso <= 15) signals.push("Retrasos menores");
    else if (diasAtraso <= 45)
      signals.push(`Retrasos ${Math.round(diasAtraso)} días`);
    else signals.push(`Atraso ${Math.round(diasAtraso)} días`);
  }

  const ratioPago = pick(feats, ["ratio_pago_cuota"]);
  if (ratioPago != null && ratioPago < 0.85) {
    signals.push(`Pagos ↓${PCT(1 - ratioPago)}`);
  }

  const ratioEgr = pick(feats, ["ratio_egresos_ingresos"]);
  if (ratioEgr != null && ratioEgr > 0.8) {
    signals.push("Egresos altos");
  }

  const saldoVenc = pick(feats, [
    "saldo_vencido_actual_total",
    "saldo_vencido",
    "hist_cuotas_atrasadas_total",
  ]);
  if (saldoVenc != null && saldoVenc > 0) {
    signals.push("Saldo vencido");
  }

  const capacidad = pick(feats, ["capacidad_pago"]);
  if (capacidad != null && capacidad < 0) {
    signals.push("Capacidad pago negativa");
  }

  const cuotasAtraso = pick(feats, ["hist_cuotas_atrasadas_max"]);
  if (cuotasAtraso != null && cuotasAtraso > 0 && !signals.some((s) => s.includes("Retraso"))) {
    signals.push("Cuotas atrasadas");
  }

  if (probabilidad >= 0.5) {
    signals.push(`Riesgo muy alto ${(probabilidad * 100).toFixed(1)}%`);
  } else if (probabilidad >= 0.2) {
    signals.push(`Riesgo elevado ${(probabilidad * 100).toFixed(1)}%`);
  } else if (probabilidad >= 0.05) {
    signals.push(`Alerta preventiva ${(probabilidad * 100).toFixed(1)}%`);
  }

  return [...new Set(signals)].slice(0, 6);
}
