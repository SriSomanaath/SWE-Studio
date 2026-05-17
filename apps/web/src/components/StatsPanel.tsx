import { Card, CardBody } from "@/components/Card";
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
    <Card>
      <CardBody>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
          <Stat label="Trajectories" value={formatCount(stats.trajectory_count)} />
          <Stat label="Pass rate" value={passRate} />
          <Stat label="Total cost" value={formatCost(stats.total_cost || null)} />
          <Stat label="Mean cost" value={meanCost} />
          <Stat label="Median cost" value={medianCost} />
          <Stat
            label="Tokens (in / out)"
            value={`${formatTokens(stats.total_tokens_sent)} / ${formatTokens(stats.total_tokens_received)}`}
          />
          <Stat label="API calls" value={formatCount(stats.total_api_calls)} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Resolved" value={formatCount(stats.resolved_count)} />
          <Stat label="Submitted" value={formatCount(stats.submitted_count)} />
          <Stat label="Completed" value={formatCount(stats.completed_count)} />
          <Stat
            label="Steps (median / p95)"
            value={`${stats.median_step_count ?? "—"} / ${stats.p95_step_count ?? "—"}`}
          />
        </div>

        {exitEntries.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="uppercase tracking-wide text-muted-foreground">Exit statuses:</span>
            {exitEntries.map(([status, count]) => (
              <span
                key={status}
                className="rounded-md bg-muted px-2 py-0.5 font-mono"
              >
                {status} · {count}
              </span>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
