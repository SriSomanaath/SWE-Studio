import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader } from "@/components/Card";
import { INTEGRATIONS } from "@/lib/integrations";
import { ogImage } from "@/lib/og";

const ogUrl = ogImage({
  title: "Integrations",
  subtitle: "Push trajectories from any coding agent",
  kind: "integration",
});

export const metadata: Metadata = {
  title: "Integrations · SWE Studio",
  description:
    "Observability and replay for coding agents — Aider, OpenHands, Cline, or any custom agent via the Python SDK.",
  alternates: { canonical: "/integrations" },
  openGraph: {
    title: "Integrations · SWE Studio",
    description: "Observability and replay for coding agents.",
    images: [{ url: ogUrl, width: 1200, height: 630 }],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: [ogUrl] },
};

export default function IntegrationsHub() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-sm text-muted-foreground">
          SWE Studio reads agent trajectories natively and accepts trajectories from any agent via the{" "}
          <Link className="underline hover:text-foreground" href="/integrations/custom">
            Python SDK
          </Link>
          .
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {INTEGRATIONS.map((i) => (
          <Link key={i.slug} href={`/integrations/${i.slug}`}>
            <Card className="h-full transition-colors hover:border-foreground/30">
              <CardHeader>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="text-base font-semibold">{i.name}</h2>
                  <span
                    className={
                      i.status === "first-class"
                        ? "rounded bg-[hsl(var(--success))]/15 px-1.5 py-0.5 text-[10px] font-medium font-medium text-[hsl(var(--success))]"
                        : i.status === "community"
                          ? "rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium font-medium text-muted-foreground"
                          : "rounded bg-[hsl(var(--warning))]/15 px-1.5 py-0.5 text-[10px] font-medium font-medium text-[hsl(var(--warning))]"
                    }
                  >
                    {i.status}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{i.tagline}</p>
              </CardHeader>
              <CardBody>
                <p className="text-sm leading-relaxed text-muted-foreground">{i.description}</p>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
