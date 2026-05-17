/**
 * @swe-studio/sdk
 *
 * Push coding-agent trajectories to a SWE Studio instance from any Node /
 * TypeScript agent. Mirror of the Python `swe-studio-sdk` package; same
 * payload shape, same /ingest endpoint, same trajectory-context pattern.
 */

export type EvalState = "resolved" | "submitted" | "failed" | "completed";

export interface ModelStats {
  instance_cost?: number | null;
  tokens_sent?: number | null;
  tokens_received?: number | null;
  api_calls?: number | null;
}

export interface HistoryMessage {
  role: "system" | "user" | "assistant" | string;
  content: string;
}

export interface TrajectoryStepRecord {
  thought: string;
  action: string;
  observation: string;
  response: string;
  messages: unknown[];
}

export interface TrajectoryPayload {
  history: HistoryMessage[];
  trajectory: TrajectoryStepRecord[];
  info: {
    exit_status: string;
    submission: string | null;
    model_stats: ModelStats;
  };
}

export interface AttachOptions {
  /** SWE Studio run identifier. Treated as kebab-case-safe by the server. */
  runId: string;
  /** Per-instance trajectory identifier. Stable across writes. */
  trajectoryId: string;
  /** Studio API base URL. Defaults to http://localhost:8080. */
  baseUrl?: string;
  /** Optional system prompt to seed the trajectory history. */
  systemPrompt?: string;
  /** Push every N steps. 1 (default) gives live mode; higher = batching. */
  flushEvery?: number;
  /** Author name to attach to annotations created via `annotate()`. */
  author?: string;
  /** Optional API key for write endpoints (when Studio has `API_KEYS` set). */
  apiKey?: string;
}

export interface FinishOptions {
  exitStatus?: string;
  submission?: string | null;
  eval?: EvalState;
  instanceCost?: number;
  tokensSent?: number;
  tokensReceived?: number;
  apiCalls?: number;
}

const DEFAULT_BASE = "http://localhost:8080";

function authHeaders(opts: AttachOptions): Record<string, string> {
  const headers: Record<string, string> = {};
  if (opts.author) headers["X-Author"] = opts.author;
  if (opts.apiKey) headers["X-API-Key"] = opts.apiKey;
  return headers;
}

export class StudioClient {
  readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly author?: string;

  constructor(opts: { baseUrl?: string; apiKey?: string; author?: string } = {}) {
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE).replace(/\/$/, "");
    this.apiKey = opts.apiKey;
    this.author = opts.author;
  }

  async ingest(
    runId: string,
    trajectoryId: string,
    payload: TrajectoryPayload,
    evalState?: EvalState,
  ): Promise<{ run_id: string; trajectory_id: string; file_path: string }> {
    const url = new URL(
      `${this.baseUrl}/ingest/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}`,
    );
    if (evalState) url.searchParams.set("eval", evalState);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`ingest failed: ${res.status} ${await safeBody(res)}`);
    }
    return (await res.json()) as { run_id: string; trajectory_id: string; file_path: string };
  }

  async annotate(
    runId: string,
    trajectoryId: string,
    body: string,
    stepIndex = -1,
  ): Promise<void> {
    const url = `${this.baseUrl}/runs/${encodeURIComponent(runId)}/trajectories/${encodeURIComponent(trajectoryId)}/annotations`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.author) headers["X-Author"] = this.author;
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ step_index: stepIndex, body }),
    });
    if (!res.ok) {
      throw new Error(`annotate failed: ${res.status} ${await safeBody(res)}`);
    }
  }
}

async function safeBody(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

export class TrajectoryContext {
  private readonly client: StudioClient;
  private readonly opts: AttachOptions;
  private readonly history: HistoryMessage[] = [];
  private readonly steps: TrajectoryStepRecord[] = [];
  private readonly info = {
    exit_status: "running",
    submission: null as string | null,
    model_stats: {
      instance_cost: null,
      tokens_sent: null,
      tokens_received: null,
      api_calls: null,
    } as ModelStats,
  };
  private flushEvery: number;
  private stepsSinceFlush = 0;
  private closed = false;

  constructor(client: StudioClient, opts: AttachOptions) {
    this.client = client;
    this.opts = opts;
    this.flushEvery = Math.max(1, opts.flushEvery ?? 1);
    if (opts.systemPrompt) {
      this.history.push({ role: "system", content: opts.systemPrompt });
    }
  }

  async userMessage(content: string): Promise<void> {
    this.history.push({ role: "user", content });
    await this.flush(true);
  }

  async step(
    s: {
      thought?: string;
      action?: string;
      observation?: string;
      response?: string;
    } = {},
  ): Promise<void> {
    this.steps.push({
      thought: s.thought ?? "",
      action: s.action ?? "",
      response: s.response ?? "",
      observation: s.observation ?? "",
      messages: [],
    });
    this.stepsSinceFlush += 1;
    if (this.stepsSinceFlush >= this.flushEvery) {
      await this.flush();
    }
  }

  async finish(opts: FinishOptions = {}): Promise<void> {
    this.info.exit_status = opts.exitStatus ?? "submitted";
    if (opts.submission !== undefined) this.info.submission = opts.submission;
    const stats = this.info.model_stats;
    if (opts.instanceCost !== undefined) stats.instance_cost = opts.instanceCost;
    if (opts.tokensSent !== undefined) stats.tokens_sent = opts.tokensSent;
    if (opts.tokensReceived !== undefined) stats.tokens_received = opts.tokensReceived;
    if (opts.apiCalls !== undefined) stats.api_calls = opts.apiCalls;
    else if (stats.api_calls == null) stats.api_calls = this.steps.length;
    this.closed = true;
    await this.flush(true, opts.eval);
  }

  private payload(): TrajectoryPayload {
    return { history: this.history, trajectory: this.steps, info: this.info };
  }

  private async flush(force = false, evalState?: EvalState): Promise<void> {
    if (!force && this.stepsSinceFlush === 0) return;
    await this.client.ingest(
      this.opts.runId,
      this.opts.trajectoryId,
      this.payload(),
      evalState,
    );
    this.stepsSinceFlush = 0;
  }
}

/**
 * Attach to a SWE Studio run. Use the returned context to record steps and
 * call `finish()` when the agent is done.
 *
 * ```ts
 * const ctx = await attach({ runId: "my-run", trajectoryId: "issue-42" });
 * await ctx.userMessage("Fix the off-by-one in foo.ts");
 * for (const step of await agent.run()) {
 *   await ctx.step({ thought: step.reasoning, action: step.command, observation: step.output });
 * }
 * await ctx.finish({ exitStatus: "submitted", submission: diff, eval: "resolved" });
 * ```
 */
export async function attach(opts: AttachOptions): Promise<TrajectoryContext> {
  const client = new StudioClient({
    baseUrl: opts.baseUrl,
    apiKey: opts.apiKey,
    author: opts.author,
  });
  return new TrajectoryContext(client, opts);
}

export default { attach, StudioClient };
