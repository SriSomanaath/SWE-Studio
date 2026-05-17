import { z } from "zod";

import {
  Annotation,
  Bookmark,
  CompareResult,
  DatasetManifest,
  LiveTrajectory,
  RunAnalytics,
  RunCompareResult,
  RunInsights,
  RunStats,
  RunSummary,
  ResolvedShare,
  Share,
  Webhook,
  WebhookDelivery,
  SearchResult,
  ShowcaseEntry,
  SimilarHit,
  TrajectoryDetail,
  TrajectoryFilters,
  TrajectorySummary,
  annotationSchema,
  bookmarkSchema,
  compareResultSchema,
  datasetManifestSchema,
  liveTrajectorySchema,
  runAnalyticsSchema,
  runCompareResultSchema,
  runInsightsSchema,
  runStatsSchema,
  runSummarySchema,
  searchResultSchema,
  resolvedShareSchema,
  shareSchema,
  showcaseEntrySchema,
  similarHitSchema,
  trajectoryDetailSchema,
  trajectorySummarySchema,
  webhookDeliverySchema,
  webhookSchema,
} from "./types";

export const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

async function request<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
): Promise<z.output<S>> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  return schema.parse(await res.json()) as z.output<S>;
}

async function requestWithCount<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
): Promise<{ data: z.output<S>; total: number }> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  const data = schema.parse(await res.json()) as z.output<S>;
  const total = Number(res.headers.get("X-Total-Count") ?? "0");
  return { data, total };
}

// --- Migrated to the typed OpenAPI client (Phase 13) ---
//
// The next three functions used to hand-write Zod schemas. They now ask the
// generated `studioApi` directly; the response shape is guaranteed by build-
// time TypeScript types from `openapi-types.ts`. Migration recipe:
//   1. Identify a read endpoint with a stable response.
//   2. Replace the `request(path, zodSchema)` call with a `studioApi.GET()` call.
//   3. Throw on `error` from openapi-fetch; otherwise return `data`.
// Endpoints that need runtime validation (e.g., untrusted ingest) stay on Zod.

import { studioApi } from "./typed-client";

export async function listRuns(): Promise<RunSummary[]> {
  const { data, error } = await studioApi.GET("/runs");
  if (error || !data) throw new Error(`GET /runs failed`);
  return data as RunSummary[];
}

export interface ListTrajectoriesArgs extends Partial<TrajectoryFilters> {
  limit?: number;
  offset?: number;
}

export function listTrajectories(
  runId: string,
  args: ListTrajectoriesArgs = {},
): Promise<{ data: TrajectorySummary[]; total: number }> {
  const params = new URLSearchParams();
  if (args.status && args.status !== "any") params.set("status", args.status);
  if (args.exit) params.set("exit", args.exit);
  if (args.search) params.set("search", args.search);
  if (args.costMin) params.set("cost_min", args.costMin);
  if (args.costMax) params.set("cost_max", args.costMax);
  if (args.sort) params.set("sort", args.sort);
  if (args.order) params.set("order", args.order);
  if (args.limit) params.set("limit", String(args.limit));
  if (args.offset) params.set("offset", String(args.offset));

  const qs = params.toString();
  return requestWithCount(
    `/runs/${encodeURIComponent(runId)}/trajectories${qs ? `?${qs}` : ""}`,
    z.array(trajectorySummarySchema),
  );
}

export function getRunStats(runId: string): Promise<RunStats> {
  return request(`/runs/${encodeURIComponent(runId)}/stats`, runStatsSchema);
}

export function getRunAnalytics(runId: string): Promise<RunAnalytics> {
  return request(
    `/runs/${encodeURIComponent(runId)}/analytics`,
    runAnalyticsSchema,
  );
}

export function compareRuns(a: string, b: string): Promise<RunCompareResult> {
  return request(
    `/runs/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    runCompareResultSchema,
  );
}

export function listLive(sinceSeconds = 60, limit = 50): Promise<LiveTrajectory[]> {
  return request(
    `/live?since=${sinceSeconds}&limit=${limit}`,
    z.array(liveTrajectorySchema),
  );
}

export function getCompare(a: string, b: string): Promise<CompareResult> {
  return request(
    `/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    compareResultSchema,
  );
}

export function listAnnotations(
  runId: string,
  trajectoryId: string,
): Promise<Annotation[]> {
  return request(
    `/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/annotations`,
    z.array(annotationSchema),
  );
}

export function listBookmarks(author?: string): Promise<Bookmark[]> {
  const qs = author ? `?author=${encodeURIComponent(author)}` : "";
  return request(`/bookmarks${qs}`, z.array(bookmarkSchema));
}

export interface SearchArgs {
  q: string;
  runId?: string;
  kind?: "all" | "trajectory" | "annotation";
  limit?: number;
}

export function getRunInsights(runId: string): Promise<RunInsights> {
  return request(`/runs/${encodeURIComponent(runId)}/insights`, runInsightsSchema);
}

export function findSimilar(
  runId: string,
  trajectoryId: string,
  limit = 10,
): Promise<SimilarHit[]> {
  return request(
    `/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/similar?limit=${limit}`,
    z.array(similarHitSchema),
  );
}

export function getRunManifest(runId: string): Promise<DatasetManifest> {
  return request(`/runs/${encodeURIComponent(runId)}/manifest.json`, datasetManifestSchema);
}

export function jsonlExportUrl(runId: string): string {
  return `${API_URL}/runs/${encodeURIComponent(runId)}/export.jsonl`;
}

export function manifestUrl(runId: string): string {
  return `${API_URL}/runs/${encodeURIComponent(runId)}/manifest.json`;
}

export function resolveShare(token: string): Promise<ResolvedShare> {
  return request(`/shares/${encodeURIComponent(token)}/resolve`, resolvedShareSchema);
}

export async function listShares(): Promise<Share[]> {
  const { data, error } = await studioApi.GET("/shares");
  if (error || !data) throw new Error(`GET /shares failed`);
  return data as Share[];
}

export async function listWebhooks(): Promise<Webhook[]> {
  const { data, error } = await studioApi.GET("/webhooks");
  if (error || !data) throw new Error(`GET /webhooks failed`);
  return data as Webhook[];
}

export function listWebhookDeliveries(
  webhookId: number,
  limit = 50,
): Promise<WebhookDelivery[]> {
  return request(
    `/webhooks/${webhookId}/deliveries?limit=${limit}`,
    z.array(webhookDeliverySchema),
  );
}

export function listShowcase(): Promise<ShowcaseEntry[]> {
  return request("/showcase", z.array(showcaseEntrySchema));
}

export function getShowcase(slug: string): Promise<ShowcaseEntry> {
  return request(`/showcase/${encodeURIComponent(slug)}`, showcaseEntrySchema);
}

export function searchTrajectories(args: SearchArgs): Promise<SearchResult> {
  const params = new URLSearchParams({ q: args.q });
  if (args.runId) params.set("run_id", args.runId);
  if (args.kind && args.kind !== "all") params.set("kind", args.kind);
  if (args.limit) params.set("limit", String(args.limit));
  return request(`/search?${params.toString()}`, searchResultSchema);
}

export function trajectoryEventsUrl(runId: string, trajectoryId: string): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? process.env.API_URL ?? "http://localhost:8080";
  return `${base}/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/events`;
}

export function getTrajectory(runId: string, trajectoryId: string): Promise<TrajectoryDetail> {
  return request(
    `/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}`,
    trajectoryDetailSchema,
  );
}
