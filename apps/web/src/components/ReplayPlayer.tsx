"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";

const SPEEDS = [0.5, 1, 2, 4] as const;
type Speed = (typeof SPEEDS)[number];

interface Props {
  totalSteps: number;
  selected: number;
  setSelected: (i: number) => void;
  playing: boolean;
  setPlaying: (b: boolean) => void;
  speed: Speed;
  setSpeed: (s: Speed) => void;
}

const BASE_INTERVAL_MS = 2500;

export function ReplayPlayer({
  totalSteps,
  selected,
  setSelected,
  playing,
  setPlaying,
  speed,
  setSpeed,
}: Props) {
  const timerRef = useRef<number | null>(null);

  // Auto-advance timer
  useEffect(() => {
    if (timerRef.current != null) window.clearInterval(timerRef.current);
    if (!playing) return;
    if (totalSteps === 0) return;

    const intervalMs = Math.max(120, BASE_INTERVAL_MS / speed);
    timerRef.current = window.setInterval(() => {
      if (selected + 1 >= totalSteps) {
        setPlaying(false);
        return;
      }
      setSelected(selected + 1);
    }, intervalMs);

    return () => {
      if (timerRef.current != null) window.clearInterval(timerRef.current);
    };
  }, [playing, speed, selected, totalSteps, setSelected, setPlaying]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (target?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === " ") {
        e.preventDefault();
        setPlaying(!playing);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (selected + 1 < totalSteps) setSelected(selected + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (selected > 0) setSelected(selected - 1);
      } else if (e.key === "," || e.key === "<") {
        e.preventDefault();
        const idx = SPEEDS.indexOf(speed);
        if (idx > 0) setSpeed(SPEEDS[idx - 1] as Speed);
      } else if (e.key === "." || e.key === ">") {
        e.preventDefault();
        const idx = SPEEDS.indexOf(speed);
        if (idx < SPEEDS.length - 1) setSpeed(SPEEDS[idx + 1] as Speed);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playing, selected, totalSteps, speed, setPlaying, setSelected, setSpeed]);

  const pct = totalSteps > 0 ? ((selected + 1) / totalSteps) * 100 : 0;
  const atEnd = selected + 1 >= totalSteps;

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-card p-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (atEnd && !playing) {
              setSelected(0);
              setPlaying(true);
            } else {
              setPlaying(!playing);
            }
          }}
          disabled={totalSteps === 0}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-md border border-border",
            "hover:bg-accent",
            totalSteps === 0 && "opacity-40",
          )}
          title={
            atEnd && !playing
              ? "Replay from start"
              : playing
                ? "Pause (space)"
                : "Play (space)"
          }
        >
          {playing ? <PauseIcon /> : atEnd ? <RewindIcon /> : <PlayIcon />}
        </button>
        <button
          type="button"
          onClick={() => selected > 0 && setSelected(selected - 1)}
          disabled={selected === 0}
          className={cn(
            "rounded-md border border-border px-2 py-1 font-mono text-xs",
            selected === 0 ? "opacity-40" : "hover:bg-accent",
          )}
          title="Previous step (←)"
        >
          ←
        </button>
        <button
          type="button"
          onClick={() => selected + 1 < totalSteps && setSelected(selected + 1)}
          disabled={selected + 1 >= totalSteps}
          className={cn(
            "rounded-md border border-border px-2 py-1 font-mono text-xs",
            selected + 1 >= totalSteps ? "opacity-40" : "hover:bg-accent",
          )}
          title="Next step (→)"
        >
          →
        </button>
        <div className="flex items-center gap-1 text-xs">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSpeed(s)}
              className={cn(
                "rounded-md border border-border px-2 py-1 font-mono",
                s === speed
                  ? "bg-foreground text-background"
                  : "hover:bg-accent",
              )}
              title={`Playback speed ${s}× (, and .)`}
            >
              {s}×
            </button>
          ))}
        </div>
        <span className="ml-auto font-mono text-xs tabular-nums text-muted-foreground">
          step {totalSteps === 0 ? 0 : selected + 1} / {totalSteps}
        </span>
      </div>
      <div
        className="relative h-1.5 cursor-pointer overflow-hidden rounded-full bg-muted"
        onClick={(e) => {
          if (totalSteps === 0) return;
          const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
          const fraction = (e.clientX - rect.left) / rect.width;
          const idx = Math.max(
            0,
            Math.min(totalSteps - 1, Math.floor(fraction * totalSteps)),
          );
          setSelected(idx);
        }}
        title="Scrub to step"
      >
        <div
          className={cn(
            "h-full transition-all",
            playing ? "bg-[hsl(var(--success))]" : "bg-foreground/60",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        <kbd className="font-mono">space</kbd> play/pause ·{" "}
        <kbd className="font-mono">←</kbd>/<kbd className="font-mono">→</kbd> step ·{" "}
        <kbd className="font-mono">,</kbd>/<kbd className="font-mono">.</kbd> speed
      </p>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <path d="M4 2.5v11l9-5.5z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <rect x="3.5" y="2.5" width="3" height="11" rx="0.6" />
      <rect x="9.5" y="2.5" width="3" height="11" rx="0.6" />
    </svg>
  );
}

function RewindIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden>
      <path d="M3 8l5-4v8z" />
      <rect x="9" y="3.5" width="2" height="9" rx="0.5" />
    </svg>
  );
}
