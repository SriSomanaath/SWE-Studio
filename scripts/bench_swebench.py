#!/usr/bin/env python3
"""Race N SWE-bench Lite tasks across models on SWE Studio's k8s executor.

    uv run --with swebench scripts/bench_swebench.py \
        --api http://localhost:8080 --api-key "$KEY" \
        --models claude-sonnet-4-5 hosted_vllm/Qwen/Qwen2.5-Coder-7B-Instruct \
        -n 50 --evaluate --prometheus http://localhost:9090

Flow: load tasks -> one /agent/run Job per (task, model) under one run_id,
both models' Jobs for a task in parallel (respecting the API's 429
concurrency cap) -> wait -> collect patches -> optionally score them with the
official SWE-bench harness (local Docker) and post verdicts back -> write a
markdown table to bench-results/<run_id>.md.

Every number is measured in this run. Anything that could not be measured is
printed as "not measured", never estimated.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Lite"
NM = "not measured"
# AWS list prices (us-east-1, USD/h) for the fixed parts of the stack; nodes
# are priced live from the AWS APIs in node_prices().
EKS_CONTROL_PLANE_HOURLY = 0.10
NAT_GATEWAY_HOURLY = 0.045


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", model)


class Api:
    def __init__(self, base: str, key: str | None) -> None:
        self.base, self.key = base.rstrip("/"), key

    def call(self, method: str, path: str, body: dict | None = None):
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-API-Key"] = self.key
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None


# --- run -----------------------------------------------------------------


def load_tasks(n: int, instance_ids: list[str]) -> list[dict]:
    from datasets import load_dataset  # ships with swebench

    rows = load_dataset(DATASET, split="test")
    if instance_ids:
        return [r for r in rows if r["instance_id"] in set(instance_ids)]
    return [rows[i] for i in range(min(n, len(rows)))]


def run_all(api: Api, tasks: list[dict], models: list[str], args) -> tuple[str, dict, int, float]:
    run_id = time.strftime("bench-%Y%m%dT%H%M%S", time.gmtime())
    final: dict[str, dict] = {}  # trajectory_id -> {phase, seconds}; kept because Jobs TTL away
    max_active = 0

    def poll() -> None:
        nonlocal max_active
        try:
            status = api.call("GET", f"/agent/runs/{run_id}/status")["trajectories"]
        except urllib.error.HTTPError as e:
            if e.code == 404:  # no Jobs yet
                return
            raise
        max_active = max(max_active, sum(s["phase"] in ("pending", "running") for s in status.values()))
        final.update({t: s for t, s in status.items() if s["phase"] in ("succeeded", "failed")})

    t0 = time.time()
    # Task-major order: both models' Jobs for a task start together (a race).
    jobs = [(t, m) for t in tasks for m in models]
    for task, model in jobs:
        body = {
            "problem": task["problem_statement"],
            "repo_url": f"https://github.com/{task['repo']}",
            "repo_ref": task["base_commit"],
            "model": model,
            "run_id": run_id,
            "trajectory_id": f"{task['instance_id']}__{slug(model)}",
            "max_steps": args.max_steps,
            "max_cost_usd": args.max_cost,
        }
        while True:
            try:
                api.call("POST", "/agent/run", body)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:  # 429 = RUNNER_MAX_CONCURRENT reached; wait for a slot
                    raise
                poll()
                time.sleep(15)
        print(f"started {body['trajectory_id']}", file=sys.stderr)

    # Jobs end by themselves (activeDeadlineSeconds); the extra 10 min only
    # covers Jobs whose pods never got scheduled.
    deadline = time.time() + args.job_deadline + 600
    while len(final) < len(jobs) and time.time() < deadline:
        poll()
        print(f"{len(final)}/{len(jobs)} finished, {max_active} max parallel", file=sys.stderr)
        time.sleep(15)
    return run_id, final, max_active, time.time() - t0


def collect(api: Api, run_id: str, tasks: list[dict], models: list[str], final: dict) -> list[dict]:
    out = []
    for task in tasks:
        for model in models:
            tid = f"{task['instance_id']}__{slug(model)}"
            rec = {"instance_id": task["instance_id"], "model": model, "trajectory_id": tid,
                   "phase": final.get(tid, {}).get("phase", "unfinished"),
                   "seconds": final.get(tid, {}).get("seconds"), "ingested": False,
                   "cost": None, "patch": "", "exit_status": None, "resolved": None}
            try:
                info = api.call("GET", f"/runs/{run_id}/trajectories/{tid}")["info"]
            except urllib.error.HTTPError:
                out.append(rec)  # pod died before reporting (OOM, deadline, eviction)
                continue
            patch = info.get("submission") or ""
            rec.update(ingested=True, exit_status=info.get("exit_status"),
                       cost=(info.get("model_stats") or {}).get("instance_cost"),
                       patch="" if patch.startswith("(") else patch)  # "(empty diff)" placeholder
            out.append(rec)
    return out


# --- evaluation ------------------------------------------------------------


def evaluate(records: list[dict], run_id: str, out_dir: Path, workers: int) -> None:
    """Score patches with the official SWE-bench harness (needs local Docker)."""
    for model in sorted({r["model"] for r in records}):
        recs = [r for r in records if r["model"] == model]
        preds = out_dir / f"{run_id}.{slug(model)}.predictions.jsonl"
        preds.write_text("".join(
            json.dumps({"instance_id": r["instance_id"], "model_name_or_path": slug(model),
                        "model_patch": r["patch"]}) + "\n" for r in recs))
        subprocess.run(
            [sys.executable, "-m", "swebench.harness.run_evaluation", "--dataset_name", DATASET,
             "--predictions_path", str(preds), "--run_id", run_id, "--max_workers", str(workers),
             "--instance_ids", *[r["instance_id"] for r in recs]],
            cwd=out_dir, check=False,
        )
        for r in recs:
            report = out_dir / "logs/run_evaluation" / run_id / slug(model) / r["instance_id"] / "report.json"
            if report.exists():
                r["resolved"] = bool(json.loads(report.read_text())[r["instance_id"]]["resolved"])
            elif not r["patch"]:
                r["resolved"] = False  # harness skips empty patches: unresolved by definition
            # else: harness error -> stays None ("not measured")


def post_verdicts(api: Api, run_id: str, records: list[dict]) -> None:
    for r in records:
        if r["ingested"] and r["resolved"] is not None:
            result = "resolved" if r["resolved"] else "failed"
            api.call("POST", f"/ingest/runs/{run_id}/trajectories/{r['trajectory_id']}/eval?result={result}")


# --- cluster measurements ----------------------------------------------------


def prom(url: str, query: str) -> list[dict]:
    q = urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(f"{url.rstrip('/')}/api/v1/query?{q}", timeout=30) as resp:
        return json.load(resp)["data"]["result"]


def node_prices(types: set[tuple[str, str]], region: str) -> dict[tuple[str, str], float]:
    """Live $/h per (instance_type, capacity_type): spot from the current spot
    price history (mean across AZs), on-demand from the AWS Pricing API."""
    prices = {}
    for itype, cap in types:
        if cap == "spot":
            out = subprocess.run(
                ["aws", "ec2", "describe-spot-price-history", "--region", region, "--instance-types", itype,
                 "--product-descriptions", "Linux/UNIX", "--start-time", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "--query", "SpotPriceHistory[].SpotPrice", "--output", "json"],
                capture_output=True, text=True, check=True).stdout
            vals = [float(v) for v in json.loads(out)]
        else:
            out = subprocess.run(
                ["aws", "pricing", "get-products", "--region", "us-east-1", "--service-code", "AmazonEC2",
                 "--filters", *[f"Type=TERM_MATCH,Field={k},Value={v}" for k, v in (
                     ("instanceType", itype), ("regionCode", region), ("operatingSystem", "Linux"),
                     ("tenancy", "Shared"), ("preInstalledSw", "NA"), ("capacitystatus", "Used"))],
                 "--query", "PriceList[0]", "--output", "text"],
                capture_output=True, text=True, check=True).stdout
            terms = json.loads(out)["terms"]["OnDemand"]
            dims = next(iter(terms.values()))["priceDimensions"]
            vals = [float(next(iter(dims.values()))["pricePerUnit"]["USD"])]
        if vals:
            prices[(itype, cap)] = sum(vals) / len(vals)
    return prices


def cluster_stats(url: str, seconds: float, region: str) -> dict:
    w = f"{max(int(seconds), 60)}s"
    stats = {"gpu_util_mean": None, "gpu_util_max": None, "cluster_cost": None, "node_hours": {}}
    for key, fn in (("gpu_util_mean", "avg_over_time"), ("gpu_util_max", "max_over_time")):
        res = prom(url, f"{fn}(avg(DCGM_FI_DEV_GPU_UTIL)[{w}:15s])")
        stats[key] = float(res[0]["value"][1]) if res else None
    # One sample per node per minute -> count / 60 = node-hours.
    res = prom(url, "sum by (label_node_kubernetes_io_instance_type, label_karpenter_sh_capacity_type) "
                    f"(count_over_time(kube_node_labels{{label_node_kubernetes_io_instance_type!=\"\"}}[{w}:60s]))")
    hours = {(r["metric"]["label_node_kubernetes_io_instance_type"],
              r["metric"].get("label_karpenter_sh_capacity_type") or "on-demand"): float(r["value"][1]) / 60
             for r in res}
    if hours:
        prices = node_prices(set(hours), region)
        if set(prices) == set(hours):
            stats["cluster_cost"] = sum(h * prices[k] for k, h in hours.items()) + \
                (EKS_CONTROL_PLANE_HOURLY + NAT_GATEWAY_HOURLY) * seconds / 3600
    stats["node_hours"] = {f"{t} ({c})": round(h, 3) for (t, c), h in hours.items()}
    return stats


# --- report ------------------------------------------------------------------


def p95(values: list[float]) -> float:
    s = sorted(values)
    return s[math.ceil(0.95 * len(s)) - 1]  # nearest-rank


def summarize(records: list[dict]) -> list[dict]:
    rows = []
    for model in sorted({r["model"] for r in records}):
        rs = [r for r in records if r["model"] == model]
        judged = [r["resolved"] for r in rs if r["resolved"] is not None]
        costs = [r["cost"] for r in rs if r["cost"] is not None]
        secs = [r["seconds"] for r in rs if r["seconds"] is not None]
        rows.append({
            "model": model,
            "tasks": len(rs),
            # Unjudged tasks (harness errors, not evaluated) shrink the
            # denominator, so the count is printed next to the rate.
            "resolved": f"{100 * sum(judged) / len(judged):.1f}% ({sum(judged)}/{len(judged)})" if judged else NM,
            "submitted": f"{100 * sum(bool(r['patch']) for r in rs) / len(rs):.1f}%",
            # pod died before reporting / agent hit an LLM error: neither is a
            # model failing the task, so they're shown, not hidden in resolved %.
            "errors": f"{sum(not r['ingested'] for r in rs)} / {sum(r.get('exit_status') == 'exit_error' for r in rs)}",
            "cost": f"${sum(costs) / len(costs):.4f}" if costs else NM,
            "wall_avg": f"{sum(secs) / len(secs):.0f}s" if secs else NM,
            "wall_p95": f"{p95(secs):.0f}s" if secs else NM,
        })
    return rows


def markdown(run_id: str, rows: list[dict], max_active: int, elapsed: float, cluster: dict | None) -> str:
    def fmt(v, f):
        return f.format(v) if v is not None else NM

    lines = [f"# SWE-bench Lite: {run_id}", "",
             "| model | tasks | resolved % | patch submitted % | errors (pod / LLM) | avg LLM cost/task | avg wall time | p95 wall time |",
             "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r['model']} | {r['tasks']} | {r['resolved']} | {r['submitted']} | {r['errors']} | "
              f"{r['cost']} | {r['wall_avg']} | {r['wall_p95']} |" for r in rows]
    c = cluster or {}
    lines += ["", "| run | value |", "|---|---|",
              f"| wall time (first launch to last Job done) | {elapsed / 60:.1f} min |",
              f"| max parallel Jobs | {max_active} |",
              f"| GPU utilisation (mean / max) | {fmt(c.get('gpu_util_mean'), '{:.0f}%')} / {fmt(c.get('gpu_util_max'), '{:.0f}%')} |",
              f"| total cluster cost for the run | {fmt(c.get('cluster_cost'), '${:.2f}')} |",
              f"| node-hours by type | {c.get('node_hours') or NM} |",
              "", "- resolved %: official SWE-bench harness (FAIL_TO_PASS and PASS_TO_PASS tests pass);"
              " `not measured` when run without `--evaluate`.",
              "- patch submitted %: agent produced a non-empty diff. A proxy, not correctness.",
              "- LLM cost: provider-reported via litellm; self-hosted vLLM is $0 here, its cost is the GPU node-hours.",
              "- wall time: Job creation to completion (Kubernetes timestamps), incl. scheduling and node scale-up.",
              f"- cluster cost: measured node-hours x live AWS prices + EKS control plane ${EKS_CONTROL_PLANE_HOURLY}/h"
              f" + NAT ${NAT_GATEWAY_HOURLY}/h list prices; excludes NAT data, EBS, LLM API spend."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8080")
    ap.add_argument("--api-key")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("-n", type=int, default=50, help="first N SWE-bench Lite test tasks")
    ap.add_argument("--instances", default="", help="comma-separated instance_ids (overrides -n)")
    ap.add_argument("--max-steps", type=int, default=30)
    ap.add_argument("--max-cost", type=float, default=2.0, help="per-run LLM cost cap (USD)")
    ap.add_argument("--job-deadline", type=int, default=1800, help="must match RUNNER_DEADLINE_SECONDS")
    ap.add_argument("--evaluate", action="store_true", help="run the official harness (local Docker)")
    ap.add_argument("--eval-workers", type=int, default=2)
    ap.add_argument("--prometheus", help="Prometheus URL for GPU util + cluster cost")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--out", default="bench-results")
    args = ap.parse_args()

    api = Api(args.api, args.api_key)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(args.n, [i for i in args.instances.split(",") if i])
    print(f"{len(tasks)} tasks x {len(args.models)} models", file=sys.stderr)

    run_id, final, max_active, elapsed = run_all(api, tasks, args.models, args)
    records = collect(api, run_id, tasks, args.models, final)
    if args.evaluate:
        evaluate(records, run_id, out_dir, args.eval_workers)
        post_verdicts(api, run_id, records)
    cluster = cluster_stats(args.prometheus, elapsed, args.region) if args.prometheus else None

    (out_dir / f"{run_id}.json").write_text(json.dumps({"records": records, "cluster": cluster,
                                                         "max_parallel_jobs": max_active, "elapsed_s": elapsed}, indent=1))
    report = markdown(run_id, summarize(records), max_active, elapsed, cluster)
    (out_dir / f"{run_id}.md").write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
