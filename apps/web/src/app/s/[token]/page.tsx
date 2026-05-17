import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnnotationPanel } from "@/components/AnnotationPanel";
import { Card, CardBody } from "@/components/Card";
import { EvalPill } from "@/components/EvalPill";
import { Stat } from "@/components/Stat";
import { StepNavigator } from "@/components/StepNavigator";
import {
  getRunStats,
  getShowcase,
  getTrajectory,
  listAnnotations,
  listTrajectories,
  resolveShare,
} from "@/lib/api";
import { formatCost, formatCount, formatTokens } from "@/lib/format";
import { ogImage } from "@/lib/og";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ token: string }>;
}

async function safeResolve(token: string) {
  try {
    return await resolveShare(token);
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) } as const;
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { token } = await params;
  const resolved = await safeResolve(token);
  if ("error" in resolved) return { title: "Shared link · SWE Studio" };
  const title =
    resolved.kind === "trajectory"
      ? `${resolved.target_traj_id} (shared)`
      : resolved.kind === "showcase"
        ? `${resolved.target_slug} (shared)`
        : `${resolved.target_run_id} (shared)`;
  const subtitle =
    resolved.kind === "trajectory"
      ? `${resolved.target_run_id} · public link`
      : "public link";
  return {
    title: `${title} · SWE Studio`,
    description: resolved.description ?? "Public share from SWE Studio.",
    openGraph: {
      title,
      description: resolved.description ?? undefined,
      images: [
        { url: ogImage({ title, subtitle, kind: "showcase" }), width: 1200, height: 630 },
      ],
      type: "article",
    },
    robots: { index: true, follow: true },
  };
}

function PublicBanner({ kind, expiresAt }: { kind: string; expiresAt: number | null | undefined }) {
  const expiry =
    expiresAt && expiresAt > Date.now() / 1000
      ? new Date(expiresAt * 1000).toLocaleString()
      : null;
  return (
    <div className="flex items-center justify-between rounded-md border border-[hsl(var(--success))]/30 bg-[hsl(var(--success))]/10 px-3 py-2 text-xs">
      <span className="flex items-center gap-2">
        <span className="rounded bg-[hsl(var(--success))] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-background">
          public
        </span>
        <span className="text-muted-foreground">Shared {kind} — anyone with this link can view.</span>
      </span>
      {expiry && (
        <span className="text-muted-foreground">Expires {expiry}</span>
      )}
    </div>
  );
}

export default async function SharePage({ params }: PageProps) {
  const { token } = await params;
  const resolved = await safeResolve(token);
  if ("error" in resolved) {
    if (resolved.error.includes("410")) {
      return (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <h1 className="text-2xl font-semibold">Link expired or revoked</h1>
          <p className="text-sm text-muted-foreground">
            This share link is no longer active. Ask the creator for a fresh one.
          </p>
          <Link
            href="/"
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Back to home
          </Link>
        </div>
      );
    }
    notFound();
  }

  if (resolved.kind === "trajectory") {
    const runId = resolved.target_run_id!;
    const trajId = resolved.target_traj_id!;
    const [detail, annotations] = await Promise.all([
      getTrajectory(runId, trajId),
      listAnnotations(runId, trajId),
    ]);
    const stats = detail.info.model_stats;
    const trajectoryNotes = annotations.filter((a) => a.step_index === -1);
    return (
      <div className="flex flex-col gap-6">
        <PublicBanner kind="trajectory" expiresAt={resolved.expires_at} />
        <div className="flex flex-col gap-2">
          <h1 className="font-mono text-2xl font-semibold">{detail.id}</h1>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{detail.run_id}</span>
            <EvalPill status={detail.eval} />
          </div>
          {resolved.description && (
            <p className="text-sm text-muted-foreground">{resolved.description}</p>
          )}
        </div>
        <Card>
          <CardBody>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <Stat label="Exit status" value={detail.info.exit_status ?? "—"} />
              <Stat label="API calls" value={formatCount(stats.api_calls)} />
              <Stat label="Tokens in" value={formatTokens(stats.tokens_sent)} />
              <Stat label="Tokens out" value={formatTokens(stats.tokens_received)} />
              <Stat label="Cost" value={formatCost(stats.instance_cost)} />
            </div>
          </CardBody>
        </Card>
        {trajectoryNotes.length > 0 && (
          <AnnotationPanel
            runId={runId}
            trajectoryId={trajId}
            stepIndex={-1}
            annotations={trajectoryNotes}
          />
        )}
        <StepNavigator
          runId={runId}
          trajectoryId={trajId}
          steps={detail.steps}
          problemStatement={detail.problem_statement}
          submission={detail.info.submission}
          annotations={annotations}
        />
      </div>
    );
  }

  if (resolved.kind === "run") {
    const runId = resolved.target_run_id!;
    const [stats, listResult] = await Promise.all([
      getRunStats(runId),
      listTrajectories(runId, { limit: 100 }),
    ]);
    return (
      <div className="flex flex-col gap-6">
        <PublicBanner kind="run" expiresAt={resolved.expires_at} />
        <div className="flex flex-col gap-1">
          <h1 className="font-mono text-2xl font-semibold">{runId}</h1>
          <p className="text-sm text-muted-foreground">
            {stats.trajectory_count} trajectories ·{" "}
            {stats.pass_rate != null ? `${(stats.pass_rate * 100).toFixed(1)}% pass rate` : "no eval"}
          </p>
        </div>
        <Card>
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="p-3">Instance</th>
                  <th className="p-3">Eval</th>
                  <th className="p-3">Exit</th>
                  <th className="p-3 text-right">Steps</th>
                  <th className="p-3 text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {listResult.data.map((t) => (
                  <tr key={t.id} className="border-b border-border last:border-b-0">
                    <td className="p-3 font-mono text-xs">{t.id}</td>
                    <td className="p-3">
                      <EvalPill status={t.eval} />
                    </td>
                    <td className="p-3 font-mono text-xs text-muted-foreground">
                      {t.exit_status ?? "—"}
                    </td>
                    <td className="p-3 text-right font-mono text-xs">{formatCount(t.step_count)}</td>
                    <td className="p-3 text-right font-mono text-xs">{formatCost(t.instance_cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      </div>
    );
  }

  // showcase
  const slug = resolved.target_slug!;
  const entry = await getShowcase(slug);
  const [detail, annotations] = await Promise.all([
    getTrajectory(entry.run_id, entry.trajectory_id),
    listAnnotations(entry.run_id, entry.trajectory_id),
  ]);
  const trajectoryNotes = annotations.filter((a) => a.step_index === -1);
  return (
    <div className="flex flex-col gap-6">
      <PublicBanner kind="showcase" expiresAt={resolved.expires_at} />
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold leading-tight">{entry.title}</h1>
        {entry.description && (
          <p className="text-sm text-muted-foreground">{entry.description}</p>
        )}
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          {entry.run_id} · {entry.trajectory_id}
          {entry.pinned_step != null && ` · pinned to step ${entry.pinned_step + 1}`}
        </p>
      </div>
      {trajectoryNotes.length > 0 && (
        <AnnotationPanel
          runId={entry.run_id}
          trajectoryId={entry.trajectory_id}
          stepIndex={-1}
          annotations={trajectoryNotes}
        />
      )}
      <StepNavigator
        runId={entry.run_id}
        trajectoryId={entry.trajectory_id}
        steps={detail.steps}
        problemStatement={detail.problem_statement}
        submission={detail.info.submission}
        annotations={annotations}
      />
    </div>
  );
}
