import Link from "next/link";

import { Card, CardBody } from "@/components/Card";
import { IconChevronRight, IconRuns } from "@/components/Icons";
import { Stat } from "@/components/Stat";
import { cn } from "@/lib/cn";
import { listRuns } from "@/lib/api";
import { formatCount } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  let runs: Awaited<ReturnType<typeof listRuns>> = [];
  let error: string | null = null;
  try {
    runs = await listRuns();
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load runs";
    runs = [];
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-[24px] font-medium tracking-tight sm:text-[28px]">Runs</h2>
        <p className="mt-1 text-[15px] text-muted-foreground">
          Each run is a set of agent trajectories. Open one to step through its instances.
        </p>
      </div>

      {error && (
        <Card className="border-[hsl(var(--danger))]/40">
          <CardBody>
            <p className="font-medium text-[hsl(var(--danger))]">Could not reach API.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {error}. Start the FastAPI sidecar with{" "}
              <code className="font-mono">pnpm dev:api</code> and ensure
              <code className="ml-1 font-mono">TRAJECTORIES_DIR</code> is set.
            </p>
          </CardBody>
        </Card>
      )}

      {!error && runs.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm">
              No runs found in <code className="font-mono">TRAJECTORIES_DIR</code>. The fixture run
              should appear here once mounted.
            </p>
          </CardBody>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {runs.map((run) => {
          const resolved = run.resolved_count;
          const total = run.trajectory_count;
          const pct = resolved != null && total > 0 ? Math.round((resolved / total) * 100) : null;
          return (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="group rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-foreground/15"
            >
              <Card className="flex h-full flex-col transition-[transform,box-shadow,border-color] duration-300 ease-out-soft group-hover:-translate-y-0.5 group-hover:border-foreground/15 group-hover:shadow-[0_12px_32px_-16px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-3 px-5 pt-5">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-foreground/70">
                    <IconRuns className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-[15px] font-semibold tracking-[-0.2px]">{run.id}</h3>
                    <p className="truncate text-[13px] text-muted-foreground">
                      {run.relative_path !== run.id ? run.relative_path : pct == null ? "Not evaluated" : "Evaluated"}
                    </p>
                  </div>
                  <IconChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform duration-300 ease-out-soft group-hover:translate-x-0.5 group-hover:text-foreground" />
                </div>

                <div className="mt-auto grid grid-cols-3 gap-3 px-5 pb-4 pt-6">
                  <Stat label="Trajectories" value={formatCount(total)} />
                  <Stat label="Resolved" value={formatCount(resolved)} />
                  <Stat label="Pass rate" value={pct == null ? "—" : `${pct}%`} />
                </div>

                {/* Pass-rate bar; a dashed track when there is nothing to measure yet. */}
                <div className="px-5 pb-5">
                  <div
                    className={cn(
                      "h-1.5 overflow-hidden rounded-full",
                      pct == null ? "border border-dashed border-border" : "bg-accent",
                    )}
                  >
                    {pct != null && (
                      <div
                        className="h-full rounded-full bg-[hsl(var(--success))] transition-[width] duration-700 ease-out-soft"
                        style={{ width: `${pct}%` }}
                      />
                    )}
                  </div>
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
