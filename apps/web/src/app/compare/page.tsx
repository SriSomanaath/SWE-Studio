import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, CardBody } from "@/components/Card";
import { CodeBlock } from "@/components/CodeBlock";
import { DiffOverlapPanel } from "@/components/DiffOverlapPanel";
import { Stat } from "@/components/Stat";
import { getCompare } from "@/lib/api";
import { formatCost, formatCount } from "@/lib/format";
import type { TrajectoryStep } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;

  if (!a || !b) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Compare</h1>
        <p className="text-sm text-muted-foreground">
          Two kinds of comparison are available.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-border/70 bg-card p-4">
            <h2 className="text-sm font-semibold">Two trajectories</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Step-by-step diff of a single instance under two runs (e.g. same problem, two models).
            </p>
            <p className="mt-3 font-mono text-xs">
              /compare?a=run:traj&amp;b=run:traj
            </p>
          </div>
          <Link
            href="/compare/runs"
            className="rounded-2xl border border-border/70 bg-card p-4 transition-colors hover:border-foreground/30"
          >
            <h2 className="text-sm font-semibold">Two runs</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Per-instance matrix across two benchmark runs. Surfaces divergence and cost delta.
            </p>
            <p className="mt-3 font-mono text-xs">/compare/runs?a=…&amp;b=…</p>
          </Link>
        </div>
      </div>
    );
  }

  let result;
  try {
    result = await getCompare(a, b);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }

  const { a: detailA, b: detailB, summary } = result;
  const maxLen = Math.max(detailA.steps.length, detailB.steps.length);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/" className="text-xs text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <h1 className="text-2xl font-semibold">Compare trajectories</h1>
        <p className="font-mono text-xs text-muted-foreground">
          {detailA.run_id}:{detailA.id} ↔ {detailB.run_id}:{detailB.id}
        </p>
      </div>

      <Card>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <Stat
              label="Steps (A → B)"
              value={`${formatCount(summary.step_count_a)} → ${formatCount(summary.step_count_b)} (${summary.step_count_delta >= 0 ? "+" : ""}${summary.step_count_delta})`}
            />
            <Stat
              label="Cost (A → B)"
              value={`${formatCost(summary.cost_a)} → ${formatCost(summary.cost_b)}`}
            />
            <Stat
              label="API calls"
              value={`${formatCount(summary.api_calls_a)} / ${formatCount(summary.api_calls_b)}`}
            />
            <Stat
              label="Eval (resolved)"
              value={`${pill(summary.eval_resolved_a)} / ${pill(summary.eval_resolved_b)}`}
            />
            <Stat
              label="Action overlap"
              value={`${(summary.action_overlap_ratio * 100).toFixed(0)}%`}
            />
          </div>
        </CardBody>
      </Card>

      <DiffOverlapPanel analysis={result.diff_analysis} />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <ColumnHeader label="A" runId={detailA.run_id} trajId={detailA.id} />
        <ColumnHeader label="B" runId={detailB.run_id} trajId={detailB.id} />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {Array.from({ length: maxLen }).flatMap((_, i) => [
          <StepCell
            key={`a-${i}`}
            step={detailA.steps[i]}
            index={i}
            otherAction={detailB.steps[i]?.action}
          />,
          <StepCell
            key={`b-${i}`}
            step={detailB.steps[i]}
            index={i}
            otherAction={detailA.steps[i]?.action}
          />,
        ])}
      </div>
    </div>
  );
}

function pill(v: boolean | null): string {
  if (v == null) return "—";
  return v ? "✅" : "❌";
}

function ColumnHeader({
  label,
  runId,
  trajId,
}: {
  label: string;
  runId: string;
  trajId: string;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-muted/30 p-3">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="mt-0.5 truncate font-mono text-sm">
        <Link href={`/runs/${runId}/${trajId}`} className="hover:text-foreground">
          {runId}:{trajId}
        </Link>
      </div>
    </div>
  );
}

function StepCell({
  step,
  index,
  otherAction,
}: {
  step: TrajectoryStep | undefined;
  index: number;
  otherAction: string | undefined;
}) {
  if (!step) {
    return (
      <div className="flex h-full min-h-[120px] items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
        no step {index + 1}
      </div>
    );
  }
  const actionsDiffer =
    otherAction != null && step.action.trim() !== otherAction.trim();
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border/70 bg-card p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Step {index + 1}</span>
        {actionsDiffer && (
          <span className="rounded bg-[hsl(var(--warning))]/15 px-1.5 py-0.5 text-[10px] font-medium font-medium text-[hsl(var(--warning))]">
            differs
          </span>
        )}
      </div>
      {step.thought && (
        <p className="text-xs leading-relaxed text-muted-foreground line-clamp-3">{step.thought}</p>
      )}
      {step.action && <CodeBlock className="max-h-[140px]">{step.action}</CodeBlock>}
      {step.observation && (
        <CodeBlock className="max-h-[140px]">{step.observation}</CodeBlock>
      )}
    </div>
  );
}
