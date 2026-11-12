import Link from "next/link";

import { cn } from "@/lib/cn";
import { formatCost, formatCount } from "@/lib/format";
import type { TopTrajectory } from "@/lib/types";

export function TopList({
  title,
  subtitle,
  runId,
  items,
  metric,
}: {
  title: string;
  subtitle?: string;
  runId: string;
  items: TopTrajectory[];
  metric: "cost" | "steps";
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-border/70 bg-card p-4">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-2 text-xs text-muted-foreground">No data.</p>
      </div>
    );
  }
  return (
    <div className="rounded-2xl border border-border/70 bg-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
      <ol className="mt-3 flex flex-col gap-2">
        {items.map((t, i) => {
          const value = metric === "cost" ? formatCost(t.instance_cost) : formatCount(t.step_count);
          return (
            <li
              key={t.id}
              className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0"
            >
              <span className="text-xs font-mono text-muted-foreground tabular-nums">
                {i + 1}
              </span>
              <Link
                href={`/runs/${runId}/${t.id}`}
                className="truncate font-mono text-xs hover:text-foreground"
                title={t.id}
              >
                {t.id}
              </Link>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    t.eval_resolved === true && "bg-[hsl(var(--success))]",
                    t.eval_resolved === false && "bg-[hsl(var(--danger))]",
                    t.eval_resolved == null && "bg-muted-foreground",
                  )}
                />
                <span className="font-mono text-xs tabular-nums">{value}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
