import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, CardBody } from "@/components/Card";
import { getRunInsights } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatCost, formatCount } from "@/lib/format";
import { ogImage } from "@/lib/og";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string }>;
}): Promise<Metadata> {
  const { runId } = await params;
  return {
    title: `Insights — ${runId} · SWE Studio`,
    description: `Action-pattern clusters and similarity insights for agent run ${runId}.`,
    openGraph: {
      title: `Insights · ${runId}`,
      images: [
        {
          url: ogImage({ title: "Insights", subtitle: runId, kind: "analytics" }),
          width: 1200,
          height: 630,
        },
      ],
    },
  };
}

export default async function InsightsPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  let insights;
  try {
    insights = await getRunInsights(runId);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          href={`/runs/${runId}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← {runId}
        </Link>
        <h1 className="text-2xl font-semibold">Insights</h1>
        <p className="text-sm text-muted-foreground">
          Trajectories grouped by their action-verb fingerprint — the top-3 most-common command
          verbs an agent used. A cluster reveals a shared strategy.
        </p>
      </div>

      {insights.clusters.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">No trajectories to cluster.</p>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="p-3">Fingerprint</th>
                  <th className="p-3 text-right">Size</th>
                  <th className="p-3 text-right">Resolved</th>
                  <th className="p-3 text-right">Failed</th>
                  <th className="p-3 text-right">Pass</th>
                  <th className="p-3 text-right">Median steps</th>
                  <th className="p-3 text-right">Mean cost</th>
                  <th className="p-3">Examples</th>
                </tr>
              </thead>
              <tbody>
                {insights.clusters.map((c) => {
                  const passRate =
                    c.size > 0 ? `${Math.round((c.resolved_count / c.size) * 100)}%` : "—";
                  return (
                    <tr
                      key={c.fingerprint}
                      className="border-b border-border last:border-b-0 hover:bg-muted/30"
                    >
                      <td className="p-3 font-mono text-xs">
                        {c.fingerprint.split("·").map((tok, i) => (
                          <span
                            key={i}
                            className="mr-1 inline-block rounded bg-muted px-1.5 py-0.5"
                          >
                            {tok}
                          </span>
                        ))}
                      </td>
                      <td className="p-3 text-right font-mono text-xs">{c.size}</td>
                      <td className="p-3 text-right font-mono text-xs text-[hsl(var(--success))]">
                        {c.resolved_count}
                      </td>
                      <td className="p-3 text-right font-mono text-xs text-[hsl(var(--danger))]">
                        {c.failed_count}
                      </td>
                      <td
                        className={cn(
                          "p-3 text-right font-mono text-xs",
                          c.resolved_count === c.size && "text-[hsl(var(--success))]",
                          c.resolved_count === 0 && c.failed_count > 0 && "text-[hsl(var(--danger))]",
                        )}
                      >
                        {passRate}
                      </td>
                      <td className="p-3 text-right font-mono text-xs">
                        {c.median_step_count ?? "—"}
                      </td>
                      <td className="p-3 text-right font-mono text-xs">
                        {formatCost(c.mean_cost)}
                      </td>
                      <td className="p-3">
                        <div className="flex flex-wrap gap-1.5">
                          {c.sample_ids.map((id) => (
                            <Link
                              key={id}
                              href={`/runs/${runId}/${id}`}
                              className="rounded-md border border-border px-1.5 py-0.5 font-mono text-[10px] hover:bg-accent"
                            >
                              {id}
                            </Link>
                          ))}
                        </div>
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
