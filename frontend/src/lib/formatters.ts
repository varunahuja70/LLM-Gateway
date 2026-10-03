/**
 * Format integer micro-USD ($1 = 1,000,000 micro-USD) as currency string.
 *
 * Rules:
 * - null/undefined: "unpriced"
 * - >= $1.00 (1,000,000 micro-USD): "$X.XX" (2 decimal places)
 * - < $1.00: up to 6 decimal places without trailing zeroes, e.g. "$0.0025"
 * - 0: "$0.00"
 */
export function formatMicroUsd(microUsd: number | null | undefined): string {
  if (microUsd === null || microUsd === undefined) {
    return "unpriced";
  }

  if (microUsd === 0) {
    return "$0.00";
  }

  const usd = microUsd / 1_000_000;

  if (usd >= 1.0) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(usd);
  }

  // Under $1.00: show up to 6 significant decimals, min 4 decimals
  const formatted = usd.toFixed(6).replace(/0+$/, "");
  return `$${formatted.endsWith(".") ? formatted.slice(0, -1) : formatted}`;
}

/**
 * Format latency in milliseconds:
 * - < 1000 ms: "X ms"
 * - >= 1000 ms: "X.XX s"
 */
export function formatLatency(latencyMs: number | null | undefined): string {
  if (latencyMs === null || latencyMs === undefined) {
    return "—";
  }

  if (latencyMs < 1000) {
    return `${Math.round(latencyMs)} ms`;
  }

  return `${(latencyMs / 1000).toFixed(2)} s`;
}

/**
 * Format token count with thousands separators (e.g. 12,450).
 */
export function formatTokens(tokens: number | null | undefined): string {
  if (tokens === null || tokens === undefined) {
    return "0";
  }
  return new Intl.NumberFormat("en-US").format(tokens);
}

/**
 * Format percentage (e.g. 0.052 -> "5.2%").
 */
export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return "0.0%";
  }
  return `${(rate * 100).toFixed(1)}%`;
}
