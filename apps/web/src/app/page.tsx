import Link from "next/link";

import { AgentComposer, type Suggestion } from "@/components/AgentComposer";
import { listRuns } from "@/lib/api";
import { formatCount } from "@/lib/format";

export const dynamic = "force-dynamic";

// Real tasks (two are SWE-bench Lite issues) so a first run is one click.
const SUGGESTIONS: Suggestion[] = [
  {
    title: "Fix bytes HTTP methods",
    body: "requests turns b'GET' into the literal string \"b'GET'\" before sending the request.",
    repo: "psf/requests",
    problem:
      "In requests/sessions.py, `method = builtin_str(method)` turns a bytes method such as b'GET' into the literal string \"b'GET'\" on Python 3, so the request goes out with a bogus method. Make bytes methods decode correctly and add a test.",
  },
  {
    title: "Accept lists of hooks",
    body: "Let the hooks argument take several callables per event instead of exactly one.",
    repo: "psf/requests",
    problem:
      "Request(hooks={'response': [hook_a, hook_b]}) wraps the list in another list and then fails because a list is not callable. Accept a list of callables per hook event and add a test.",
  },
  {
    title: "Warm-up run",
    body: "Append a line to a README and submit: a quick end-to-end check of your executor.",
    repo: "octocat/Hello-World",
    problem: 'Append the line "Hello from SWE Studio" to the README file, then submit.',
  },
];

export default async function HomePage() {
  const runs = await listRuns().catch(() => []);
  const recent = runs.slice(0, 4);

  return (
    <div className="flex flex-col items-center pb-16">
      <h2 className="mt-[8vh] text-balance text-center text-[28px] font-medium leading-tight tracking-[-0.6px] sm:mt-[12vh] sm:text-[36px]">
        What should your agent fix?
      </h2>
      <div className="mt-8 flex w-full flex-col items-center">
        <AgentComposer suggestions={SUGGESTIONS} />
      </div>

      {recent.length > 0 && (
        <section className="mt-10 w-full max-w-[1020px]">
          <div className="mb-2.5 flex items-baseline justify-between">
            <p className="text-sm text-muted-foreground">Runs</p>
            <Link href="/runs" className="text-sm text-muted-foreground hover:text-foreground">
              View all
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {recent.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${encodeURIComponent(run.id)}`}
                className="flex items-center justify-between rounded-2xl border border-border px-5 py-4 transition-[transform,box-shadow,border-color] duration-300 ease-out-soft hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-[0_10px_30px_-14px_rgba(0,0,0,0.18)]"
              >
                <span className="truncate font-mono text-[14px]">{run.id}</span>
                <span className="ml-4 shrink-0 text-sm text-muted-foreground">
                  {formatCount(run.trajectory_count)} trajectories
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
