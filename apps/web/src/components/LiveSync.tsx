"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { trajectoryEventsUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useEventStream } from "@/lib/sse";

interface TrajEvent {
  type: string;
  step_count?: number;
  exit_status?: string | null;
  step_count_delta?: number;
}

/**
 * Subscribes to the trajectory's SSE channel. On each event it triggers a
 * router.refresh() so the Server Component re-fetches the trajectory detail
 * with the new step list, then renders a pulse indicator with the latest
 * step count.
 */
export function LiveSync({
  runId,
  trajectoryId,
  initialStepCount,
  exitStatus,
}: {
  runId: string;
  trajectoryId: string;
  initialStepCount: number;
  exitStatus: string | null;
}) {
  const router = useRouter();
  const [stepCount, setStepCount] = useState(initialStepCount);
  const [pulse, setPulse] = useState(false);

  // Once the run finishes, stop subscribing.
  const isTerminal = exitStatus != null && exitStatus !== "running";
  const url = isTerminal
    ? null
    : trajectoryEventsUrl(runId, trajectoryId);

  const { state } = useEventStream<TrajEvent>(url, (e) => {
    if (typeof e.step_count === "number") setStepCount(e.step_count);
    setPulse(true);
    window.setTimeout(() => setPulse(false), 600);
    router.refresh();
  });

  if (isTerminal) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1 text-xs",
        state === "open" && "border-[hsl(var(--success))]/40",
        state === "error" && "border-[hsl(var(--danger))]/40",
      )}
      aria-live="polite"
    >
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full transition-all",
          state === "open" && "bg-[hsl(var(--success))]",
          state === "error" && "bg-[hsl(var(--danger))]",
          state === "connecting" && "bg-[hsl(var(--warning))] animate-pulse",
          state === "closed" && "bg-muted-foreground",
          state === "idle" && "bg-muted-foreground",
          pulse && state === "open" && "ring-4 ring-[hsl(var(--success))]/30",
        )}
      />
      <span className="font-mono tabular-nums">
        live · step {stepCount}
      </span>
    </span>
  );
}
