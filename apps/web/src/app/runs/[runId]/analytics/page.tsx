import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  CostHistogramChart,
  ExitStatusChart,
  PassRateChart,
  StepHistogramChart,
} from "@/components/AnalyticsCharts";
import { Card, CardBody } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { TopList } from "@/components/TopList";
import { getRunAnalytics, getRunStats } from "@/lib/api";
import { formatCost, formatCount, formatTokens } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string }>;
}): Promise<Metadata> {
  const { runId } = await params;
  return {
    title: `Analytics — ${runId} · SWE Studio`,
    description: `Cost, step-count, and pass-rate distributions for agent run ${runId}.`,
  };
}

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  let stats;
  let analytics;
  try {
    [stats, analytics] = await Promise.all([getRunStats(runId), getRunAnalytics(runId)]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  const passRatePct =
    stats.pass_rate != null ? `${(stats.pass_rate * 100).toFixed(1)}%` : "—";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          href={`/runs/${runId}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← {runId}
        </Link>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Distributions, top-N trajectories, and pass-rate breakdowns for{" "}
          <span className="font-mono">{runId}</span>.
        </p>
      </div>

      {/* Plain-text summary for AEO / screen readers. Mirrors the chart data. */}
      <Card>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
            <Stat label="Trajectories" value={formatCount(stats.trajectory_count)} />
            <Stat label="Pass rate" value={passRatePct} />
            <Stat label="Resolved" value={formatCount(stats.resolved_count)} />
            <Stat label="Total cost" value={formatCost(stats.total_cost || null)} />
            <Stat
              label="Tokens in / out"
              value={`${formatTokens(stats.total_tokens_sent)} / ${formatTokens(stats.total_tokens_received)}`}
            />
            <Stat
              label="Steps median / p95"
              value={`${stats.median_step_count ?? "—"} / ${stats.p95_step_count ?? "—"}`}
            />
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <CostHistogramChart bins={analytics.cost_histogram} />
        <StepHistogramChart bins={analytics.step_histogram} />
        <PassRateChart buckets={analytics.pass_rate_by_step_bucket} />
        <ExitStatusChart data={analytics.exit_status_breakdown} />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <TopList
          title="Most expensive trajectories"
          subtitle="top 10 by instance cost"
          runId={runId}
          items={analytics.top_costly}
          metric="cost"
        />
        <TopList
          title="Longest trajectories"
          subtitle="top 10 by step count"
          runId={runId}
          items={analytics.top_longest}
          metric="steps"
        />
      </div>
    </div>
  );
}
