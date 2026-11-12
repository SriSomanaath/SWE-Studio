"""Generate a HuggingFace-Datasets-compatible export for a Studio run.

The output directory contains everything needed to push the run to the Hub:

    out/
      README.md            # HF dataset card with YAML frontmatter
      dataset_info.json    # schema + counts + size
      data/run.jsonl       # one trajectory per line (HF reads .jsonl natively)
      manifest.json        # Studio-side provenance

Usage::

    python -m app.tools.dataset_card --run sample-run-001 --output ./hf-card
    cd ./hf-card
    huggingface-cli upload <your-username>/<your-dataset-name> . .
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app import __version__, dataset

_FIELD_FEATURES: dict[str, dict[str, str]] = {
    "run_id": {"dtype": "string", "_type": "Value"},
    "instance_id": {"dtype": "string", "_type": "Value"},
    "problem_statement": {"dtype": "string", "_type": "Value"},
    "exit_status": {"dtype": "string", "_type": "Value"},
    "resolved": {"dtype": "bool", "_type": "Value"},
    "submitted": {"dtype": "bool", "_type": "Value"},
    "completed": {"dtype": "bool", "_type": "Value"},
    "submission": {"dtype": "string", "_type": "Value"},
    "step_count": {"dtype": "int32", "_type": "Value"},
    "instance_cost": {"dtype": "float64", "_type": "Value"},
    "tokens_sent": {"dtype": "int32", "_type": "Value"},
    "tokens_received": {"dtype": "int32", "_type": "Value"},
    "api_calls": {"dtype": "int32", "_type": "Value"},
}


def _features() -> dict[str, Any]:
    features = dict(_FIELD_FEATURES)
    features["steps"] = {
        "_type": "Sequence",
        "feature": {
            "thought": {"dtype": "string", "_type": "Value"},
            "action": {"dtype": "string", "_type": "Value"},
            "observation": {"dtype": "string", "_type": "Value"},
            "response": {"dtype": "string", "_type": "Value"},
        },
    }
    return features


def _readme(run_id: str, manifest: dict[str, Any], pretty_name: str | None) -> str:
    n = manifest["record_count"]
    resolved = manifest["stats"]["resolved_count"]
    pass_rate = manifest["stats"]["pass_rate"]
    pass_pct = f"{pass_rate * 100:.1f}%" if pass_rate is not None else "—"
    total_cost = manifest["stats"]["total_cost_usd"]
    pretty = pretty_name or f"SWE Studio · {run_id}"

    return f"""---
pretty_name: {json.dumps(pretty)}
tags:
  - swe-studio
  - agent-benchmark
  - coding-agents
  - agent-trajectories
  - llm
task_categories:
  - text-generation
  - other
language:
  - en
size_categories:
  - n<1K
license: other
configs:
  - config_name: default
    data_files: data/run.jsonl
---

# {pretty}

Coding-agent trajectories exported from a [SWE Studio](https://github.com/your-org/SWE-Studio) run.

## Summary

| Metric | Value |
|---|---|
| Trajectories | {n} |
| Resolved | {resolved} ({pass_pct}) |
| Total cost (USD) | ${total_cost:.2f} |
| Run id | `{run_id}` |
| Studio version | `{__version__}` |
| Generated | `{manifest["generated_at"]}` |

## Schema

Each row is a self-contained trajectory:

| Field | Type | Description |
|---|---|---|
| `run_id` | string | SWE Studio run identifier |
| `instance_id` | string | Per-instance identifier |
| `problem_statement` | string | The user-facing task |
| `exit_status` | string | Agent exit code (`submitted`, `exit_forfeit`, …) |
| `resolved` / `submitted` / `completed` | bool | evaluation flags |
| `submission` | string | The final unified-diff patch |
| `step_count` | int | Number of agent steps |
| `instance_cost` | float | Cost in USD |
| `tokens_sent` / `tokens_received` / `api_calls` | int | Per-instance token + API totals |
| `steps` | list | One record per step with `thought`, `action`, `observation`, `response` |

## Loading

```python
from datasets import load_dataset
ds = load_dataset("<your-org>/<your-dataset>")
```

## Provenance

This dataset was produced by `python -m app.tools.dataset_card` from a Studio
run. The full per-instance manifest is available alongside as `manifest.json`.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Studio run id to export")
    parser.add_argument(
        "--output", required=True, type=Path, help="Output directory (will be created)"
    )
    parser.add_argument("--pretty-name", default=None, help="HF pretty_name override")
    args = parser.parse_args(argv)

    out: Path = args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(exist_ok=True)

    # JSONL: stream straight from the dataset module — no HTTP, no extra deps.
    jsonl_path = out / "data" / "run.jsonl"
    record_count = 0
    with jsonl_path.open("wb") as fh:
        for line in dataset.iter_jsonl(args.run):
            fh.write(line)
            record_count += 1

    manifest = dataset.manifest(args.run)
    manifest["record_count"] = record_count
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    dataset_info = {
        "features": _features(),
        "splits": {
            "train": {
                "name": "train",
                "num_examples": record_count,
            }
        },
        "config_name": "default",
        "description": f"SWE Studio run {args.run} ({record_count} trajectories)",
    }
    (out / "dataset_info.json").write_text(json.dumps(dataset_info, indent=2))

    (out / "README.md").write_text(_readme(args.run, manifest, args.pretty_name))

    print(f"wrote {record_count} records to {jsonl_path}", file=sys.stderr)
    print(f"dataset card ready: {out}", file=sys.stderr)
    print("next: huggingface-cli upload <user>/<dataset> . .", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
