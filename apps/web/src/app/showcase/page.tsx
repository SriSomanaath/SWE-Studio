import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader } from "@/components/Card";
import { listShowcase } from "@/lib/api";
import { ogImage } from "@/lib/og";

export const dynamic = "force-dynamic";

const ogUrl = ogImage({
  title: "Showcase",
  subtitle: "Curated trajectories worth a second look",
  kind: "showcase",
});

export const metadata: Metadata = {
  title: "Showcase · SWE Studio",
  description:
    "Curated coding-agent trajectories — patches that landed, instructive failures, surprising paths through hard problems.",
  alternates: { canonical: "/showcase" },
  openGraph: {
    title: "Showcase · SWE Studio",
    description: "Curated coding-agent trajectories.",
    images: [{ url: ogUrl, width: 1200, height: 630 }],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: [ogUrl] },
};

function formatTime(t: number): string {
  return new Date(t * 1000).toLocaleDateString();
}

export default async function ShowcaseHub() {
  let entries: Awaited<ReturnType<typeof listShowcase>> = [];
  try {
    entries = await listShowcase();
  } catch {
    entries = [];
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Showcase</h1>
        <p className="text-sm text-muted-foreground">
          Curated trajectories with shareable vanity URLs. Add new ones with{" "}
          <code className="font-mono text-foreground">python -m app.tools.curate add</code>.
        </p>
      </div>

      {entries.length === 0 ? (
        <Card>
          <CardBody>
            <p className="text-sm text-muted-foreground">
              No showcase entries yet. From <code className="font-mono">apps/api</code>:
            </p>
            <pre className="mt-3 overflow-auto rounded-xl border border-border/70 bg-muted/40 p-3 font-mono text-xs">
{`python -m app.tools.curate add \\
  --slug django-boolean-fix \\
  --run sample-run-001 \\
  --traj django__django-12345 \\
  --title "BooleanField accepts integer 0 and 1" \\
  --step 3`}
            </pre>
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {entries.map((e) => (
            <Link key={e.slug} href={`/showcase/${e.slug}`}>
              <Card className="h-full transition-colors hover:border-foreground/30">
                <CardHeader>
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-base font-semibold leading-tight">{e.title}</h2>
                    <span className="text-[10px] text-muted-foreground">{formatTime(e.created_at)}</span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">
                    {e.run_id} · {e.trajectory_id}
                    {e.pinned_step != null && <> · step {e.pinned_step + 1}</>}
                  </p>
                </CardHeader>
                {e.description && (
                  <CardBody>
                    <p className="text-sm text-muted-foreground">{e.description}</p>
                  </CardBody>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
