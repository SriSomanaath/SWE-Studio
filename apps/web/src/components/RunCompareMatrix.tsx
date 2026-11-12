"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { cn } from "@/lib/cn";
import { formatCost } from "@/lib/format";
import type { InstanceCompareRow, InstanceSide } from "@/lib/types";

type Filter = "all" | "divergent" | "a_wins" | "b_wins" | "in_both" | "only_a" | "only_b";

const FILTER_OPTIONS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "All" },
  { value: "divergent", label: "Only divergent" },
  { value: "a_wins", label: "A wins" },
  { value: "b_wins", label: "B wins" },
  { value: "in_both", label: "In both" },
  { value: "only_a", label: "Only A" },
  { value: "only_b", label: "Only B" },
];

export function RunCompareMatrix({
  aId,
  bId,
  rows,
}: {
  aId: string;
  bId: string;
  rows: InstanceCompareRow[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const filter = (params.get("view") as Filter) || "all";

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      const ra = row.in_a.eval_resolved;
      const rb = row.in_b.eval_resolved;
      switch (filter) {
        case "divergent":
          return row.divergent;
        case "a_wins":
          return ra === true && rb !== true;
        case "b_wins":
          return rb === true && ra !== true;
        case "in_both":
          return row.in_a.present && row.in_b.present;
        case "only_a":
          return row.in_a.present && !row.in_b.present;
        case "only_b":
          return !row.in_a.present && row.in_b.present;
        default:
          return true;
      }
    });
  }, [rows, filter]);

  function setFilter(next: Filter) {
    const sp = new URLSearchParams(params.toString());
    if (next === "all") sp.delete("view");
    else sp.set("view", next);
    router.replace(`?${sp.toString()}`, { scroll: false });
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {FILTER_OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => setFilter(o.value)}
            className={cn(
              "rounded-xl border border-border/70 px-2.5 py-1 hover:bg-accent",
              filter === o.value && "bg-accent text-accent-foreground",
            )}
          >
            {o.label}
          </button>
        ))}
        <span className="ml-auto text-muted-foreground">
          {filtered.length} of {rows.length} instances
        </span>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border/70 bg-card">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/30 text-left text-xs font-medium text-muted-foreground">
            <tr>
              <th className="p-3">Instance</th>
              <th className="p-3">A · {aId}</th>
              <th className="p-3">B · {bId}</th>
              <th className="p-3 text-right">Δ cost</th>
              <th className="p-3 text-right">Compare</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-border last:border-b-0 hover:bg-muted/30",
                  row.divergent && "bg-[hsl(var(--warning))]/5",
                )}
              >
                <td className="p-3 font-mono text-xs">{row.id}</td>
                <td className="p-3">
                  <SideCell side={row.in_a} />
                </td>
                <td className="p-3">
                  <SideCell side={row.in_b} />
                </td>
                <td className="p-3 text-right font-mono text-xs">
                  {row.cost_delta == null ? "—" : (
                    <span
                      className={cn(
                        row.cost_delta > 0 && "text-[hsl(var(--danger))]",
                        row.cost_delta < 0 && "text-[hsl(var(--success))]",
                      )}
                    >
                      {row.cost_delta > 0 ? "+" : ""}
                      {formatCost(row.cost_delta)}
                    </span>
                  )}
                </td>
                <td className="p-3 text-right">
                  {row.in_a.present && row.in_b.present ? (
                    <Link
                      href={`/compare?a=${encodeURIComponent(`${aId}:${row.id}`)}&b=${encodeURIComponent(`${bId}:${row.id}`)}`}
                      className="rounded-xl border border-border/70 px-2 py-1 text-xs hover:bg-accent"
                    >
                      open →
                    </Link>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-muted-foreground">
                  No instances match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function SideCell({ side }: { side: InstanceSide }) {
  if (!side.present) {
    return <span className="text-xs text-muted-foreground">absent</span>;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          side.eval_resolved === true && "bg-[hsl(var(--success))]",
          side.eval_resolved === false && "bg-[hsl(var(--danger))]",
          side.eval_resolved == null && "bg-muted-foreground",
        )}
      />
      <span className="font-mono">{formatCost(side.instance_cost)}</span>
      <span className="font-mono text-muted-foreground">·</span>
      <span className="font-mono text-muted-foreground">
        {side.step_count ?? 0} steps
      </span>
      {side.exit_status && (
        <span className="font-mono text-[10px] text-muted-foreground">
          ({side.exit_status})
        </span>
      )}
    </div>
  );
}
