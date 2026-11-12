import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnnotationPanel } from "@/components/AnnotationPanel";
import { BookmarkButton } from "@/components/BookmarkButton";
import { EvalPill } from "@/components/EvalPill";
import { LiveSync } from "@/components/LiveSync";
import { ShareMenu } from "@/components/ShareMenu";
import { Stat } from "@/components/Stat";
import { StepNavigator } from "@/components/StepNavigator";
import { SummarizeButton } from "@/components/SummarizeButton";
import { getTrajectory, listAnnotations } from "@/lib/api";
import { formatCost, formatCount, formatTokens } from "@/lib/format";
import { ogImage } from "@/lib/og";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ runId: string; trajectoryId: string }>;
}): Promise<Metadata> {
  const { runId, trajectoryId } = await params;
  const ogUrl = ogImage({
    title: trajectoryId,
    subtitle: runId,
    kind: "trajectory",
  });
  return {
    title: `${trajectoryId} — ${runId} · SWE Studio`,
    description: `Step through agent trajectory ${trajectoryId} from run ${runId}.`,
    openGraph: {
      title: `${trajectoryId} · ${runId}`,
      images: [{ url: ogUrl, width: 1200, height: 630 }],
      type: "article",
    },
    twitter: { card: "summary_large_image", images: [ogUrl] },
  };
}

export const dynamic = "force-dynamic";

export default async function TrajectoryPage({
  params,
}: {
  params: Promise<{ runId: string; trajectoryId: string }>;
}) {
  const { runId, trajectoryId } = await params;

  let detail;
  let annotations;
  try {
    [detail, annotations] = await Promise.all([
      getTrajectory(runId, trajectoryId),
      listAnnotations(runId, trajectoryId),
    ]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  const stats = detail.info.model_stats;
  const trajectoryNotes = annotations.filter((a) => a.step_index === -1);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link
          href={`/runs/${runId}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← {runId}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold">{detail.id}</h1>
          <EvalPill status={detail.eval} />
          <LiveSync
            runId={runId}
            trajectoryId={trajectoryId}
            initialStepCount={detail.steps.length}
            exitStatus={detail.info.exit_status ?? null}
          />
          <div className="ml-auto flex items-center gap-2">
            <Link
              href={`/runs/${runId}/${trajectoryId}/similar`}
              className="rounded-xl border border-border/70 px-2.5 py-1 text-xs hover:bg-accent"
            >
              Find similar
            </Link>
            <SummarizeButton runId={runId} trajectoryId={trajectoryId} />
            <BookmarkButton
              runId={runId}
              trajectoryId={trajectoryId}
              initialIsBookmarked={false}
            />
            <ShareMenu runId={runId} trajectoryId={trajectoryId} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            <Stat tile label="Exit status" value={detail.info.exit_status ?? "—"} />
            <Stat tile label="API calls" value={formatCount(stats.api_calls)} />
            <Stat tile label="Tokens in" value={formatTokens(stats.tokens_sent)} />
            <Stat tile label="Tokens out" value={formatTokens(stats.tokens_received)} />
            <Stat tile label="Cost" value={formatCost(stats.instance_cost)} />
      </div>

      <AnnotationPanel
        runId={runId}
        trajectoryId={trajectoryId}
        stepIndex={-1}
        annotations={trajectoryNotes}
      />

      <StepNavigator
        runId={runId}
        trajectoryId={trajectoryId}
        steps={detail.steps}
        problemStatement={detail.problem_statement}
        submission={detail.info.submission}
        annotations={annotations}
      />
    </div>
  );
}
