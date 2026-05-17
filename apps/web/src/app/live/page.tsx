import Link from "next/link";

import { Card, CardBody } from "@/components/Card";
import { EvalPill } from "@/components/EvalPill";
import { listLive } from "@/lib/api";
import { formatCount } from "@/lib/format";

import { LiveAutoRefresh } from "./LiveAutoRefresh";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function LivePage({
  searchParams,
}: {
  searchParams: Promise<{ since?: string }>;
}) {
  const { since } = await searchParams;
  const sinceSeconds = Math.min(3600, Math.max(5, Number(since) || 60));

  let trajectories: Awaited<ReturnType<typeof listLive>> = [];
  let error: string | null = null;
  try {
    trajectories = await listLive(sinceSeconds, 50);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load live activity";
    trajectories = [];
  }

  const now = Date.now() / 1000;

  return (
    <div className="flex flex-col gap-6">
      <LiveAutoRefresh />
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Live activity</h1>
        <p className="text-sm text-muted-foreground">
          Trajectories whose `.traj` file was modified in the last{" "}
          <span className="font-mono">{sinceSeconds}s</span>. Open one to step through it as the
          agent writes.
        </p>
      </div>

      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
          </CardBody>
        </Card>
      )}

      {!error && trajectories.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm">
              Nothing is updating. Trigger the bundled replay tool to demo live mode:
            </p>
            <pre className="mt-3 overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
{`python -m app.tools.replay \\
  --src ../../fixtures/trajectories/sample-run-001/django__django-12345.traj \\
  --dst $TRAJECTORIES_DIR/live-demo/django-12345.traj \\
  --delay 2`}
            </pre>
          </CardBody>
        </Card>
      )}

      {trajectories.length > 0 && (
        <Card>
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="p-3">Run</th>
                  <th className="p-3">Trajectory</th>
                  <th className="p-3">Eval</th>
                  <th className="p-3 text-right">Steps</th>
                  <th className="p-3 text-right">Updated</th>
                </tr>
              </thead>
              <tbody>
                {trajectories.map((t) => {
                  const ago = Math.max(0, now - t.mtime);
                  return (
                    <tr key={`${t.run_id}:${t.trajectory_id}`} className="border-b border-border last:border-b-0 hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs">
                        <Link href={`/runs/${t.run_id}`} className="hover:text-foreground">
                          {t.run_id}
                        </Link>
                      </td>
                      <td className="p-3">
                        <Link
                          href={`/runs/${t.run_id}/${t.trajectory_id}`}
                          className="font-mono text-xs hover:text-foreground"
                        >
                          {t.trajectory_id}
                        </Link>
                      </td>
                      <td className="p-3">
                        <EvalPill status={t.eval} />
                      </td>
                      <td className="p-3 text-right font-mono text-xs">
                        {formatCount(t.step_count)}
                      </td>
                      <td className="p-3 text-right font-mono text-xs text-muted-foreground">
                        {ago < 60 ? `${ago.toFixed(0)}s ago` : `${(ago / 60).toFixed(1)}m ago`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
