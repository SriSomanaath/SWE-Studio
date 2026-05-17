import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { jsonlExportUrl, listRuns, manifestUrl } from "@/lib/api";
import { formatCost, formatCount } from "@/lib/format";
import { ogImage } from "@/lib/og";

export const dynamic = "force-dynamic";

const ogUrl = ogImage({
  title: "Datasets",
  subtitle: "Export Studio runs as HuggingFace-ready JSONL",
  kind: "showcase",
});

export const metadata: Metadata = {
  title: "Datasets · SWE Studio",
  description:
    "Download SWE Studio runs as line-delimited JSON for HuggingFace Datasets, ML training, or external analysis.",
  alternates: { canonical: "/datasets" },
  openGraph: {
    title: "Datasets · SWE Studio",
    description: "Export SWE Studio runs as HuggingFace-compatible JSONL.",
    images: [{ url: ogUrl, width: 1200, height: 630 }],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: [ogUrl] },
};

export default async function DatasetsPage() {
  let runs: Awaited<ReturnType<typeof listRuns>> = [];
  try {
    runs = await listRuns();
  } catch {
    runs = [];
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Datasets</h1>
        <p className="text-sm text-muted-foreground">
          Every run is exportable as a HuggingFace-compatible dataset. Use the JSONL endpoint for
          quick ML pipelines, or run the bundled <code className="font-mono">dataset_card</code>{" "}
          CLI to produce a complete HF Hub upload directory.
        </p>
      </div>

      {runs.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">No runs to export yet.</p>
          </CardBody>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {runs.map((r) => (
            <Card key={r.id}>
              <CardHeader>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="font-mono text-sm font-semibold">{r.id}</h2>
                  <span className="text-xs text-muted-foreground">
                    {r.trajectory_count} trajector{r.trajectory_count === 1 ? "y" : "ies"}
                  </span>
                </div>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Stat label="Trajectories" value={formatCount(r.trajectory_count)} />
                  <Stat label="Resolved" value={formatCount(r.resolved_count)} />
                  <Stat
                    label="Pass rate"
                    value={
                      r.resolved_count != null && r.trajectory_count > 0
                        ? `${Math.round((r.resolved_count / r.trajectory_count) * 100)}%`
                        : "—"
                    }
                  />
                  <Stat label="Has results" value={r.has_results ? "yes" : "no"} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <a
                    href={jsonlExportUrl(r.id)}
                    download
                    className="rounded-md border border-border bg-foreground px-3 py-1.5 text-background hover:opacity-90"
                  >
                    Download .jsonl
                  </a>
                  <a
                    href={manifestUrl(r.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md border border-border px-3 py-1.5 hover:bg-accent"
                  >
                    View manifest
                  </a>
                  <Link
                    href={`/runs/${r.id}/insights`}
                    className="rounded-md border border-border px-3 py-1.5 hover:bg-accent"
                  >
                    Insights →
                  </Link>
                </div>
                <details className="mt-4 text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Push this run to the HuggingFace Hub
                  </summary>
                  <pre className="mt-2 overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono">
{`# From apps/api, with the venv activated:
python -m app.tools.dataset_card \\
  --run ${r.id} \\
  --output ./hf-card-${r.id} \\
  --pretty-name "Coding-agent trajectories — ${r.id}"

cd ./hf-card-${r.id}
huggingface-cli upload <your-username>/<dataset-name> . .`}
                  </pre>
                </details>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
