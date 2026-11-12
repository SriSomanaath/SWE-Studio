"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import Link from "next/link";
import { useRef } from "react";

import { cn } from "@/lib/cn";
import { formatCost, formatCount, formatTokens } from "@/lib/format";
import type { TrajectorySummary } from "@/lib/types";

import { EvalPill } from "./EvalPill";

const ROW_HEIGHT = 44;
const HEADER_HEIGHT = 36;

const GRID_COLS = "minmax(220px,2fr) 110px minmax(120px,1fr) 70px 90px 90px 100px 80px";

export function VirtualizedTrajectoryTable({
  runId,
  trajectories,
}: {
  runId: string;
  trajectories: TrajectorySummary[];
}) {
  const parentRef = useRef<HTMLDivElement | null>(null);

  const rowVirtualizer = useVirtualizer({
    count: trajectories.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  if (trajectories.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-2xl border border-border/70 bg-card text-sm text-muted-foreground">
        No trajectories match the current filters.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border/70 bg-card">
      <div
        className="grid items-center gap-3 border-b border-border bg-muted/30 px-3 text-xs font-medium text-muted-foreground"
        style={{ gridTemplateColumns: GRID_COLS, height: HEADER_HEIGHT }}
      >
        <span>Instance</span>
        <span>Eval</span>
        <span>Exit</span>
        <span className="text-right">Steps</span>
        <span className="text-right">API</span>
        <span className="text-right">In</span>
        <span className="text-right">Out</span>
        <span className="text-right">Cost</span>
      </div>

      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ maxHeight: `min(70vh, ${ROW_HEIGHT * 20}px)` }}
      >
        <div
          style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}
        >
          {rowVirtualizer.getVirtualItems().map((vi) => {
            const t = trajectories[vi.index];
            return (
              <div
                key={t.id}
                className={cn(
                  "absolute left-0 right-0 grid items-center gap-3 border-b border-border px-3 transition-colors hover:bg-muted/30",
                  vi.index === trajectories.length - 1 && "border-b-0",
                )}
                style={{
                  gridTemplateColumns: GRID_COLS,
                  height: vi.size,
                  transform: `translateY(${vi.start}px)`,
                }}
              >
                <Link
                  href={`/runs/${runId}/${t.id}`}
                  className="truncate font-mono text-xs hover:text-foreground"
                  title={t.id}
                >
                  {t.id}
                </Link>
                <EvalPill status={t.eval} />
                <span className="truncate font-mono text-xs text-muted-foreground" title={t.exit_status ?? ""}>
                  {t.exit_status ?? "—"}
                </span>
                <span className="text-right font-mono text-xs">{formatCount(t.step_count)}</span>
                <span className="text-right font-mono text-xs">{formatCount(t.api_calls)}</span>
                <span className="text-right font-mono text-xs">{formatTokens(t.tokens_sent)}</span>
                <span className="text-right font-mono text-xs">{formatTokens(t.tokens_received)}</span>
                <span className="text-right font-mono text-xs">{formatCost(t.instance_cost)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
