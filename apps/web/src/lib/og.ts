const SITE_URL = process.env.SITE_URL ?? "http://localhost:3000";

export function ogImage(opts: {
  title: string;
  subtitle?: string;
  kind?: "trajectory" | "run" | "showcase" | "integration" | "analytics" | "compare";
}): string {
  const params = new URLSearchParams({ title: opts.title });
  if (opts.subtitle) params.set("subtitle", opts.subtitle);
  if (opts.kind) params.set("kind", opts.kind);
  return `${SITE_URL}/og?${params.toString()}`;
}
