import type { MetadataRoute } from "next";

import { listRuns, listShowcase } from "@/lib/api";
import { INTEGRATIONS } from "@/lib/integrations";

const SITE_URL = process.env.SITE_URL ?? "http://localhost:3000";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "hourly", priority: 1.0 },
    { url: `${SITE_URL}/live`, changeFrequency: "always", priority: 0.7 },
    { url: `${SITE_URL}/compare`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/compare/runs`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${SITE_URL}/bookmarks`, changeFrequency: "daily", priority: 0.5 },
    { url: `${SITE_URL}/search`, changeFrequency: "weekly", priority: 0.5 },
    { url: `${SITE_URL}/showcase`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/integrations`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/datasets`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/webhooks`, changeFrequency: "weekly", priority: 0.4 },
  ];

  const integrationRoutes: MetadataRoute.Sitemap = INTEGRATIONS.map((i) => ({
    url: `${SITE_URL}/integrations/${i.slug}`,
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  let runRoutes: MetadataRoute.Sitemap = [];
  let showcaseRoutes: MetadataRoute.Sitemap = [];
  try {
    const [runs, showcase] = await Promise.all([listRuns(), listShowcase()]);
    runRoutes = runs.flatMap((r) => [
      {
        url: `${SITE_URL}/runs/${encodeURIComponent(r.id)}`,
        changeFrequency: "daily" as const,
        priority: 0.8,
      },
      {
        url: `${SITE_URL}/runs/${encodeURIComponent(r.id)}/analytics`,
        changeFrequency: "daily" as const,
        priority: 0.7,
      },
      {
        url: `${SITE_URL}/runs/${encodeURIComponent(r.id)}/insights`,
        changeFrequency: "daily" as const,
        priority: 0.7,
      },
    ]);
    showcaseRoutes = showcase.map((e) => ({
      url: `${SITE_URL}/showcase/${encodeURIComponent(e.slug)}`,
      changeFrequency: "weekly" as const,
      priority: 0.9,
      lastModified: new Date(e.updated_at * 1000),
    }));
  } catch {
    // API down — return static + integrations only.
  }

  return [...staticRoutes, ...integrationRoutes, ...runRoutes, ...showcaseRoutes];
}
