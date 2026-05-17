from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import dataset as svc
from app import db

router = APIRouter(prefix="/runs", tags=["dataset"])


@router.get("/{run_id}/export.jsonl")
def export_jsonl(run_id: str) -> StreamingResponse:
    # Validate up front so 404s aren't raised mid-stream (after headers flush).
    if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return StreamingResponse(
        svc.iter_jsonl(run_id),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{run_id}.jsonl"',
        },
    )


@router.get("/{run_id}/manifest.json")
def export_manifest(run_id: str) -> dict[str, Any]:
    return svc.manifest(run_id)
