export function formatCost(cost: number | null | undefined): string {
  if (cost == null) return "—";
  return `$${cost.toFixed(2)}`;
}

export function formatTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString();
}

export function formatCount(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString();
}

export function truncate(s: string, max = 200): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
