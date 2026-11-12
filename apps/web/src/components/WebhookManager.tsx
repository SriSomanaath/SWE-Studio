"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { createWebhook, deleteWebhook, setWebhookActive } from "@/lib/client";
import { cn } from "@/lib/cn";
import type { Webhook } from "@/lib/types";

const EVENT_OPTIONS = [
  "trajectory.completed",
  "trajectory.resolved",
  "trajectory.updated",
  "summary.generated",
  "bookmark.created",
  "showcase.created",
];

export function WebhookManager({ initial }: { initial: Webhook[] }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleEvent(name: string) {
    setEvents((es) =>
      es.includes(name) ? es.filter((e) => e !== name) : [...es, name],
    );
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await createWebhook({
        url: url.trim(),
        events,
        description: description.trim() || null,
      });
      setUrl("");
      setDescription("");
      setEvents([]);
      setOpen(false);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create webhook");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm(`Delete webhook #${id}?`)) return;
    try {
      await deleteWebhook(id);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete webhook");
    }
  }

  async function toggleActive(w: Webhook) {
    try {
      await setWebhookActive(w.id, !w.active);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update webhook");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {initial.length} subscription{initial.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="rounded-xl border border-border/70 bg-foreground px-3 py-1.5 text-xs text-background hover:opacity-90"
        >
          {open ? "Cancel" : "+ Add webhook"}
        </button>
      </div>

      {open && (
        <div className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-card p-4">
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-muted-foreground">URL</span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
              className="rounded-xl border border-border/70 bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-muted-foreground">Description</span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Alert #eng-agents on resolved trajectories"
              className="rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-xs outline-none focus:border-foreground/40"
            />
          </label>
          <fieldset className="flex flex-col gap-1 text-xs">
            <legend className="font-medium text-muted-foreground">
              Events (none = all)
            </legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {EVENT_OPTIONS.map((opt) => (
                <label
                  key={opt}
                  className={cn(
                    "flex cursor-pointer items-center gap-1.5 rounded-xl border border-border/70 px-2 py-1 font-mono text-[10px]",
                    events.includes(opt) && "border-foreground/30 bg-accent",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={events.includes(opt)}
                    onChange={() => toggleEvent(opt)}
                    className="accent-foreground"
                  />
                  {opt}
                </label>
              ))}
            </div>
          </fieldset>
          {error && <p className="text-xs text-[hsl(var(--danger))]">{error}</p>}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={submit}
              disabled={busy || !url.trim()}
              className={cn(
                "rounded-xl border border-border/70 px-3 py-1.5 text-xs",
                url.trim() && !busy
                  ? "bg-foreground text-background hover:opacity-90"
                  : "opacity-50",
              )}
            >
              {busy ? "Creating…" : "Create webhook"}
            </button>
          </div>
        </div>
      )}

      {initial.length > 0 && (
        <ul className="flex flex-col gap-2">
          {initial.map((w) => (
            <li
              key={w.id}
              className="rounded-xl border border-border/70 bg-card p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="font-mono text-xs">
                  #{w.id} ·{" "}
                  <span className={cn(w.active ? "text-foreground" : "text-muted-foreground")}>
                    {w.url}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => toggleActive(w)}
                    className="rounded-xl border border-border/70 px-2 py-1 hover:bg-accent"
                  >
                    {w.active ? "Pause" : "Resume"}
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(w.id)}
                    className="rounded-xl border border-border/70 px-2 py-1 text-[hsl(var(--danger))] hover:bg-[hsl(var(--danger))]/10"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
                <span
                  className={cn(
                    "rounded-md px-1.5 py-0.5 font-medium font-medium",
                    w.active
                      ? "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))]"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {w.active ? "active" : "paused"}
                </span>
                {w.events.length === 0 ? (
                  <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono">all events</span>
                ) : (
                  w.events.map((e) => (
                    <span key={e} className="rounded-md bg-muted px-1.5 py-0.5 font-mono">
                      {e}
                    </span>
                  ))
                )}
              </div>
              {w.description && (
                <p className="mt-1 text-xs text-muted-foreground">{w.description}</p>
              )}
              <details className="mt-2 text-[10px]">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  Signing secret
                </summary>
                <code className="mt-1 block break-all rounded bg-muted/40 p-2 font-mono">
                  {w.secret}
                </code>
                <p className="mt-1 text-muted-foreground">
                  Verify deliveries with HMAC-SHA256:{" "}
                  <code>X-Studio-Signature: sha256=&lt;hex(hmac(secret, body))&gt;</code>
                </p>
              </details>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
