import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, CardBody } from "@/components/Card";
import { findSimilar } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string; trajectoryId: string }>;
}): Promise<Metadata> {
  const { runId, trajectoryId } = await params;
  return {
    title: `Similar to ${trajectoryId} · SWE Studio`,
    description: `Trajectories that share action verbs with ${runId}:${trajectoryId}.`,
  };
}

export default async function SimilarPage({
  params,
}: {
  params: Promise<{ runId: string; trajectoryId: string }>;
}) {
  const { runId, trajectoryId } = await params;
  let hits;
  try {
    hits = await findSimilar(runId, trajectoryId, 20);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          href={`/runs/${runId}/${trajectoryId}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← {trajectoryId}
        </Link>
        <h1 className="text-2xl font-semibold">Similar trajectories</h1>
        <p className="text-sm text-muted-foreground">
          Trajectories that share the most distinctive action tokens with{" "}
          <span className="font-mono">
            {runId}:{trajectoryId}
          </span>
          .
        </p>
      </div>

      {hits.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">
              No similar trajectories found. This run may be the only one taking this approach.
            </p>
          </CardBody>
        </Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {hits.map((h) => (
            <li key={`${h.run_id}:${h.trajectory_id}`}>
              <Link
                href={`/runs/${h.run_id}/${h.trajectory_id}`}
                className="block rounded-xl border border-border/70 bg-card p-3 hover:border-foreground/30"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-xs">
                    {h.run_id} · {h.trajectory_id}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    score {h.score.toFixed(2)}
                  </span>
                </div>
                <p
                  className="mt-1 text-xs text-muted-foreground"
                  dangerouslySetInnerHTML={{ __html: renderSnippet(h.snippet) }}
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function renderSnippet(s: string): string {
  const escaped = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped.replace(
    /\[([^\]]+)\]/g,
    '<mark class="rounded bg-[hsl(var(--warning))]/30 px-0.5 text-foreground">$1</mark>',
  );
}
