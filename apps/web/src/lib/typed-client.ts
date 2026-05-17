/**
 * Typed Studio API client.
 *
 * Built on top of `openapi-fetch` with types pulled from
 * `openapi-types.ts`, which is regenerated from the live FastAPI
 * `/openapi.json` via `pnpm gen:openapi`. Server-side schema changes propagate
 * to the web client at type-check time.
 *
 * Migration plan:
 *   1. `lib/api.ts` still ships hand-written Zod schemas and is the historical
 *      surface every page imports from. It remains the source of truth for
 *      runtime validation.
 *   2. New endpoints should be added here first. Pages that need only static
 *      typing (no runtime parse) can use this client directly.
 *   3. Over time, fold the existing Zod schemas into thin wrappers around the
 *      generated types so the two layers stay in sync.
 */

import createClient from "openapi-fetch";

import type { paths } from "./openapi-types";

const DEFAULT_BASE =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export function createStudioApi(
  baseUrl: string = DEFAULT_BASE,
  init?: { apiKey?: string; author?: string },
) {
  const headers: Record<string, string> = {};
  if (init?.apiKey) headers["X-API-Key"] = init.apiKey;
  if (init?.author) headers["X-Author"] = init.author;
  return createClient<paths>({ baseUrl, headers });
}

/** Default singleton client. Reads env at module-load time. */
export const studioApi = createStudioApi();

// --- Demonstrative typed endpoints -----------------------------------------
//
// These functions exist so the rest of the code can `import` something
// concrete and pages have a worked example of how to consume the typed client.
// They mirror two Phase 8 + Phase 11 reads that are not validated at runtime
// in `lib/api.ts`.

export async function getHealth() {
  const { data, error } = await studioApi.GET("/health");
  if (error || !data) throw new Error(`GET /health failed`);
  return data;
}

export async function getEmbeddingsStatus() {
  const { data, error } = await studioApi.GET("/embeddings/status");
  if (error || !data) throw new Error(`GET /embeddings/status failed`);
  return data;
}
