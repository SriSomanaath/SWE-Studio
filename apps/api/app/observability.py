"""Logging + metrics infrastructure.

JSON logs go to stdout so a container orchestrator can pick them up. Metrics
are hand-rolled in Prometheus text-exposition format (no extra dep) and
exposed at /metrics.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

# --- JSON log formatter ----------------------------------------------------


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Pick up custom fields injected via extra={"k": v}.
        for key, value in record.__dict__.items():
            if key in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            }:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


# --- Metrics registry ------------------------------------------------------


@dataclass
class _Counter:
    help: str
    samples: dict[tuple[tuple[str, str], ...], float] = field(
        default_factory=lambda: defaultdict(float)
    )


@dataclass
class _Gauge:
    help: str
    value: float = 0.0


@dataclass
class _Histogram:
    help: str
    buckets: tuple[float, ...]
    # Per-label-set state: (counts-per-bucket, sum, count)
    samples: dict[tuple[tuple[str, str], ...], tuple[list[int], float, int]] = field(
        default_factory=dict
    )


class MetricsRegistry:
    """Thread-safe Prometheus-compatible registry."""

    def __init__(self) -> None:
        self._counters: dict[str, _Counter] = {}
        self._gauges: dict[str, _Gauge] = {}
        self._histograms: dict[str, _Histogram] = {}
        self._lock = threading.Lock()

    # --- Counters

    def register_counter(self, name: str, help: str) -> None:
        with self._lock:
            self._counters.setdefault(name, _Counter(help=help))

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            counter = self._counters.get(name)
            if counter is None:
                counter = _Counter(help="(unregistered)")
                self._counters[name] = counter
            counter.samples[key] += value

    # --- Gauges

    def register_gauge(self, name: str, help: str) -> None:
        with self._lock:
            self._gauges.setdefault(name, _Gauge(help=help))

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            gauge = self._gauges.get(name)
            if gauge is None:
                gauge = _Gauge(help="(unregistered)")
                self._gauges[name] = gauge
            gauge.value = value

    # --- Histograms

    def register_histogram(self, name: str, help: str, buckets: tuple[float, ...]) -> None:
        with self._lock:
            self._histograms.setdefault(name, _Histogram(help=help, buckets=buckets))

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            hist = self._histograms.get(name)
            if hist is None:
                return  # silently drop — histograms must be registered upfront
            counts, total, n = hist.samples.get(key, ([0] * len(hist.buckets), 0.0, 0))
            counts = list(counts)
            for i, upper in enumerate(hist.buckets):
                if value <= upper:
                    counts[i] += 1
            hist.samples[key] = (counts, total + value, n + 1)

    # --- Render

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name, counter in sorted(self._counters.items()):
                lines.append(f"# HELP {name} {counter.help}")
                lines.append(f"# TYPE {name} counter")
                if not counter.samples:
                    lines.append(f"{name} 0")
                for labels, value in sorted(counter.samples.items()):
                    lines.append(f"{name}{_fmt_labels(labels)} {value}")
            for name, gauge in sorted(self._gauges.items()):
                lines.append(f"# HELP {name} {gauge.help}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {gauge.value}")
            for name, hist in sorted(self._histograms.items()):
                lines.append(f"# HELP {name} {hist.help}")
                lines.append(f"# TYPE {name} histogram")
                for labels, (counts, total, n) in sorted(hist.samples.items()):
                    label_str = _fmt_labels(labels)
                    # `observe()` increments every bucket whose upper bound
                    # exceeds the value, so counts[i] is already cumulative
                    # and matches the Prometheus convention as-is.
                    for i, upper in enumerate(hist.buckets):
                        bucket_labels = _add_label(label_str, "le", str(upper))
                        lines.append(f"{name}_bucket{bucket_labels} {counts[i]}")
                    inf_label = _add_label(label_str, "le", "+Inf")
                    lines.append(f"{name}_bucket{inf_label} {n}")
                    lines.append(f"{name}_sum{label_str} {total}")
                    lines.append(f"{name}_count{label_str} {n}")
        return "\n".join(lines) + "\n"


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{_escape(v)}"' for k, v in labels]
    return "{" + ",".join(parts) + "}"


def _add_label(existing: str, k: str, v: str) -> str:
    if not existing:
        return f'{{{k}="{_escape(v)}"}}'
    return existing[:-1] + f',{k}="{_escape(v)}"' + "}"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics = MetricsRegistry()

# Standard metric definitions — declared up front so they appear in /metrics
# even before the first event.
metrics.register_counter("api_requests_total", "Total HTTP requests served.")
metrics.register_histogram(
    "api_request_duration_seconds",
    "Latency of HTTP requests in seconds.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
metrics.register_counter("indexer_files_indexed_total", "Trajectory files indexed.")
metrics.register_counter("search_queries_total", "Search queries answered.")
metrics.register_counter("ai_summaries_total", "Trajectory summaries generated.")
metrics.register_gauge("trajectories_indexed", "Trajectories currently in the index.")
metrics.register_gauge("runs_indexed", "Runs currently in the index.")

# --- Agent run metrics -------------------------------------------------------
# Started at launch (routers/agent.py); finished when the trajectory lands
# (thread worker, or /ingest for k8s Jobs). Runs whose pod dies before
# ingesting never "finish" here; kube-state-metrics' kube_job_status_failed
# covers those on the dashboard, which keeps agent failures (exit_status) and
# infra failures (OOM, deadline, eviction) apart.
metrics.register_counter("agent_runs_started_total", "Agent runs launched.")
metrics.register_counter("agent_runs_finished_total", "Agent runs finished, by exit_status.")
metrics.register_counter("agent_cost_usd_total", "LLM spend of finished runs (USD).")
metrics.register_counter(
    "llm_tokens_total", "LLM tokens of finished runs, kind=prompt|completion|cached."
)
metrics.register_counter("agent_evals_total", "Evaluation verdicts recorded via /ingest?eval=.")
metrics.register_histogram(
    "agent_run_duration_seconds",
    "Launch-to-trajectory wall time; includes Job scheduling and node scale-up.",
    buckets=(30, 60, 120, 300, 600, 900, 1200, 1800, 3600),
)

# ponytail: in-memory, so a run launched before an API restart finishes
# without a duration sample; counters are unaffected. Persist t0 if it matters.
_run_started: dict[tuple[str, str], tuple[float, str]] = {}


def run_started(run_id: str, trajectory_id: str, model: str, executor: str) -> None:
    _run_started[(run_id, trajectory_id)] = (time.monotonic(), model)
    metrics.inc("agent_runs_started_total", model=model, executor=executor)


def run_finished(run_id: str, trajectory_id: str, info: dict) -> None:
    t0, launched_model = _run_started.pop((run_id, trajectory_id), (None, "unknown"))
    model = str(info.get("model") or launched_model)
    stats = info.get("model_stats") or {}
    metrics.inc(
        "agent_runs_finished_total",
        model=model,
        exit_status=str(info.get("exit_status") or "unknown"),
    )
    metrics.inc("agent_cost_usd_total", float(stats.get("instance_cost") or 0), model=model)
    for kind, key in (
        ("prompt", "tokens_sent"),
        ("completion", "tokens_received"),
        ("cached", "tokens_cached"),
    ):
        metrics.inc("llm_tokens_total", float(stats.get(key) or 0), model=model, kind=kind)
    if t0 is not None:
        metrics.observe("agent_run_duration_seconds", time.monotonic() - t0, model=model)
