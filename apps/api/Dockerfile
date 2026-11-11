FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # Runner Jobs start in /work/repo, not /app; keep `app` importable.
    PYTHONPATH=/app

# git: the k8s runner clones the target repo and `submit` runs `git diff`.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# One image serves both roles: the API (default CMD) and the agent runner
# (k8s Job overrides the command with `python -m app.agent.job_main`).
RUN pip install --upgrade pip && pip install ".[agent,k8s,s3]"

COPY app ./app

# No USER here: docker-compose's existing root-owned /data volume must keep
# working. In k8s the pod securityContext forces uid 1000 / non-root.

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
