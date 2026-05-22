/** Genera etiquetas de señales de riesgo a partir de features del socio. */

const PCT = (v: number) => `${Math.round(Math.abs(v) * 100)}%`;

export function detectRiskSignals(
  feats: Record<string, number>,
  probabilidad: number
): string[] {
  const signals: string[] = [];

  const variacionSaldo =
    feats.variacion_saldo_30d ??
    feats.variacion_saldo ??
    feats.var_saldo_30d;
  if (variacionSaldo != null && variacionSaldo < -0.1) {
    signals.push(`Saldo ↓${PCT(variacionSaldo)}`);
  }

  const variacionMov =
    feats.variacion_movimientos_30d ??
    feats.variacion_movimientos ??
    feats.pct_var_movimientos;
  if (variacionMov != null && variacionMov < -0.1) {
    signals.push(`Movimientos ↓${PCT(variacionMov)}`);
  } else if (
    feats.num_movimientos_30d != null &&
    feats.num_movimientos_30d < 4
  ) {
    signals.push("Movimientos ↓");
  } else if (
    feats.xt_n_operaciones != null &&
    feats.xt_n_operaciones < 3
  ) {
    signals.push("Poca actividad");
  }

  const diasAtraso =
    feats.dias_desde_ultimo_pago_max ??
    feats.dias_atraso_promedio ??
    feats.max_dias_mora_actual;
  if (diasAtraso != null && diasAtraso > 0) {
    if (diasAtraso <= 15) signals.push("Retrasos menores");
    else if (diasAtraso <= 45) signals.push(`Retrasos ${Math.round(diasAtraso)} días`);
    else signals.push(`Atraso ${Math.round(diasAtraso)} días`);
  }

  if (feats.ratio_pago_cuota != null && feats.ratio_pago_cuota < 0.75) {
    signals.push(`Pagos ↓${PCT(1 - feats.ratio_pago_cuota)}`);
  }

  if (feats.ratio_egresos_ingresos != null && feats.ratio_egresos_ingresos > 0.85) {
    signals.push("Egresos altos");
  }

  if (
    feats.saldo_vencido_actual_total != null &&
    feats.saldo_vencido_actual_total > 0
  ) {
    signals.push("Saldo vencido");
  }

  if (
    feats.capacidad_pago != null &&
    feats.capacidad_pago < 0 &&
    probabilidad >= 0.2
  ) {
    signals.push("Capacidad pago negativa");
  }

  return signals.slice(0, 5);
}
