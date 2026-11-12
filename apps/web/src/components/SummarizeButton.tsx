"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { API_URL } from "@/lib/api";
import { postSummarize } from "@/lib/client";
import { cn } from "@/lib/cn";

interface StatusResponse {
  heuristic_available: boolean;
  ai_available: boolean;
}

export function SummarizeButton({
  runId,
  trajectoryId,
}: {
  runId: string;
  trajectoryId: string;
}) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<null | "heuristic" | "ai">(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/summary/status`)
      .then((r) => r.json() as Promise<StatusResponse>)
      .then((s) => setAiAvailable(s.ai_available))
      .catch(() => setAiAvailable(false));
  }, []);

  async function run(provider: "heuristic" | "ai") {
    setBusy(provider);
    setError(null);
    setOpen(false);
    try {
      await postSummarize(runId, trajectoryId, provider, true);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to summarize");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={busy != null}
        className={cn(
          "rounded-xl border border-border/70 px-2.5 py-1 text-xs",
          "hover:bg-accent",
          busy != null && "opacity-60",
        )}
        title="Generate an AI-assisted summary"
      >
        {busy ? `Summarizing (${busy})…` : "Summarize ▾"}
      </button>
      {error && (
        <span className="absolute -bottom-7 right-0 max-w-xs truncate rounded-md border border-[hsl(var(--danger))]/40 bg-card px-2 py-1 text-[10px] text-[hsl(var(--danger))]">
          {error}
        </span>
      )}
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-60 rounded-xl border border-border/70 bg-card p-2 shadow-lg">
          <button
            type="button"
            onClick={() => run("heuristic")}
            className="block w-full rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent"
          >
            <div className="font-medium">Heuristic</div>
            <div className="text-muted-foreground">
              Deterministic summary from step actions + final patch. No API key needed.
            </div>
          </button>
          <button
            type="button"
            onClick={() => run("ai")}
            disabled={!aiAvailable}
            className={cn(
              "mt-1 block w-full rounded-md px-2 py-1.5 text-left text-xs",
              aiAvailable ? "hover:bg-accent" : "opacity-50",
            )}
          >
            <div className="font-medium">AI (Claude)</div>
            <div className="text-muted-foreground">
              {aiAvailable
                ? "Anthropic-backed summary based on the full trajectory."
                : "Disabled — set ANTHROPIC_API_KEY on the API to enable."}
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
