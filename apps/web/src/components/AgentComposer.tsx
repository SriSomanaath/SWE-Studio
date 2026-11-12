"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { IconArrowUp, IconBranch, IconChevronDown, IconPlus } from "@/components/Icons";
import { API_URL } from "@/lib/api";
import { cn } from "@/lib/cn";
import { studioIdentityHeaders } from "@/lib/session-headers";

const MODELS = [
  { id: "claude-sonnet-4-5", label: "Claude Sonnet 4.5" },
  { id: "moonshot/kimi-k3", label: "Kimi K3" },
  { id: "hosted_vllm/Qwen/Qwen2.5-Coder-7B-Instruct", label: "Qwen 2.5 Coder (vLLM)" },
];

export type Suggestion = { title: string; body: string; problem: string; repo: string };

type Launched = { runId: string; trajectoryId: string; phase: string };

// "owner/repo", "github.com/owner/repo" or a full URL -> clone URL for a k8s
// Job; anything else is treated as a path on the API host (thread executor).
function toRepoUrl(repo: string): string | null {
  const r = repo.trim().replace(/\.git$/, "");
  if (/^https?:\/\//.test(r)) return r;
  if (/^github\.com\//.test(r)) return `https://${r}`;
  if (/^[\w.-]+\/[\w.-]+$/.test(r)) return `https://github.com/${r}`;
  return null;
}

export function AgentComposer({ suggestions }: { suggestions: Suggestion[] }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [problem, setProblem] = useState("");
  const [repo, setRepo] = useState("");
  const [model, setModel] = useState(MODELS[0].id);
  const [ref, setRef] = useState("HEAD");
  const [maxSteps, setMaxSteps] = useState(30);
  const [maxCost, setMaxCost] = useState(2);
  const [options, setOptions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [launched, setLaunched] = useState<Launched | null>(null);

  const ready = problem.trim() && repo.trim() && !busy;

  // Job runs only produce a trajectory once the pod reports back, so show
  // the Job's phase here instead of opening an empty trajectory page.
  useEffect(() => {
    if (!launched || launched.phase === "succeeded" || launched.phase === "failed") return;
    const t = window.setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/agent/runs/${encodeURIComponent(launched.runId)}/status`);
        if (!res.ok) return;
        const body = (await res.json()) as { trajectories: Record<string, { phase: string }> };
        const phase = body.trajectories[launched.trajectoryId]?.phase;
        if (phase) setLaunched((l) => (l ? { ...l, phase } : l));
      } catch {
        // transient; next tick retries
      }
    }, 3000);
    return () => window.clearInterval(t);
  }, [launched]);

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    const repoUrl = toRepoUrl(repo);
    try {
      const res = await fetch(`${API_URL}/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await studioIdentityHeaders()) },
        body: JSON.stringify({
          problem,
          model,
          max_steps: Number(maxSteps),
          max_cost_usd: Number(maxCost),
          ...(repoUrl ? { repo_url: repoUrl, repo_ref: ref || "HEAD" } : { repo: repo.trim() }),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`);
      }
      const body = (await res.json()) as { run_id: string; trajectory_id: string };
      if (repoUrl) {
        setLaunched({ runId: body.run_id, trajectoryId: body.trajectory_id, phase: "pending" });
      } else {
        router.push(`/runs/${encodeURIComponent(body.run_id)}/${encodeURIComponent(body.trajectory_id)}?play=1`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start the agent");
    } finally {
      setBusy(false);
    }
  }

  const field =
    "h-9 rounded-full border border-border bg-background px-3.5 text-[13px] outline-none transition-[border-color,box-shadow] duration-200 ease-out-soft placeholder:text-muted-foreground focus:border-foreground/25 focus:shadow-[0_0_0_3px_rgba(0,0,0,0.04)]";

  const modelSelect = (
    <label className="relative shrink-0">
      <span className="sr-only">Model</span>
      <select
        value={model}
        onChange={(e) => setModel(e.target.value)}
        className="h-9 cursor-pointer appearance-none rounded-full bg-accent pl-3.5 pr-8 text-[13px] font-medium outline-none transition-colors duration-200 ease-out-soft hover:bg-foreground/[0.08]"
      >
        {MODELS.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
          </option>
        ))}
      </select>
      <IconChevronDown className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
    </label>
  );

  return (
    <>
      <form onSubmit={submit} className="w-full max-w-[860px]">
        <div className="flex h-14 items-center gap-1 rounded-full border border-border bg-background pl-2 pr-2 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.10)] transition-[box-shadow,border-color] duration-300 ease-out-soft focus-within:border-foreground/15 focus-within:shadow-[0_1px_2px_rgba(0,0,0,0.05),0_16px_40px_-16px_rgba(0,0,0,0.18)] sm:h-16 sm:gap-1.5 sm:pl-2.5 sm:pr-2.5">
          <span className="orb h-9 w-9 shrink-0 rounded-full sm:h-10 sm:w-10" />
          <button
            type="button"
            onClick={() => setOptions((o) => !o)}
            aria-label="Run options"
            aria-expanded={options}
            className={cn(
              "rounded-full p-2 text-foreground/75 transition-[transform,background-color] duration-300 ease-out-soft hover:bg-accent active:scale-90 sm:ml-0.5",
              options && "rotate-45 bg-accent",
            )}
          >
            <IconPlus className="size-5" />
          </button>
          <input
            ref={inputRef}
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            placeholder="Describe a bug for the agent to fix…"
            // 16px minimum on mobile: smaller text makes iOS zoom on focus.
            className="min-w-0 flex-1 bg-transparent px-1 text-[16px] outline-none placeholder:text-muted-foreground sm:text-[17px]"
            aria-label="Task for the agent"
          />
          <div className="hidden sm:block">{modelSelect}</div>
          <button
            type="submit"
            disabled={!ready}
            aria-label="Start agent"
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-[background-color,transform,box-shadow] duration-300 ease-out-soft sm:h-11 sm:w-11",
              ready
                ? "bg-foreground text-background shadow-[0_4px_12px_-4px_rgba(0,0,0,0.35)] hover:scale-[1.04] active:scale-95"
                : "scale-95 bg-foreground/15 text-background",
            )}
          >
            <IconArrowUp className="size-[19px]" />
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-center gap-2 px-1">
          <label className="relative w-full sm:w-auto">
            <span className="sr-only">Repository</span>
            <IconBranch className="pointer-events-none absolute left-3.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              placeholder="owner/repo or server path"
              className={cn(field, "w-full pl-9 font-mono sm:w-[270px]")}
            />
          </label>
        </div>

        {/* Run options expand in place (grid-rows 0fr -> 1fr), no layout jump. */}
        <div
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-out-soft",
            options ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-center gap-2 px-1 pt-2.5">
              <div className="sm:hidden">{modelSelect}</div>
              <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="branch or commit" aria-label="Git ref" className={cn(field, "w-[150px] font-mono")} />
              <label className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                Steps
                <input type="number" min={1} max={200} value={maxSteps} onChange={(e) => setMaxSteps(Number(e.target.value))} className={cn(field, "w-[72px]")} />
              </label>
              <label className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                Budget $
                <input type="number" min={0.01} step={0.5} value={maxCost} onChange={(e) => setMaxCost(Number(e.target.value))} className={cn(field, "w-[72px]")} />
              </label>
            </div>
          </div>
        </div>

        {error && <p className="fade-in mt-3 text-center text-sm text-[hsl(var(--danger))]">{error}</p>}
        {launched && (
          <p className="fade-in mt-3 text-center text-sm text-muted-foreground">
            Kubernetes Job <span className="font-mono text-foreground">{launched.trajectoryId}</span>:{" "}
            <span className="font-medium text-foreground">{launched.phase}</span>
            {launched.phase === "succeeded" || launched.phase === "failed" ? (
              <>
                {" · "}
                <Link
                  className="font-medium text-foreground underline underline-offset-2"
                  href={`/runs/${encodeURIComponent(launched.runId)}/${encodeURIComponent(launched.trajectoryId)}`}
                >
                  Open trajectory
                </Link>
              </>
            ) : (
              "…"
            )}
          </p>
        )}
      </form>

      <section className="mt-12 w-full max-w-[1020px] sm:mt-[12vh]">
        <p className="mb-2.5 text-sm text-muted-foreground">Suggestions</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {suggestions.map((s) => (
            <button
              key={s.title}
              type="button"
              onClick={() => {
                setProblem(s.problem);
                setRepo(s.repo);
                inputRef.current?.focus();
              }}
              className="rounded-2xl border border-border bg-background px-5 py-4 text-left transition-[transform,box-shadow,border-color] duration-300 ease-out-soft hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-[0_10px_30px_-14px_rgba(0,0,0,0.18)] active:translate-y-0 active:scale-[0.995]"
            >
              <p className="text-[16px] font-medium tracking-[-0.2px] sm:text-[17px]">{s.title}</p>
              <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground sm:text-[15px]">{s.body}</p>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
