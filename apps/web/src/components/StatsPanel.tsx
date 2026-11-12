import { Stat } from "@/components/Stat";
import { formatCost, formatCount, formatTokens } from "@/lib/format";
import type { RunStats } from "@/lib/types";

export function StatsPanel({ stats }: { stats: RunStats }) {
  const passRate =
    stats.pass_rate == null ? "—" : `${(stats.pass_rate * 100).toFixed(1)}%`;
  const meanCost = formatCost(stats.mean_cost);
  const medianCost = formatCost(stats.median_cost);
  const exitEntries = Object.entries(stats.exit_status_counts).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <section className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        <Stat tile label="Trajectories" value={formatCount(stats.trajectory_count)} />
        <Stat tile label="Pass rate" value={passRate} />
        <Stat tile label="Resolved" value={formatCount(stats.resolved_count)} />
        <Stat tile label="Total cost" value={formatCost(stats.total_cost || null)} />
        <Stat tile label="Mean cost" value={meanCost} />
        <Stat tile label="Median cost" value={medianCost} />
        <Stat
          tile
          label="Tokens in / out"
          value={`${formatTokens(stats.total_tokens_sent)} / ${formatTokens(stats.total_tokens_received)}`}
        />
        <Stat tile label="API calls" value={formatCount(stats.total_api_calls)} />
        <Stat tile label="Submitted" value={formatCount(stats.submitted_count)} />
        <Stat tile label="Completed" value={formatCount(stats.completed_count)} />
        <Stat
          tile
          label="Steps median / p95"
          value={`${stats.median_step_count ?? "—"} / ${stats.p95_step_count ?? "—"}`}
        />
      </div>

      {exitEntries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <span className="text-muted-foreground">Exit statuses</span>
          {exitEntries.map(([status, count]) => (
            <span
              key={status}
              className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-background px-2.5 py-0.5 font-mono text-xs"
            >
              {status}
              <span className="text-muted-foreground">{count}</span>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
