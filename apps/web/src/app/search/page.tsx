import type { Metadata } from "next";

import { Card, CardBody } from "@/components/Card";
import { SearchHitItem } from "@/components/SearchHits";
import { searchTrajectories } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const { q } = await searchParams;
  if (q) return { title: `“${q}” — Search · SWE Studio` };
  return { title: "Search · SWE Studio" };
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; run_id?: string; kind?: string }>;
}) {
  const { q, run_id, kind } = await searchParams;
  const query = q?.trim() ?? "";
  const validKind =
    kind === "trajectory" || kind === "annotation" ? (kind as "trajectory" | "annotation") : "all";

  if (!query) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold">Search</h1>
        <p className="text-sm text-muted-foreground">
          Type a query into the box, or open the palette with{" "}
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-xs">
            ⌘K
          </kbd>{" "}
          /{" "}
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-xs">
            Ctrl K
          </kbd>
          . Searches problem statements, step thoughts/actions/observations, and annotations.
        </p>
      </div>
    );
  }

  let result;
  try {
    result = await searchTrajectories({ q: query, runId: run_id, kind: validKind, limit: 100 });
  } catch (err) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-[hsl(var(--danger))]">
            Search failed: {err instanceof Error ? err.message : "unknown error"}
          </p>
        </CardBody>
      </Card>
    );
  }

  const trajectoryHits = result.hits.filter((h) => h.kind === "trajectory");
  const annotationHits = result.hits.filter((h) => h.kind === "annotation");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">
          Search · <span className="font-mono">{query}</span>
        </h1>
        <p className="text-sm text-muted-foreground">
          {result.hits.length} hits
          {run_id && (
            <>
              {" "}
              · scoped to <span className="font-mono">{run_id}</span>
            </>
          )}
        </p>
      </div>

      {trajectoryHits.length > 0 && (
        <Section title="Trajectories" count={trajectoryHits.length}>
          {trajectoryHits.map((h) => (
            <SearchHitItem key={`t-${h.run_id}:${h.trajectory_id}`} hit={h} />
          ))}
        </Section>
      )}

      {annotationHits.length > 0 && (
        <Section title="Annotations" count={annotationHits.length}>
          {annotationHits.map((h, i) => (
            <SearchHitItem key={`a-${h.run_id}:${h.trajectory_id}:${i}`} hit={h} />
          ))}
        </Section>
      )}

      {result.hits.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">No hits for that query.</p>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold font-medium text-muted-foreground">
        {title} ({count})
      </h2>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  );
}
