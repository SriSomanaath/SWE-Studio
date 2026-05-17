# @swe-studio/sdk

Push coding-agent trajectories to a [SWE Studio](https://github.com/<your-org>/SWE-Studio) instance from any Node / TypeScript agent.

The SDK wraps the Studio `/ingest` endpoint with a context manager–style API. Each step you record is pushed to Studio immediately so its live mode lights up while your agent is still running.

## Install

```bash
npm install @swe-studio/sdk
# or: pnpm add @swe-studio/sdk
# or: yarn add @swe-studio/sdk
```

## Quick start

```ts
import { attach } from "@swe-studio/sdk";

const ctx = await attach({
  runId: "my-cline-run",
  trajectoryId: "issue-42",
  baseUrl: "http://localhost:8080",
});

await ctx.userMessage("Fix the off-by-one in foo.ts");

for await (const event of agent.run(prompt)) {
  await ctx.step({
    thought: event.reasoning,
    action: event.toolCall,
    observation: event.toolResult,
  });
}

await ctx.finish({
  exitStatus: "submitted",
  submission: agent.finalDiff,
  eval: "resolved",
  instanceCost: 0.27,
  tokensSent: 18420,
  tokensReceived: 1923,
});
```

Open `http://localhost:3001/live` in another tab while this runs — Studio will pick up each step in real time.

## Batching

`flushEvery: N` defers the HTTP POST until N steps have accumulated:

```ts
const ctx = await attach({ runId, trajectoryId, flushEvery: 5 });
```

`finish()` always flushes regardless of `flushEvery`.

## Auth

When the Studio API is started with `API_KEYS=...`, pass `apiKey`:

```ts
const ctx = await attach({ runId, trajectoryId, apiKey: "studio-prod-abc123" });
```

`author` sets the `X-Author` header for any annotations you create via the low-level `StudioClient`.

## Low-level client

```ts
import { StudioClient } from "@swe-studio/sdk";

const client = new StudioClient({ baseUrl: "http://localhost:8080" });
await client.ingest("my-run", "issue-1", {
  history: [{ role: "user", content: "fix it" }],
  trajectory: [{ thought: "", action: "ls", observation: "", response: "", messages: [] }],
  info: { exit_status: "submitted", submission: null, model_stats: {} },
});
```

## License

MIT.
