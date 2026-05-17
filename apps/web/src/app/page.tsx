import Link from "next/link";

import { Card, CardBody, CardHeader } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { listRuns } from "@/lib/api";
import { formatCount } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function HomePage() {
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
        <h1 className="text-2xl font-semibold">Runs</h1>
        <p className="text-sm text-muted-foreground">
          Each run is a directory of agent trajectories. Click a run to step through individual
          instances.
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

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {runs.map((run) => {
          const resolved = run.resolved_count;
          const total = run.trajectory_count;
          const passRate =
            resolved != null && total > 0 ? `${Math.round((resolved / total) * 100)}%` : "—";
          return (
            <Link key={run.id} href={`/runs/${run.id}`}>
              <Card className="h-full transition-colors hover:border-foreground/30">
                <CardHeader>
                  <h2 className="font-mono text-sm font-medium">{run.id}</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">{run.relative_path}</p>
                </CardHeader>
                <CardBody>
                  <div className="grid grid-cols-3 gap-3">
                    <Stat label="Trajectories" value={formatCount(total)} />
                    <Stat label="Resolved" value={formatCount(resolved)} />
                    <Stat label="Pass rate" value={passRate} />
                  </div>
                </CardBody>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
