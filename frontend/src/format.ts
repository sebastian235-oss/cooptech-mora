export function formatProbPercent(prob: number): string {
  if (!Number.isFinite(prob) || prob <= 0) return "0%";
  const pct = prob * 100;
  if (pct < 0.01) return "<0.01%";
  if (pct < 0.1) return `${pct.toFixed(3)}%`;
  if (pct < 1) return `${pct.toFixed(2)}%`;
  return `${pct.toFixed(1)}%`;
}

export function probBarWidth(prob: number): number {
  if (prob <= 0) return 0;
  const pct = prob * 100;
  return Math.min(Math.max(pct, prob > 0 ? 2 : 0), 100);
}
