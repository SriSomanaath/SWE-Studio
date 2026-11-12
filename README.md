# SWE Studio

Dashboard and toolkit for working with coding agent trajectories. Reads `.traj` files from disk, lets you browse, search, compare and replay them in a web UI, and can also run its own agent loop against a local repo.

## Stack

- FastAPI + SQLite (with FTS5) for the API and index
- Next.js 15 App Router for the web
- pnpm workspaces + Turborepo
- Python and JS SDKs for pushing trajectories from external agents
- NextAuth for sign in (GitHub or dev credentials)
- Optional `sentence-transformers` for semantic similarity
- `litellm` for the bundled in-process coding agent

## Repo layout

```
apps/
  api/         FastAPI backend (index, routers, agent loop)
  web/         Next.js frontend
  sdk-python/  pip install swe-studio-sdk  (also ships the swe-studio CLI)
  sdk-js/      npm install @swe-studio/sdk
fixtures/      sample trajectories so the app boots with content
docker-compose.yml
```

## Quickstart

```bash
# install
pnpm install
python -m venv apps/api/.venv && source apps/api/.venv/bin/activate
pip install -e "apps/api[dev]"

# .env
cp .env.example .env
# default TRAJECTORIES_DIR points at the included fixtures

# run (two terminals or via pnpm dev)
pnpm dev:api    # http://localhost:8080  (OpenAPI at /docs)
pnpm dev:web    # http://localhost:3000
```

Or with Docker:

```bash
docker compose up --build
```

### Demo `.env`

The viewer runs on the bundled fixtures with no API keys. Only the agent
features (`/agent/new`, ensemble, bench) call an LLM.

```env
# Viewer: index the sample trajectories shipped in the repo
TRAJECTORIES_DIR=./fixtures/trajectories
API_HOST=0.0.0.0
API_PORT=8080
NEXT_PUBLIC_API_URL=http://localhost:8080

# Sign in: local dev credentials, no GitHub app needed
AUTH_DEV_CREDENTIALS=true
AUTH_SECRET=change-me   # openssl rand -base64 32
SITE_URL=http://localhost:3000

# Optional: GitHub sign in
# AUTH_GITHUB_ID=
# AUTH_GITHUB_SECRET=

# Optional: agent + AI summaries. Leave empty for a zero-cost demo.
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# VLLM_BASE_URL=        # self-hosted open model (see deploy/k8s/vllm)
```

## Live demo and cost

| Piece | Where | Cost |
|---|---|---|
| Web (`apps/web`) | Vercel | free tier |
| API (`apps/api`, SQLite + fixtures) | Render / Fly.io / Railway | free tier to ~$5/mo |
| Agent runs | your LLM key | per call. Leave keys unset on a public demo. |
| Kubernetes stack (`infra/`, `deploy/k8s`) | AWS EKS + Karpenter | EKS control plane ~$73/mo plus nodes; GPU nodes for vLLM cost much more. Not needed for a demo. |

For a portfolio link, deploy the web app and API with no LLM keys. The
EKS, vLLM and monitoring setup is documented in `infra/` and `deploy/k8s`
for anyone who wants to reproduce the benchmark.

## What it does

**Viewer**

- automatic indexing of every `.traj` in `TRAJECTORIES_DIR`
- trajectory page with step nav, copy-link to a step, replay player (space, arrow keys, speed pills)
- filters, sort, virtualized table for huge runs
- live mode renders new steps over SSE as files change
- analytics dashboard (cost / step / pass rate histograms, top N)
- per-trajectory and run-vs-run compare with patch overlap
- action-fingerprint clusters and similarity (FTS or optional embeddings)
- full text search across problems, step text, annotations
- `cmd k` palette anywhere in the app

**Collab**

- annotations on any step (or the whole trajectory)
- bookmarks per author
- public share links with TTL and revoke
- markdown export of any trajectory
- webhooks (HMAC signed, retry with backoff) for `trajectory.resolved` and friends
- real time presence over SSE
- sign in via NextAuth (GitHub or local dev credentials)

**Producer**

- `POST /ingest` for external agents to push trajectories
- bundled agent at `POST /agent/run` (and a web form at `/agent/new`)
- tools: `bash`, `read`, `write`, `submit`, `finish`
- optional Docker sandbox for the `bash` tool
- ensemble endpoint to race N models on the same problem
- batch harness CLI for running over a JSONL of instances

**Ops**

- structured JSON logs to stdout
- Prometheus `/metrics`
- optional API key auth for write endpoints
- AI trajectory summaries (heuristic or Anthropic backed)
- HuggingFace ready dataset export with `dataset_card` CLI

## CLI

```bash
swe-studio runs ls
swe-studio traj show sample-run-001 django__django-12345
swe-studio search "BooleanField"
swe-studio summarize sample-run-001 django__django-12345
swe-studio curate add --slug bool-fix --run-id sample-run-001 \
  --trajectory-id django__django-12345 --title "BooleanField fix"
swe-studio webhook add --url https://hooks.slack.com/... --events trajectory.resolved
swe-studio agent run --problem "Fix the off by one" --repo /path/to/repo
swe-studio bench run --instances instances.jsonl --model claude-sonnet-4-5
```

## Push a trajectory from any agent

Python:

```python
from swe_studio_sdk import attach

with attach("my-run", "issue-42") as ctx:
    ctx.user_message("Fix the off by one in foo.py")
    for thought, action, obs in agent.run():
        ctx.step(thought=thought, action=action, observation=obs)
    ctx.finish(exit_status="submitted", submission=patch, eval="resolved")
```

Node:

```ts
import { attach } from "@swe-studio/sdk";

const ctx = await attach({ runId: "my-run", trajectoryId: "issue-42" });
await ctx.userMessage("Fix the off by one in foo.ts");
for await (const ev of agent.run()) {
  await ctx.step({ thought: ev.reasoning, action: ev.toolCall, observation: ev.toolResult });
}
await ctx.finish({ exitStatus: "submitted", submission: diff, eval: "resolved" });
```

## License

MIT.
