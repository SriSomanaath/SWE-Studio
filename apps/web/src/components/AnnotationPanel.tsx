"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { getAuthor } from "@/lib/author";
import { deleteAnnotation, postAnnotation } from "@/lib/client";
import { cn } from "@/lib/cn";
import type { Annotation } from "@/lib/types";

function formatTime(t: number): string {
  return new Date(t * 1000).toLocaleString();
}

export function AnnotationPanel({
  runId,
  trajectoryId,
  stepIndex,
  annotations,
  compact = false,
}: {
  runId: string;
  trajectoryId: string;
  stepIndex: number;
  annotations: Annotation[];
  compact?: boolean;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [me, setMe] = useState("anonymous");
  const [, startTransition] = useTransition();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setMe(getAuthor()), []);

  async function submit() {
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await postAnnotation(runId, trajectoryId, stepIndex, draft);
      setDraft("");
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setError(null);
    try {
      await deleteAnnotation(id);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-3",
        !compact && "surface-soft p-4",
      )}
    >
      {!compact && (
        <h3 className="text-xs font-semibold font-medium text-muted-foreground">
          {stepIndex === -1 ? "Notes on this trajectory" : `Notes on step ${stepIndex + 1}`}
        </h3>
      )}

      {annotations.length > 0 && (
        <ul className="flex flex-col gap-2">
          {annotations.map((a) => (
            <li
              key={a.id}
              className="rounded-xl border border-border/70 bg-background p-2.5"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-xs">@{a.author}</span>
                <span className="text-[10px] text-muted-foreground">
                  {formatTime(a.created_at)}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{a.body}</p>
              {a.author === me && (
                <button
                  type="button"
                  onClick={() => remove(a.id)}
                  disabled={busy}
                  className="mt-1 text-[10px] font-medium text-muted-foreground hover:text-[hsl(var(--danger))]"
                >
                  delete
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={
            stepIndex === -1 ? "Add a note about this trajectory…" : "Add a note about this step…"
          }
          className="min-h-[60px] resize-y rounded-xl border border-border/70 bg-background px-2.5 py-1.5 text-sm outline-none focus:border-foreground/40"
          rows={2}
          disabled={busy}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-medium text-muted-foreground">
            as @{me}
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={busy || !draft.trim()}
            className={cn(
              "rounded-xl border border-border/70 px-2.5 py-1 text-xs",
              draft.trim() && !busy
                ? "bg-foreground text-background hover:opacity-90"
                : "opacity-50",
            )}
          >
            {busy ? "Posting…" : "Post note"}
          </button>
        </div>
        {error && <p className="text-xs text-[hsl(var(--danger))]">{error}</p>}
      </div>
    </div>
  );
}
