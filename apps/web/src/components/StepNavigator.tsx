"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AnnotationPanel } from "@/components/AnnotationPanel";
import { cn } from "@/lib/cn";
import { truncate } from "@/lib/format";
import type { Annotation, TrajectoryStep } from "@/lib/types";

import { ReplayPlayer } from "./ReplayPlayer";
import { StepView } from "./StepView";

const SPEEDS = [0.5, 1, 2, 4] as const;
type Speed = (typeof SPEEDS)[number];

function parseSpeed(raw: string | null): Speed {
  const n = Number(raw);
  return SPEEDS.includes(n as Speed) ? (n as Speed) : 1;
}

export function StepNavigator({
  runId,
  trajectoryId,
  steps,
  problemStatement,
  submission,
  annotations,
}: {
  runId: string;
  trajectoryId: string;
  steps: TrajectoryStep[];
  problemStatement: string | null | undefined;
  submission: string | null | undefined;
  annotations: Annotation[];
}) {
  const router = useRouter();
  const params = useSearchParams();

  const stepFromUrl = useMemo(() => {
    const raw = params.get("step");
    if (!raw) return 0;
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 0 || n >= steps.length) return 0;
    return n;
  }, [params, steps.length]);

  const [selected, setSelected] = useState(stepFromUrl);
  const [copied, setCopied] = useState(false);
  const [playing, setPlaying] = useState(params.get("play") === "1");
  const [speed, setSpeed] = useState<Speed>(parseSpeed(params.get("speed")));

  // Stay in sync when URL changes externally (back/forward).
  useEffect(() => setSelected(stepFromUrl), [stepFromUrl]);

  function writeUrl(next: { step?: number; play?: boolean; speed?: Speed }) {
    const sp = new URLSearchParams(params.toString());
    if (next.step !== undefined) sp.set("step", String(next.step));
    if (next.play !== undefined) {
      if (next.play) sp.set("play", "1");
      else sp.delete("play");
    }
    if (next.speed !== undefined) {
      if (next.speed !== 1) sp.set("speed", String(next.speed));
      else sp.delete("speed");
    }
    router.replace(`?${sp.toString()}`, { scroll: false });
  }

  function selectStep(i: number) {
    setSelected(i);
    writeUrl({ step: i });
  }

  function handleSetPlaying(b: boolean) {
    setPlaying(b);
    writeUrl({ play: b });
  }

  function handleSetSpeed(s: Speed) {
    setSpeed(s);
    writeUrl({ speed: s });
  }

  async function copyPermalink() {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${window.location.pathname}?step=${selected}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  }

  const items = useMemo(
    () =>
      steps.map((step, i) => ({
        index: i,
        label: step.action ? truncate(step.action.split("\n")[0], 60) : `Step ${i + 1}`,
        hasNotes: annotations.some((a) => a.step_index === i),
      })),
    [steps, annotations],
  );

  if (steps.length === 0) {
    return (
      <div className="rounded-md border border-border p-6 text-center text-sm text-muted-foreground">
        This trajectory has no steps.
      </div>
    );
  }

  const current = steps[selected];
  const stepAnnotations = annotations.filter((a) => a.step_index === selected);

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[260px_1fr]">
      <aside className="flex max-h-[80vh] flex-col gap-1 overflow-y-auto rounded-md border border-border bg-card p-2 text-sm">
        {items.map((item) => (
          <SidebarLink
            key={item.index}
            active={item.index === selected}
            onClick={() => selectStep(item.index)}
          >
            <div className="flex items-center gap-2">
              <span className="w-6 text-xs text-muted-foreground tabular-nums">
                {item.index + 1}
              </span>
              <span className="flex-1 truncate font-mono text-xs">{item.label}</span>
              {item.hasNotes && (
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-[hsl(var(--warning))]"
                  title="Has notes"
                />
              )}
            </div>
          </SidebarLink>
        ))}
      </aside>

      <section className="flex min-w-0 flex-col gap-6">
        {problemStatement && selected === 0 && (
          <div className="rounded-md border border-border bg-muted/30 p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Problem statement
            </h3>
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {problemStatement}
            </pre>
          </div>
        )}

        <ReplayPlayer
          totalSteps={steps.length}
          selected={selected}
          setSelected={selectStep}
          playing={playing}
          setPlaying={handleSetPlaying}
          speed={speed}
          setSpeed={handleSetSpeed}
        />

        <div className="flex items-center justify-end">
          <button
            type="button"
            onClick={copyPermalink}
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs hover:bg-accent",
              copied && "border-[hsl(var(--success))]/40 text-[hsl(var(--success))]",
            )}
          >
            {copied ? "Copied" : "Copy permalink to this step"}
          </button>
        </div>

        <StepView step={current} index={selected} />

        {submission && selected === steps.length - 1 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Final submission (patch)
            </h3>
            <pre className="max-h-[500px] overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed">
              <code>{submission}</code>
            </pre>
          </div>
        )}

        <AnnotationPanel
          runId={runId}
          trajectoryId={trajectoryId}
          stepIndex={selected}
          annotations={stepAnnotations}
        />
      </section>
    </div>
  );
}

function SidebarLink({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded px-2 py-1.5 text-left transition-colors",
        active ? "bg-accent text-accent-foreground" : "hover:bg-accent/60",
      )}
    >
      {children}
    </button>
  );
}
