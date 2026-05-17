"""HTTP client around the SWE Studio /ingest endpoint."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class StudioClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        *,
        author: Optional[str] = None,
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.author = author
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "StudioClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def ingest(
        self,
        run_id: str,
        trajectory_id: str,
        payload: dict[str, Any],
        *,
        eval: Optional[str] = None,
    ) -> dict[str, Any]:
        params = {"eval": eval} if eval else None
        res = self._client.post(
            f"/ingest/runs/{run_id}/trajectories/{trajectory_id}",
            params=params,
            json=payload,
        )
        res.raise_for_status()
        return res.json()

    def annotate(
        self,
        run_id: str,
        trajectory_id: str,
        body: str,
        step_index: int = -1,
    ) -> dict[str, Any]:
        headers = {"X-Author": self.author} if self.author else {}
        res = self._client.post(
            f"/runs/{run_id}/trajectories/{trajectory_id}/annotations",
            json={"step_index": step_index, "body": body},
            headers=headers,
        )
        res.raise_for_status()
        return res.json()
