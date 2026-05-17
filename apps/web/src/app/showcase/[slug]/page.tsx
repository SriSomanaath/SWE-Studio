import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnnotationPanel } from "@/components/AnnotationPanel";
import { Card, CardBody } from "@/components/Card";
import { EvalPill } from "@/components/EvalPill";
import { Stat } from "@/components/Stat";
import { StepNavigator } from "@/components/StepNavigator";
import { getShowcase, getTrajectory, listAnnotations } from "@/lib/api";
import { formatCost, formatCount, formatTokens } from "@/lib/format";
import { ogImage } from "@/lib/og";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const entry = await getShowcase(slug);
    const ogUrl = ogImage({
      title: entry.title,
      subtitle: `${entry.run_id} · ${entry.trajectory_id}`,
      kind: "showcase",
    });
    return {
      title: `${entry.title} · SWE Studio`,
      description:
        entry.description ?? `Curated trajectory: ${entry.run_id} · ${entry.trajectory_id}`,
      alternates: { canonical: `/showcase/${entry.slug}` },
      openGraph: {
        title: entry.title,
        description: entry.description ?? undefined,
        images: [{ url: ogUrl, width: 1200, height: 630 }],
        type: "article",
      },
      twitter: { card: "summary_large_image", images: [ogUrl] },
    };
  } catch {
    return { title: "Not found · SWE Studio" };
  }
}

export default async function ShowcasePage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ step?: string }>;
}) {
  const { slug } = await params;
  const { step: stepParam } = await searchParams;

  let entry;
  try {
    entry = await getShowcase(slug);
  } catch {
    notFound();
  }

  let detail;
  let annotations;
  try {
    [detail, annotations] = await Promise.all([
      getTrajectory(entry.run_id, entry.trajectory_id),
      listAnnotations(entry.run_id, entry.trajectory_id),
    ]);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  const stats = detail.info.model_stats;
  const trajectoryNotes = annotations.filter((a) => a.step_index === -1);
  const initialStep =
    stepParam != null && !Number.isNaN(Number(stepParam))
      ? Number(stepParam)
      : entry.pinned_step ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/showcase" className="text-xs text-muted-foreground hover:text-foreground">
          ← Showcase
        </Link>
        <h1 className="text-2xl font-semibold leading-tight">{entry.title}</h1>
        {entry.description && (
          <p className="text-sm text-muted-foreground">{entry.description}</p>
        )}
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-mono">
            <Link href={`/runs/${entry.run_id}`} className="hover:text-foreground">
              {entry.run_id}
            </Link>
            {" · "}
            <Link
              href={`/runs/${entry.run_id}/${entry.trajectory_id}`}
              className="hover:text-foreground"
            >
              {entry.trajectory_id}
            </Link>
          </span>
          <EvalPill status={detail.eval} />
          <span>· curated by @{entry.author}</span>
        </p>
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
          runId={entry.run_id}
          trajectoryId={entry.trajectory_id}
          stepIndex={-1}
          annotations={trajectoryNotes}
        />
      )}

      <StepNavigator
        key={`${slug}-${initialStep}`}
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
