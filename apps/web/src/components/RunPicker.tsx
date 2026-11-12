"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/cn";
import type { RunSummary } from "@/lib/types";

export function RunPicker({
  runs,
  paramA = "a",
  paramB = "b",
}: {
  runs: RunSummary[];
  paramA?: string;
  paramB?: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const a = params.get(paramA) ?? "";
  const b = params.get(paramB) ?? "";

  function update(next: { a?: string; b?: string }) {
    const sp = new URLSearchParams(params.toString());
    if (next.a !== undefined) {
      if (next.a) sp.set(paramA, next.a);
      else sp.delete(paramA);
    }
    if (next.b !== undefined) {
      if (next.b) sp.set(paramB, next.b);
      else sp.delete(paramB);
    }
    router.replace(`?${sp.toString()}`, { scroll: false });
  }

  function swap() {
    const sp = new URLSearchParams(params.toString());
    sp.set(paramA, b);
    sp.set(paramB, a);
    router.replace(`?${sp.toString()}`, { scroll: false });
  }

  if (runs.length === 0) {
    return (
      <div className="rounded-xl border border-border/70 bg-card p-3 text-sm text-muted-foreground">
        No runs available. Index some <code className="font-mono">.traj</code> files first.
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-border/70 bg-card p-3">
      <RunSelect label="Run A" value={a} onChange={(v) => update({ a: v })} runs={runs} disabled={b} />
      <button
        type="button"
        onClick={swap}
        disabled={!a || !b}
        className={cn(
          "h-9 rounded-xl border border-border/70 px-3 text-sm",
          a && b ? "hover:bg-accent" : "opacity-40",
        )}
        title="Swap A and B"
      >
        ↔
      </button>
      <RunSelect label="Run B" value={b} onChange={(v) => update({ b: v })} runs={runs} disabled={a} />
    </div>
  );
}

function RunSelect({
  label,
  value,
  onChange,
  runs,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  runs: RunSummary[];
  disabled?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-[200px] rounded-xl border border-border/70 bg-background px-2.5 py-1.5 font-mono text-sm outline-none focus:border-foreground/40"
      >
        <option value="">— pick a run —</option>
        {runs.map((r) => (
          <option key={r.id} value={r.id} disabled={r.id === disabled}>
            {r.id}
          </option>
        ))}
      </select>
    </label>
  );
}
