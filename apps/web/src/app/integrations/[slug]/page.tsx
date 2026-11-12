import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, CardBody } from "@/components/Card";
import { INTEGRATIONS, getIntegration } from "@/lib/integrations";
import { ogImage } from "@/lib/og";

export function generateStaticParams() {
  return INTEGRATIONS.map((i) => ({ slug: i.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const integration = getIntegration(slug);
  if (!integration) return { title: "Integration not found" };

  const ogUrl = ogImage({
    title: `${integration.name} → SWE Studio`,
    subtitle: integration.tagline,
    kind: "integration",
  });

  return {
    title: `${integration.name} observability — push trajectories to SWE Studio`,
    description: integration.description,
    keywords: integration.keywords,
    alternates: { canonical: `/integrations/${slug}` },
    openGraph: {
      title: `${integration.name} → SWE Studio`,
      description: integration.description,
      images: [{ url: ogUrl, width: 1200, height: 630 }],
      type: "article",
    },
    twitter: { card: "summary_large_image", images: [ogUrl] },
  };
}

export default async function IntegrationPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const integration = getIntegration(slug);
  if (!integration) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/integrations" className="text-xs text-muted-foreground hover:text-foreground">
          ← Integrations
        </Link>
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-2xl font-semibold">{integration.name}</h1>
          <a
            href={integration.upstream}
            target={integration.upstream.startsWith("http") ? "_blank" : undefined}
            rel="noreferrer"
            className="text-xs font-mono text-muted-foreground hover:text-foreground"
          >
            {integration.upstream.startsWith("http") ? integration.upstream + " ↗" : integration.upstream}
          </a>
        </div>
        <p className="text-sm text-muted-foreground">{integration.tagline}</p>
      </div>

      <Card>
        <CardBody>
          <p className="text-sm leading-relaxed">{integration.description}</p>
        </CardBody>
      </Card>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold font-medium text-muted-foreground">
          Integrate in 30 seconds
        </h2>
        <pre className="overflow-auto rounded-2xl border border-border/70 bg-muted/30 p-4 font-mono text-xs leading-relaxed">
          <code>{integration.snippet}</code>
        </pre>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold font-medium text-muted-foreground">
          What you get in Studio
        </h2>
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {integration.features.map((f) => (
            <li
              key={f}
              className="flex items-start gap-2 rounded-xl border border-border/70 bg-card p-3 text-sm"
            >
              <span className="mt-1 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[hsl(var(--success))]" />
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/live"
          className="rounded-xl border border-border/70 px-3 py-1.5 hover:bg-accent"
        >
          See live mode →
        </Link>
        <Link
          href="/runs"
          className="rounded-xl border border-border/70 px-3 py-1.5 hover:bg-accent"
        >
          Browse runs →
        </Link>
      </div>
    </div>
  );
}
