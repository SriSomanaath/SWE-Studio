import Link from "next/link";
import { notFound } from "next/navigation";

import { FiltersBar } from "@/components/FiltersBar";
import { StatsPanel } from "@/components/StatsPanel";
import { VirtualizedTrajectoryTable } from "@/components/VirtualizedTrajectoryTable";
import { getRunStats, listTrajectories } from "@/lib/api";
import type { SortField, SortOrder, StatusFilter } from "@/lib/types";

export const dynamic = "force-dynamic";

type SearchParams = {
  status?: string;
  exit?: string;
  search?: string;
  cost_min?: string;
  cost_max?: string;
  sort?: string;
  order?: string;
};

function s(v: string | undefined): string | undefined {
  return v && v.length > 0 ? v : undefined;
}

const STATUS_VALUES = new Set<StatusFilter>([
  "any",
  "resolved",
  "submitted",
  "failed",
  "unscored",
]);
const SORT_VALUES = new Set<SortField>([
  "id",
  "instance_cost",
  "api_calls",
  "step_count",
  "tokens_sent",
]);

function asStatus(v: string | undefined): StatusFilter {
  return v && STATUS_VALUES.has(v as StatusFilter) ? (v as StatusFilter) : "any";
}
function asSort(v: string | undefined): SortField {
  return v && SORT_VALUES.has(v as SortField) ? (v as SortField) : "id";
}
function asOrder(v: string | undefined): SortOrder {
  return v === "desc" ? "desc" : "asc";
}

export default async function RunPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { runId } = await params;
  const sp = await searchParams;

  const filters = {
    status: asStatus(sp.status),
    exit: s(sp.exit) ?? "",
    search: s(sp.search) ?? "",
    costMin: s(sp.cost_min) ?? "",
    costMax: s(sp.cost_max) ?? "",
    sort: asSort(sp.sort),
    order: asOrder(sp.order),
  };

  let listResult;
  let stats;
  try {
    [listResult, stats] = await Promise.all([
      listTrajectories(runId, { ...filters, limit: 5000 }),
      getRunStats(runId),
    ]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  const { data: trajectories, total } = listResult;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/" className="text-xs text-muted-foreground hover:text-foreground">
          ← All runs
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-mono text-2xl font-semibold">{runId}</h1>
            <p className="text-sm text-muted-foreground">
              {stats.trajectory_count} trajectories ·{" "}
              {stats.pass_rate != null
                ? `${(stats.pass_rate * 100).toFixed(1)}% pass rate`
                : "no eval"}
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href={`/runs/${runId}/insights`}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Insights →
            </Link>
            <Link
              href={`/runs/${runId}/analytics`}
              className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
            >
              Analytics →
            </Link>
          </div>
        </div>
      </div>

      <StatsPanel stats={stats} />

      <FiltersBar total={total} />

      <VirtualizedTrajectoryTable runId={runId} trajectories={trajectories} />
    </div>
  );
}
