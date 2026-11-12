import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "scripts" / "bench_swebench.py"
_spec = importlib.util.spec_from_file_location("bench_swebench", _path)
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


def rec(model, resolved, patch, cost, seconds, ingested=True):
    return {
        "model": model,
        "resolved": resolved,
        "patch": patch,
        "cost": cost,
        "seconds": seconds,
        "ingested": ingested,
    }


def test_summary_math_and_never_invents_numbers() -> None:
    records = [
        rec("claude", True, "diff", 0.40, 100),
        rec("claude", False, "diff", 0.60, 300),
        rec("claude", None, "diff", None, None, ingested=False),  # pod died: no data
        rec("qwen", None, "", 0.0, 50),  # not evaluated
    ]
    claude, qwen = bench.summarize(records)
    assert claude["resolved"] == "50.0% (1/2)"  # unjudged task excluded, and the count says so
    assert (
        claude["cost"] == "$0.5000"
        and claude["wall_avg"] == "200s"
        and claude["wall_p95"] == "300s"
    )
    assert claude["errors"] == "1 / 0" and claude["submitted"] == "100.0%"
    assert qwen["resolved"] == bench.NM and qwen["submitted"] == "0.0%"
    assert bench.p95(list(range(1, 101))) == 95

    md = bench.markdown("bench-x", [claude, qwen], max_active=4, elapsed=600, cluster=None)
    assert "| GPU utilisation (mean / max) | not measured / not measured |" in md
    assert "| total cluster cost for the run | not measured |" in md
