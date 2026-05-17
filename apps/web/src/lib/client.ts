"use client";

import { API_URL } from "./api";
import { getAuthor } from "./author";
import { studioIdentityHeaders } from "./session-headers";

async function mutate(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
): Promise<Response> {
  const headers: Record<string, string> = {
    "X-Author": getAuthor(),
    ...(await studioIdentityHeaders()),
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${method} ${path}: ${res.status} ${text}`);
  }
  return res;
}

export async function postAnnotation(
  runId: string,
  trajectoryId: string,
  stepIndex: number,
  body: string,
): Promise<void> {
  await mutate(
    "POST",
    `/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/annotations`,
    { step_index: stepIndex, body },
  );
}

export async function deleteAnnotation(annotationId: number): Promise<void> {
  await mutate("DELETE", `/annotations/${annotationId}`);
}

export async function putBookmark(
  runId: string,
  trajectoryId: string,
  note?: string,
): Promise<void> {
  await mutate(
    "PUT",
    `/bookmarks/${encodeURIComponent(runId)}/${encodeURIComponent(trajectoryId)}`,
    { note: note ?? null },
  );
}

export async function removeBookmark(runId: string, trajectoryId: string): Promise<void> {
  await mutate(
    "DELETE",
    `/bookmarks/${encodeURIComponent(runId)}/${encodeURIComponent(trajectoryId)}`,
  );
}

export async function postSummarize(
  runId: string,
  trajectoryId: string,
  provider: "heuristic" | "ai",
  force = false,
): Promise<void> {
  const qs = `?provider=${provider}${force ? "&force=true" : ""}`;
  await mutate(
    "POST",
    `/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/summarize${qs}`,
  );
}

export async function createShare(args: {
  kind: "run" | "trajectory" | "showcase";
  runId?: string;
  trajectoryId?: string;
  slug?: string;
  description?: string | null;
  ttlSeconds?: number | null;
}): Promise<{ token: string; url: string }> {
  const res = await mutate("POST", "/shares", {
    kind: args.kind,
    run_id: args.runId,
    trajectory_id: args.trajectoryId,
    slug: args.slug,
    description: args.description ?? null,
    ttl_seconds: args.ttlSeconds ?? null,
  });
  const body = (await res.json()) as { token: string; url: string };
  return body;
}

export async function revokeShare(token: string): Promise<void> {
  await mutate("DELETE", `/shares/${encodeURIComponent(token)}`);
}

export async function createWebhook(args: {
  url: string;
  events: string[];
  description?: string | null;
}): Promise<void> {
  await mutate("POST", "/webhooks", args);
}

export async function deleteWebhook(id: number): Promise<void> {
  await mutate("DELETE", `/webhooks/${id}`);
}

export async function setWebhookActive(id: number, active: boolean): Promise<void> {
  await mutate("PATCH", `/webhooks/${id}`, { active });
}
