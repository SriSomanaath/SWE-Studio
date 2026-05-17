import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, CardBody } from "@/components/Card";
import { RunCompareMatrix } from "@/components/RunCompareMatrix";
import { RunPicker } from "@/components/RunPicker";
import { Stat } from "@/components/Stat";
import { compareRuns, listRuns } from "@/lib/api";
import { formatCost, formatCount } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}): Promise<Metadata> {
  const { a, b } = await searchParams;
  if (a && b) {
    return {
      title: `${a} vs ${b} — SWE Studio`,
      description: `Per-instance comparison of runs ${a} and ${b}: pass rate, cost, and step-count deltas.`,
    };
  }
  return {
    title: "Compare runs · SWE Studio",
    description:
      "Compare two benchmark runs side-by-side: per-instance pass rate, cost, step-count, and divergence.",
  };
}

export default async function CompareRunsPage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;
  const runs = await listRuns();

  let result;
  let error: string | null = null;
  if (a && b && a !== b) {
    try {
      result = await compareRuns(a, b);
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) notFound();
      error = err instanceof Error ? err.message : "Failed to load compare result";
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/compare" className="text-xs text-muted-foreground hover:text-foreground">
          ← Compare
        </Link>
        <h1 className="text-2xl font-semibold">Compare runs</h1>
        <p className="text-sm text-muted-foreground">
          Per-instance matrix of pass rate, cost and step count for two benchmark runs.
        </p>
      </div>

      <RunPicker runs={runs} />

      {a && b && a === b && (
        <Card>
          <CardBody>
            <p className="text-sm text-[hsl(var(--warning))]">Pick two different runs.</p>
          </CardBody>
        </Card>
      )}

      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-[hsl(var(--danger))]">{error}</p>
          </CardBody>
        </Card>
      )}

      {result && (
        <>
          <Card>
            <CardBody>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
                <Stat
                  label="Resolved in both"
                  value={formatCount(result.summary.resolved_in_both)}
                />
                <Stat
                  label="Resolved only A"
                  value={formatCount(result.summary.resolved_only_a)}
                />
                <Stat
                  label="Resolved only B"
                  value={formatCount(result.summary.resolved_only_b)}
                />
                <Stat
                  label="Failed in both"
                  value={formatCount(result.summary.failed_in_both)}
                />
                <Stat label="Divergent" value={formatCount(result.summary.divergent_count)} />
                <Stat
                  label="In both / A only / B only"
                  value={`${result.summary.instances_in_both} / ${result.summary.instances_in_a_only} / ${result.summary.instances_in_b_only}`}
                />
                <Stat
                  label="Δ total cost (B − A)"
                  value={
                    <span
                      className={
                        result.summary.cost_delta > 0
                          ? "text-[hsl(var(--danger))]"
                          : result.summary.cost_delta < 0
                            ? "text-[hsl(var(--success))]"
                            : ""
                      }
                    >
                      {result.summary.cost_delta > 0 ? "+" : ""}
                      {formatCost(result.summary.cost_delta)}
                    </span>
                  }
                />
              </div>
            </CardBody>
          </Card>

          <RunCompareMatrix
            aId={result.summary.a_id}
            bId={result.summary.b_id}
            rows={result.instances}
          />
        </>
      )}
    </div>
  );
}
