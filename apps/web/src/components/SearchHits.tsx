import Link from "next/link";

import { cn } from "@/lib/cn";
import type { SearchHit } from "@/lib/types";

export function SearchHitItem({ hit }: { hit: SearchHit }) {
  const href = buildHref(hit);
  return (
    <Link
      href={href}
      className="block rounded-xl border border-border/70 bg-card p-3 hover:border-foreground/30"
    >
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] font-medium font-medium",
              hit.kind === "trajectory"
                ? "bg-muted text-muted-foreground"
                : "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))]",
            )}
          >
            {hit.kind}
          </span>
          <span className="font-mono text-xs">
            {hit.run_id} · {hit.trajectory_id}
            {hit.step_index != null && (
              <span className="text-muted-foreground"> · step {hit.step_index + 1}</span>
            )}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground">{hit.field}</span>
      </div>
      <p
        className="mt-2 text-sm leading-relaxed text-muted-foreground"
        dangerouslySetInnerHTML={{ __html: renderSnippet(hit.snippet) }}
      />
    </Link>
  );
}

export function buildHref(hit: SearchHit): string {
  const base = `/runs/${encodeURIComponent(hit.run_id)}/${encodeURIComponent(hit.trajectory_id)}`;
  if (hit.step_index != null) return `${base}?step=${hit.step_index}`;
  return base;
}

/** Convert FTS5 `[match]` brackets into highlighted spans. Anything else is escaped. */
function renderSnippet(s: string): string {
  const escaped = s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(
    /\[([^\]]+)\]/g,
    '<mark class="rounded bg-[hsl(var(--warning))]/30 px-0.5 text-foreground">$1</mark>',
  );
}
