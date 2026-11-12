"""Run each agent trajectory as a Kubernetes `batch/v1` Job.

Opt-in via AGENT_EXECUTOR=k8s. The Job *is* the sandbox: the agent's `bash`
tool runs as a subprocess inside a throwaway, non-root, read-only-rootfs pod
with no Kubernetes API token, then POSTs the finished `.traj` back to the
API's `/ingest` endpoint. No shared filesystem between API and runners, so
runners can land on any node.

Why Jobs and not a Deployment/worker queue: a run is finite work that must
run exactly once and then go away. Jobs give us that (backoffLimit=0,
activeDeadlineSeconds, ttlSecondsAfterFinished) plus per-run resource
limits and isolation, with the scheduler doing the placement.

The manifest is a plain dict (the client accepts dicts), so building it needs
no `kubernetes` import and is unit-testable without a cluster.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.config import settings

# Pods the NetworkPolicy in deploy/k8s/base.yaml locks down.
RUNNER_LABELS = {"app": "swe-studio", "component": "agent-runner"}

# Kubernetes label values: <=63 chars, alnum at both ends, [A-Za-z0-9._-].
_LABEL_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]{0,61}[A-Za-z0-9])?$")


def _label(value: str) -> str:
    """Coerce a model name like `openai/Qwen/Qwen2.5-Coder-7B` into a label."""
    v = re.sub(r"[^A-Za-z0-9._-]", "_", value)[:63].strip("._-")
    return v or "unknown"


def job_name(run_id: str, trajectory_id: str) -> str:
    # Job names must be lowercase DNS-1123; our ids may contain uppercase,
    # dots and underscores, so hash instead of sanitising (no collisions).
    digest = hashlib.sha1(f"{run_id}/{trajectory_id}".encode()).hexdigest()[:16]
    return f"agent-{digest}"


def build_job(
    *,
    run_id: str,
    trajectory_id: str,
    model: str,
    problem: str,
    repo_url: str,
    repo_ref: str,
    max_steps: int,
    max_cost_usd: float,
) -> dict[str, Any]:
    if not _LABEL_RE.match(run_id):
        raise ValueError("run_id must be a valid label value (<=63 chars, alnum ends)")

    labels = {**RUNNER_LABELS, "run-id": run_id, "model": _label(model)}
    # The pod has a read-only root fs; these two emptyDirs are the only
    # writable paths. /tmp holds HOME, git config and the local .traj.
    mounts = [
        {"name": "work", "mountPath": "/work"},
        {"name": "tmp", "mountPath": "/tmp"},
    ]
    container_security = {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    common_env = [{"name": "HOME", "value": "/tmp"}]

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name(run_id, trajectory_id),
            "namespace": settings.k8s_namespace,
            "labels": labels,
            # Full ids live in annotations: no label length/charset limits.
            "annotations": {"swe-studio/trajectory-id": trajectory_id},
        },
        "spec": {
            # A failed agent run is a result, not a crash to retry: retrying
            # would double LLM spend and overwrite the first trajectory.
            "backoffLimit": 0,
            # ...but a spot reclaim / node drain is not the agent's fault:
            # pods killed by a disruption don't count toward backoffLimit, so
            # the Job just reruns on a fresh node.
            "podFailurePolicy": {
                "rules": [{"action": "Ignore", "onPodConditions": [{"type": "DisruptionTarget"}]}]
            },
            "activeDeadlineSeconds": settings.runner_deadline_seconds,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    # On EKS: land on the Karpenter cpu-spot pool, not the
                    # small on-demand system nodes the API lives on.
                    **(
                        {"nodeSelector": {"swe-studio/pool": settings.runner_pool}}
                        if settings.runner_pool
                        else {}
                    ),
                    # The agent runs arbitrary shell; it must not inherit a
                    # token that can talk to the Kubernetes API.
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    # Clone in an init container so the agent container starts
                    # with the repo ready. Values go through env, never string
                    # interpolation, so a hostile ref can't inject shell.
                    "initContainers": [
                        {
                            "name": "clone",
                            "image": settings.runner_image,
                            "imagePullPolicy": "IfNotPresent",
                            "command": [
                                "sh",
                                "-c",
                                "git init -q /work/repo && cd /work/repo"
                                ' && git remote add origin "$REPO_URL"'
                                ' && git fetch -q --depth 1 origin "$REPO_REF"'
                                " && git checkout -q FETCH_HEAD",
                            ],
                            "env": [
                                *common_env,
                                {"name": "REPO_URL", "value": repo_url},
                                {"name": "REPO_REF", "value": repo_ref},
                            ],
                            "volumeMounts": mounts,
                            "securityContext": container_security,
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"},
                            },
                        }
                    ],
                    "containers": [
                        {
                            "name": "agent",
                            "image": settings.runner_image,
                            "imagePullPolicy": "IfNotPresent",
                            # -P: don't put the cwd (the cloned repo) on sys.path.
                            # Otherwise a repo shipping e.g. `requests/` shadows
                            # the runner's own deps (found on psf/requests).
                            "command": ["python", "-P", "-m", "app.agent.job_main"],
                            "workingDir": "/work/repo",
                            "env": [
                                *common_env,
                                {"name": "RUN_ID", "value": run_id},
                                {"name": "TRAJECTORY_ID", "value": trajectory_id},
                                {"name": "MODEL", "value": model},
                                {"name": "PROBLEM", "value": problem},
                                {"name": "MAX_STEPS", "value": str(max_steps)},
                                {"name": "MAX_COST_USD", "value": str(max_cost_usd)},
                                {"name": "INGEST_URL", "value": settings.runner_ingest_url},
                            ],
                            # LLM provider keys + STUDIO_API_KEY. Optional so
                            # a keyless local model still works.
                            "envFrom": [
                                {"secretRef": {"name": settings.runner_secret, "optional": True}}
                            ],
                            "volumeMounts": mounts,
                            "securityContext": container_security,
                            "resources": {
                                "requests": {"cpu": "250m", "memory": "512Mi"},
                                "limits": {"cpu": "1", "memory": "1Gi"},
                            },
                        }
                    ],
                    "volumes": [
                        {"name": "work", "emptyDir": {"sizeLimit": "2Gi"}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "256Mi"}},
                    ],
                },
            },
        },
    }


def _batch_api():
    from kubernetes import client, config  # lazy: only needed in k8s mode

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()  # running the API outside the cluster
    return client.BatchV1Api()


def create_job(**kwargs: Any) -> str:
    body = build_job(**kwargs)
    _batch_api().create_namespaced_job(namespace=settings.k8s_namespace, body=body)
    return body["metadata"]["name"]


def ensure_capacity(n: int) -> None:
    """Refuse new runs when `n` more would exceed RUNNER_MAX_CONCURRENT.

    Why not KEDA: KEDA ScaledJob turns queue depth into Jobs, but we create
    Jobs directly per request, and Karpenter already turns Pending pods into
    nodes. The only missing piece is a ceiling on LLM spend + cluster size,
    which this count gives (the NodePool `limits` are the hard backstop).
    ponytail: count-then-create is racy across concurrent requests/replicas;
    move to a DB-backed counter or a queue if the API scales out.
    """
    jobs = _batch_api().list_namespaced_job(
        namespace=settings.k8s_namespace, label_selector="app=swe-studio,component=agent-runner"
    )
    active = sum(1 for j in jobs.items if not (j.status.succeeded or j.status.failed))
    if active + n > settings.runner_max_concurrent:
        raise CapacityError(
            f"{active} runs active, limit {settings.runner_max_concurrent}; retry later"
        )


class CapacityError(RuntimeError):
    pass


def job_phase(status: Any) -> str:
    """Map a V1JobStatus to pending|running|succeeded|failed.

    `active` counts pods that exist but may still be pulling/cloning; `ready`
    says the agent container is actually up.
    """
    if status.succeeded:
        return "succeeded"
    if status.failed:
        return "failed"
    if status.ready:
        return "running"
    return "pending"


def _seconds(job: Any) -> float | None:
    """Job creation to completion/failure, from Kubernetes' own timestamps.

    Includes scheduling, node scale-up and the clone, i.e. the wall time a
    user actually waits. None while the Job is still running.
    """
    st = job.status
    end = st.completion_time or next(
        (
            c.last_transition_time
            for c in st.conditions or []
            if c.type == "Failed" and c.status == "True"
        ),
        None,
    )
    return (end - job.metadata.creation_timestamp).total_seconds() if end else None


def run_status(run_id: str) -> dict[str, dict[str, Any]]:
    """trajectory_id -> {phase, seconds} for every Job of a run."""
    jobs = _batch_api().list_namespaced_job(
        namespace=settings.k8s_namespace,
        label_selector=f"app=swe-studio,component=agent-runner,run-id={run_id}",
    )
    return {
        (j.metadata.annotations or {}).get("swe-studio/trajectory-id", j.metadata.name): {
            "phase": job_phase(j.status),
            "seconds": _seconds(j),
        }
        for j in jobs.items
    }
