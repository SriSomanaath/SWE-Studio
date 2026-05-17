"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Card, CardBody } from "@/components/Card";
import { API_URL } from "@/lib/api";
import { studioIdentityHeaders } from "@/lib/session-headers";

export default function NewAgentRun() {
  const router = useRouter();
  const [problem, setProblem] = useState("");
  const [repo, setRepo] = useState("");
  const [model, setModel] = useState("claude-sonnet-4-5");
  const [maxSteps, setMaxSteps] = useState(30);
  const [maxCost, setMaxCost] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(await studioIdentityHeaders()),
      };
      const res = await fetch(`${API_URL}/agent/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          problem,
          repo,
          model,
          max_steps: Number(maxSteps),
          max_cost_usd: Number(maxCost),
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`${res.status}: ${txt}`);
      }
      const body = (await res.json()) as { run_id: string; trajectory_id: string };
      router.push(
        `/runs/${encodeURIComponent(body.run_id)}/${encodeURIComponent(body.trajectory_id)}?play=1`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start agent");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Run an agent</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Launches SWE Studio&apos;s in-process coding agent against a local repository. The
          trajectory is written incrementally so Phase 3 live mode renders the playback as the
          agent works.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-xs">
          <span className="uppercase tracking-wide text-muted-foreground">Problem statement</span>
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            required
            rows={5}
            placeholder="e.g. 'foo.py raises TypeError when called with no args. Add a default and add a test that pins the new behavior.'"
            className="rounded-md border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-foreground/40"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs">
          <span className="uppercase tracking-wide text-muted-foreground">Repository path</span>
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            required
            placeholder="/Users/you/code/your-repo"
            className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
          />
          <span className="text-[10px] text-muted-foreground">
            Absolute path on the server. The agent runs <code className="font-mono">bash</code>/{" "}
            <code className="font-mono">read</code> / <code className="font-mono">write</code>{" "}
            relative to this directory.
          </span>
        </label>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="uppercase tracking-wide text-muted-foreground">Model</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="uppercase tracking-wide text-muted-foreground">Max steps</span>
            <input
              type="number"
              value={maxSteps}
              onChange={(e) => setMaxSteps(Number(e.target.value))}
              min={1}
              max={200}
              className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="uppercase tracking-wide text-muted-foreground">Max cost (USD)</span>
            <input
              type="number"
              step="0.01"
              value={maxCost}
              onChange={(e) => setMaxCost(Number(e.target.value))}
              min={0.01}
              className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs outline-none focus:border-foreground/40"
            />
          </label>
        </div>

        {error && (
          <Card>
            <CardBody>
              <p className="text-xs text-[hsl(var(--danger))]">{error}</p>
            </CardBody>
          </Card>
        )}

        <button
          type="submit"
          disabled={busy || !problem.trim() || !repo.trim()}
          className="rounded-md border border-border bg-foreground px-3 py-2 text-sm text-background hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Starting agent…" : "Start agent run →"}
        </button>
      </form>

      <Card>
        <CardBody>
          <h2 className="text-sm font-semibold">Safety notes</h2>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            <li>
              Commands run in a subprocess at <code className="font-mono">repo</code>, with no
              container isolation. Don&apos;t point at sensitive working trees.
            </li>
            <li>
              Each <code className="font-mono">bash</code> step has a 30-second timeout. Files
              written by the agent are capped at 64 KB.
            </li>
            <li>
              The agent will stop at <code className="font-mono">max_steps</code>,{" "}
              <code className="font-mono">max_cost_usd</code>, or when it issues{" "}
              <code className="font-mono">submit</code> /{" "}
              <code className="font-mono">finish</code>.
            </li>
            <li>
              Requires <code className="font-mono">ANTHROPIC_API_KEY</code> (or{" "}
              <code className="font-mono">OPENAI_API_KEY</code>) in the API environment, and{" "}
              <code className="font-mono">pip install litellm</code>.
            </li>
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}
