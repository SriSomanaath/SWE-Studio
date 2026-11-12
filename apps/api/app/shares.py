"""Public signed share URLs.

A share is a token that lets anyone open a specific run / trajectory /
showcase without authenticating. The token is a URL-safe random 16-byte ID
authenticated by a row in the `shares` table — the server is the source of
truth, so there's no JWT-style replay-after-rotation risk. Tokens can be
TTL-bounded and revoked at any time.
"""

from __future__ import annotations

import secrets
import time

from fastapi import HTTPException

from app import db
from app.config import settings
from app.schemas import ResolvedShare, Share

_VALID_KINDS: set[str] = {"run", "trajectory", "showcase"}


def _ensure_secret_configured() -> None:
    if not settings.app_secret:
        raise HTTPException(
            status_code=503,
            detail="Share links are disabled — set APP_SECRET on the API to enable.",
        )


def _generate_token() -> str:
    # 16 bytes → 22-char urlsafe-base64. Plenty of entropy for short links.
    return secrets.token_urlsafe(16)


def _share_url(token: str) -> str:
    base = settings.site_url.rstrip("/")
    return f"{base}/s/{token}"


def _row_to_share(row: object, *, with_url: bool = False) -> Share:
    d = dict(row)  # type: ignore[arg-type]
    s = Share(
        token=d["token"],
        kind=d["kind"],
        target_run_id=d["target_run_id"],
        target_traj_id=d["target_traj_id"],
        target_slug=d["target_slug"],
        description=d["description"],
        author=d["author"],
        created_at=d["created_at"],
        expires_at=d["expires_at"],
        revoked=bool(d["revoked"]),
    )
    if with_url:
        s.url = _share_url(s.token)
    return s


def _validate_target(
    kind: str,
    run_id: str | None,
    trajectory_id: str | None,
    slug: str | None,
) -> tuple[str | None, str | None, str | None]:
    if kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {sorted(_VALID_KINDS)}")
    if kind == "run":
        if not run_id:
            raise HTTPException(status_code=400, detail="kind=run requires run_id")
        if not db.fetch_one("SELECT 1 FROM runs WHERE id = ?", (run_id,)):
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return run_id, None, None
    if kind == "trajectory":
        if not run_id or not trajectory_id:
            raise HTTPException(
                status_code=400, detail="kind=trajectory requires run_id + trajectory_id"
            )
        if not db.fetch_one(
            "SELECT 1 FROM trajectories WHERE run_id = ? AND id = ?",
            (run_id, trajectory_id),
        ):
            raise HTTPException(
                status_code=404, detail=f"Trajectory '{trajectory_id}' not found"
            )
        return run_id, trajectory_id, None
    if kind == "showcase":
        if not slug:
            raise HTTPException(status_code=400, detail="kind=showcase requires slug")
        if not db.fetch_one("SELECT 1 FROM showcase WHERE slug = ?", (slug,)):
            raise HTTPException(status_code=404, detail=f"Showcase '{slug}' not found")
        return None, None, slug
    raise AssertionError("unreachable")


def create_share(
    *,
    kind: str,
    run_id: str | None,
    trajectory_id: str | None,
    slug: str | None,
    description: str | None,
    ttl_seconds: int | None,
    author: str | None,
) -> Share:
    _ensure_secret_configured()
    rid, tid, sl = _validate_target(kind, run_id, trajectory_id, slug)

    if ttl_seconds is not None:
        if ttl_seconds <= 0 or ttl_seconds > 60 * 60 * 24 * 365:
            raise HTTPException(
                status_code=400,
                detail="ttl_seconds must be 1–31536000 (1 year max) or omit for no expiry",
            )

    now = time.time()
    expires_at = (now + ttl_seconds) if ttl_seconds else None
    token = _generate_token()
    auth = (author or "").strip()[:64] or "anonymous"
    desc = (description or "").strip()[:300] or None

    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO shares
                (token, kind, target_run_id, target_traj_id, target_slug,
                 description, author, created_at, expires_at, revoked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (token, kind, rid, tid, sl, desc, auth, now, expires_at),
        )

    return get_share(token, include_url=True, include_revoked=True)


def list_shares() -> list[Share]:
    rows = db.fetch_all(
        "SELECT * FROM shares ORDER BY created_at DESC LIMIT 200"
    )
    return [_row_to_share(r, with_url=True) for r in rows]


def get_share(token: str, *, include_url: bool = False, include_revoked: bool = False) -> Share:
    row = db.fetch_one("SELECT * FROM shares WHERE token = ?", (token,))
    if not row:
        raise HTTPException(status_code=404, detail="Share not found")
    share = _row_to_share(row, with_url=include_url)
    if not include_revoked and share.revoked:
        raise HTTPException(status_code=410, detail="Share has been revoked")
    return share


def revoke_share(token: str) -> None:
    row = db.fetch_one("SELECT token FROM shares WHERE token = ?", (token,))
    if not row:
        raise HTTPException(status_code=404, detail="Share not found")
    with db.write_tx() as conn:
        conn.execute("UPDATE shares SET revoked = 1 WHERE token = ?", (token,))


def resolve(token: str) -> ResolvedShare:
    """Used by the public /s/{token} route. Returns the target descriptor
    or raises 404/410 if revoked/expired."""
    share = get_share(token, include_revoked=False)
    if share.expires_at is not None and share.expires_at < time.time():
        raise HTTPException(status_code=410, detail="Share has expired")
    return ResolvedShare(
        token=share.token,
        kind=share.kind,
        expires_at=share.expires_at,
        description=share.description,
        target_run_id=share.target_run_id,
        target_traj_id=share.target_traj_id,
        target_slug=share.target_slug,
    )
