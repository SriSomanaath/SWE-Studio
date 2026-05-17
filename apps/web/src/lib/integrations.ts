export interface Integration {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  upstream: string;
  status: "first-class" | "community" | "experimental";
  keywords: string[];
  snippet: string;
  features: string[];
}

export const INTEGRATIONS: Integration[] = [
  {
    slug: "studio",
    name: "SWE Studio Agent",
    tagline: "Native, built in",
    description:
      "SWE Studio ships its own coding-agent loop. Launch a run from the web form or the CLI; trajectories are indexed automatically and live mode streams every step as it's written.",
    upstream: "/agent/new",
    status: "first-class",
    keywords: [
      "SWE Studio agent",
      "coding agent dashboard",
      "agent trajectory viewer",
    ],
    snippet: `# Launch directly from the terminal:
swe-studio agent run \\
  --problem "Fix the off-by-one in foo.py" \\
  --repo /path/to/your/repo \\
  --model claude-sonnet-4-5

# Or open /agent/new in the browser.`,
    features: [
      "Automatic indexing of every .traj the agent writes",
      "Live trajectory streaming via SSE while the run is in progress",
      "Optional Docker sandbox per `bash` command",
      "Cost, token, and step-count analytics out of the box",
    ],
  },
  {
    slug: "aider",
    name: "Aider",
    tagline: "Push trajectories via the SDK",
    description:
      "Use the swe-studio-sdk to stream Aider sessions into Studio. Each turn becomes a step you can replay; final diffs land in the per-trajectory patch view; cost is tracked end-to-end.",
    upstream: "https://github.com/Aider-AI/aider",
    status: "community",
    keywords: ["Aider observability", "Aider session viewer", "Aider trajectory dashboard"],
    snippet: `pip install swe-studio-sdk

from swe_studio_sdk import attach

with attach("aider-run", issue_id) as ctx:
    ctx.user_message(issue_body)
    for response in coder.run_stream(issue_body):
        ctx.step(
            thought=response.reasoning or "",
            action=response.edit_command or "",
            observation=response.test_output or "",
        )
    ctx.finish(
        exit_status="submitted",
        submission=coder.last_diff,
        eval="resolved" if coder.tests_passing else "failed",
        instance_cost=coder.usage.total_cost_usd,
    )`,
    features: [
      "Step-by-step replay of every Aider turn",
      "Final diff displayed in the Studio patch view",
      "Cost & token totals reconciled to Aider's usage object",
      "Annotate any step with team notes",
    ],
  },
  {
    slug: "openhands",
    name: "OpenHands",
    tagline: "Stream Action/Observation events",
    description:
      "OpenHands emits Action and Observation events you can map directly onto Studio steps. The SDK's context manager handles incremental ingest so live mode lights up while the agent works.",
    upstream: "https://github.com/All-Hands-AI/OpenHands",
    status: "community",
    keywords: ["OpenHands dashboard", "OpenHands replay", "OpenHands observability"],
    snippet: `from swe_studio_sdk import attach
from openhands.events import Action, Observation

with attach("openhands-run", task_id) as ctx:
    ctx.user_message(task.description)
    async for ev in agent.stream():
        if isinstance(ev, Action):
            ctx.step(thought=ev.thought, action=ev.command)
        elif isinstance(ev, Observation):
            ctx.step(observation=ev.content)
    ctx.finish(exit_status=agent.exit_status, submission=agent.final_diff)`,
    features: [
      "Per-event step granularity (Action + Observation)",
      "Compatible with both async and sync runners",
      "Side-by-side compare with any other agent on the same instance",
      "Multi-instance run matrix for benchmark comparisons",
    ],
  },
  {
    slug: "cline",
    name: "Cline",
    tagline: "VS Code agent observability",
    description:
      "Bridge Cline's task log into Studio with the SDK. Useful when running Cline on long-form refactors or benchmark suites, every prompt/response/tool call becomes a Studio step.",
    upstream: "https://github.com/cline/cline",
    status: "community",
    keywords: ["Cline observability", "VS Code agent dashboard", "Cline trajectory viewer"],
    snippet: `from swe_studio_sdk import attach

with attach("cline-run", task_id) as ctx:
    ctx.user_message(task.prompt)
    for entry in cline_task.iter_log():
        ctx.step(
            thought=entry.reasoning,
            action=entry.tool_call,
            observation=entry.tool_result,
        )
    ctx.finish(exit_status="submitted", submission=cline_task.final_diff)`,
    features: [
      "Tool-call-level granularity",
      "Cost tracking when paired with provider usage hooks",
      "Markdown export for sharing Cline sessions with teammates",
      "Bookmark & annotate noteworthy edits",
    ],
  },
  {
    slug: "custom",
    name: "Custom agents",
    tagline: "Bring your own loop",
    description:
      "Have a homegrown agent? The SDK's context manager works with any Python loop. Push trajectories step-by-step for live mode, or buffer with flush_every to batch ingest at scale.",
    upstream: "/api-docs",
    status: "first-class",
    keywords: ["LLM agent observability", "agent trajectory tool", "agent benchmark dashboard"],
    snippet: `from swe_studio_sdk import attach

with attach("my-run", instance_id, flush_every=3) as ctx:  # batch every 3 steps
    ctx.user_message(problem)
    for thought, action, obs in my_agent.run(problem):
        ctx.step(thought=thought, action=action, observation=obs)
    ctx.finish(
        exit_status="submitted",
        submission=patch,
        eval="resolved",
        instance_cost=usage.cost_usd,
        tokens_sent=usage.prompt_tokens,
        tokens_received=usage.completion_tokens,
    )`,
    features: [
      "Studio's native .traj format",
      "Atomic incremental writes, Studio never sees half-written files",
      "Works with any LLM provider via swe-studio-sdk's HTTP client",
      "Same analytics, compare, and search features as native runs",
    ],
  },
];

export function getIntegration(slug: string): Integration | undefined {
  return INTEGRATIONS.find((i) => i.slug === slug);
}
