from app.agent.k8s import build_job, job_name


def test_build_job_is_locked_down() -> None:
    job = build_job(
        run_id="ensemble-20261111T120000",
        trajectory_id="openai_Qwen_Qwen2.5-Coder-7B-20261111T120000",
        model="openai/Qwen/Qwen2.5-Coder-7B",
        problem="fix it; rm -rf / $(whoami)",
        repo_url="https://github.com/octocat/Hello-World",
        repo_ref="master",
        max_steps=5,
        max_cost_usd=1.0,
    )
    spec = job["spec"]
    pod = spec["template"]["spec"]
    agent, clone = pod["containers"][0], pod["initContainers"][0]

    assert (
        spec["backoffLimit"] == 0
        and spec["activeDeadlineSeconds"]
        and spec["ttlSecondsAfterFinished"]
    )
    assert pod["restartPolicy"] == "Never" and pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    for c in (agent, clone):
        assert c["securityContext"]["readOnlyRootFilesystem"] is True
        assert c["securityContext"]["allowPrivilegeEscalation"] is False
        assert c["resources"]["limits"]["memory"]
    # NetworkPolicy selects on these; model label must be sanitised.
    labels = spec["template"]["metadata"]["labels"]
    assert (
        labels["component"] == "agent-runner" and labels["model"] == "openai_Qwen_Qwen2.5-Coder-7B"
    )
    # The cloned repo must not shadow the runner's imports.
    assert agent["command"][:2] == ["python", "-P"]
    # User input travels as env, never spliced into the shell command.
    assert "Hello-World" not in " ".join(clone["command"])
    assert {"name": "PROBLEM", "value": "fix it; rm -rf / $(whoami)"} in agent["env"]
    # DNS-1123 job name, stable per (run, trajectory).
    assert job["metadata"]["name"] == job_name(
        "ensemble-20261111T120000", "openai_Qwen_Qwen2.5-Coder-7B-20261111T120000"
    )
    assert job["metadata"]["name"].islower() and len(job["metadata"]["name"]) <= 63


def test_capacity_limit_counts_only_unfinished_jobs(monkeypatch) -> None:
    from types import SimpleNamespace as NS

    import pytest

    from app.agent import k8s

    def job(**status):
        return NS(status=NS(succeeded=status.get("succeeded"), failed=status.get("failed")))

    jobs = [job(), job(), job(succeeded=1), job(failed=1)]  # 2 active
    monkeypatch.setattr(
        k8s, "_batch_api", lambda: NS(list_namespaced_job=lambda **_: NS(items=jobs))
    )
    # k8s.settings, not app.config.settings: other tests reload app.config.
    monkeypatch.setattr(k8s.settings, "runner_max_concurrent", 4)

    k8s.ensure_capacity(2)  # 2 + 2 == 4: allowed
    with pytest.raises(k8s.CapacityError):
        k8s.ensure_capacity(3)  # an ensemble that would overshoot is refused whole


def test_ingest_mirrors_traj_and_results_to_s3(monkeypatch, tmp_path) -> None:
    import sys
    from types import SimpleNamespace as NS

    from fastapi.testclient import TestClient

    from app.routers import ingest

    uploads = []
    fake_boto3 = NS(client=lambda name: NS(upload_file=lambda f, b, k: uploads.append((b, k))))
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setattr(ingest.settings, "trajectories_bucket", "bench-bucket")
    monkeypatch.setattr(ingest.settings, "trajectories_dir", tmp_path)
    monkeypatch.setattr(ingest.settings, "api_keys", [])
    monkeypatch.setattr(ingest.indexer, "_reindex_run", lambda _: None)

    from app.main import app

    r = TestClient(app).post(
        "/ingest/runs/r1/trajectories/t1?eval=resolved",
        json={"history": [], "trajectory": [], "info": {"exit_status": "submitted"}},
    )
    assert r.status_code == 201
    assert (tmp_path / "r1" / "t1.traj").exists()  # local copy stays the source of truth
    assert uploads == [("bench-bucket", "r1/t1.traj"), ("bench-bucket", "r1/results.json")]
