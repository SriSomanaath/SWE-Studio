/**
 * Integration test: spawn the real FastAPI server in a subprocess and verify
 * that an attach() round-trip lands on the Studio side. This is the closest
 * possible end-to-end check — the SDK speaks real HTTP, the server is real.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { attach, StudioClient } from "../src/index.js";

const API_DIR = join(import.meta.dirname, "..", "..", "api");
const VENV_PY = join(API_DIR, ".venv", "bin", "python");

let server: ChildProcess;
let baseUrl: string;
let tmpDir: string;

beforeAll(async () => {
  tmpDir = mkdtempSync(join(tmpdir(), "swe-studio-js-sdk-"));
  const port = await freePort();
  baseUrl = `http://127.0.0.1:${port}`;

  const env = {
    ...process.env,
    TRAJECTORIES_DIR: tmpDir,
    DB_PATH: join(tmpDir, "index.sqlite"),
    INDEXER_ENABLED: "false",
  };

  server = spawn(
    VENV_PY,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "warning"],
    { cwd: API_DIR, env, stdio: ["ignore", "pipe", "pipe"] },
  );

  // Wait until /health responds.
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${baseUrl}/health`);
      if (r.ok) return;
    } catch {
      /* keep polling */
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("uvicorn did not come up");
}, 30_000);

afterAll(async () => {
  if (server) {
    server.kill("SIGTERM");
    await new Promise((r) => setTimeout(r, 200));
  }
  if (tmpDir) rmSync(tmpDir, { recursive: true, force: true });
});

async function freePort(): Promise<number> {
  const net = await import("node:net");
  return await new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as { port: number }).port;
      srv.close(() => resolve(port));
    });
  });
}

describe("attach()", () => {
  it("rounds-trips a complete trajectory", async () => {
    const ctx = await attach({
      runId: "js-run",
      trajectoryId: "issue-001",
      baseUrl,
      systemPrompt: "You are an agent",
    });
    await ctx.userMessage("Fix foo.ts");
    await ctx.step({ thought: "look around", action: "ls", observation: "foo.ts" });
    await ctx.step({ thought: "patch", action: "sed -i s/a/b/ foo.ts", observation: "" });
    await ctx.finish({
      exitStatus: "submitted",
      submission: "diff --git a/foo.ts b/foo.ts\n+++ b/foo.ts\n@@\n+b\n-a\n",
      eval: "resolved",
      instanceCost: 0.07,
      tokensSent: 1200,
      tokensReceived: 180,
    });

    const res = await fetch(`${baseUrl}/runs/js-run/trajectories/issue-001`);
    expect(res.ok).toBe(true);
    const body = (await res.json()) as {
      steps: unknown[];
      info: { model_stats: { instance_cost: number } };
      eval: { resolved: boolean };
    };
    expect(body.steps).toHaveLength(2);
    expect(body.info.model_stats.instance_cost).toBe(0.07);
    expect(body.eval.resolved).toBe(true);
  });

  it("flushEvery batches steps but always flushes on finish", async () => {
    const ctx = await attach({
      runId: "js-run",
      trajectoryId: "issue-002",
      baseUrl,
      flushEvery: 5,
    });
    await ctx.userMessage("Do work");
    for (let i = 0; i < 3; i++) {
      await ctx.step({ thought: `t${i}`, action: `echo ${i}` });
    }
    // Steps 1..3 should NOT have been pushed yet (threshold is 5).
    const mid = await (await fetch(`${baseUrl}/runs/js-run/trajectories/issue-002`)).json();
    expect((mid as { info: { exit_status: string } }).info.exit_status).toBe("running");

    await ctx.finish({ exitStatus: "exit_forfeit" });

    const after = await (await fetch(`${baseUrl}/runs/js-run/trajectories/issue-002`)).json();
    expect((after as { steps: unknown[] }).steps).toHaveLength(3);
    expect((after as { info: { exit_status: string } }).info.exit_status).toBe("exit_forfeit");
  });

  it("StudioClient.annotate creates an annotation", async () => {
    const client = new StudioClient({ baseUrl, author: "js-test" });
    // Use the trajectory created in test 1.
    await client.annotate("js-run", "issue-001", "annotation from JS SDK", 0);
    const res = await fetch(`${baseUrl}/runs/js-run/trajectories/issue-001/annotations`);
    const notes = (await res.json()) as Array<{ author: string; body: string; step_index: number }>;
    expect(notes.some((n) => n.author === "js-test" && n.step_index === 0)).toBe(true);
  });
});
