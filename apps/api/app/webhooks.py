"""Outgoing webhook subscriptions + delivery.

Subscriptions live in the `webhooks` table. The delivery worker subscribes
to the in-process EventBus firehose; on each interesting event it filters the
list of webhooks, serializes a JSON payload, signs it with the per-subscription
secret, and POSTs to the URL with exponential backoff retry. Each attempt is
recorded in `webhook_deliveries` so the UI can show recent failures.

Event payload shape::

    {
      "id": "uuid",
      "event": "trajectory.resolved",
      "timestamp": 1779011584.346,
      "data": { …event-specific… }
    }
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

from app import db
from app.schemas import Webhook, WebhookDelivery
from app.streaming import bus, channel_firehose

logger = logging.getLogger(__name__)

_DELIVERY_TIMEOUT = 8.0
_MAX_ATTEMPTS = 4
_BACKOFF_BASE = 1.0  # seconds


# --- CRUD layer ------------------------------------------------------------


def _row_to_webhook(row: Any) -> Webhook:
    return Webhook(
        id=row["id"],
        url=row["url"],
        events=json.loads(row["events"]) if row["events"] else [],
        secret=row["secret"],
        active=bool(row["active"]),
        description=row["description"],
        created_at=row["created_at"],
    )


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL must use http or https")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="URL is missing a host")
    return url


def list_webhooks() -> list[Webhook]:
    rows = db.fetch_all(
        "SELECT id, url, events, secret, active, description, created_at "
        "FROM webhooks ORDER BY id DESC"
    )
    return [_row_to_webhook(r) for r in rows]


def get_webhook(webhook_id: int) -> Webhook:
    row = db.fetch_one(
        "SELECT id, url, events, secret, active, description, created_at "
        "FROM webhooks WHERE id = ?",
        (webhook_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")
    return _row_to_webhook(row)


def create_webhook(
    *,
    url: str,
    events: list[str],
    description: str | None,
) -> Webhook:
    url = _validate_url(url)
    secret = "whsec_" + secrets.token_urlsafe(24)
    now = time.time()
    with db.write_tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO webhooks (url, events, secret, active, description, created_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (url, json.dumps(events or []), secret, description, now),
        )
        new_id = cur.lastrowid
    return get_webhook(new_id)  # type: ignore[arg-type]


def update_webhook(
    webhook_id: int,
    *,
    url: str | None = None,
    events: list[str] | None = None,
    active: bool | None = None,
    description: str | None = None,
) -> Webhook:
    current = get_webhook(webhook_id)
    new_url = _validate_url(url) if url is not None else current.url
    new_events = events if events is not None else current.events
    new_active = current.active if active is None else bool(active)
    new_desc = description if description is not None else current.description
    with db.write_tx() as conn:
        conn.execute(
            """
            UPDATE webhooks
            SET url = ?, events = ?, active = ?, description = ?
            WHERE id = ?
            """,
            (new_url, json.dumps(new_events), int(new_active), new_desc, webhook_id),
        )
    return get_webhook(webhook_id)


def delete_webhook(webhook_id: int) -> None:
    with db.write_tx() as conn:
        cur = conn.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")


def list_deliveries(webhook_id: int, limit: int = 50) -> list[WebhookDelivery]:
    rows = db.fetch_all(
        """
        SELECT id, webhook_id, event, payload, status_code, success, attempts, error, created_at
        FROM webhook_deliveries
        WHERE webhook_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (webhook_id, limit),
    )
    return [
        WebhookDelivery(
            id=r["id"],
            webhook_id=r["webhook_id"],
            event=r["event"],
            payload=r["payload"],
            status_code=r["status_code"],
            success=bool(r["success"]),
            attempts=r["attempts"],
            error=r["error"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# --- Signing ---------------------------------------------------------------


def sign(secret: str, payload: bytes) -> str:
    """HMAC-SHA256 hex digest. Send in `X-Studio-Signature` as `sha256=<hex>`."""
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


# --- Delivery worker -------------------------------------------------------


async def _post_with_retry(
    url: str, secret: str, payload_bytes: bytes
) -> tuple[int, int | None, str | None]:
    """Return (attempts, status_code, error). Lazy-imports httpx to keep the
    base API surface dep-light for callers that don't enable webhooks."""
    import httpx  # noqa: WPS433

    last_error: str | None = None
    last_status: int | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
                res = await client.post(
                    url,
                    content=payload_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "swe-studio-webhook/1",
                        "X-Studio-Signature": sign(secret, payload_bytes),
                    },
                )
            last_status = res.status_code
            if 200 <= res.status_code < 300:
                return attempt, res.status_code, None
            last_error = f"HTTP {res.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
    return _MAX_ATTEMPTS, last_status, last_error


def _matches(events: list[str], event: str) -> bool:
    return not events or event in events


def _record_delivery(
    webhook_id: int,
    event: str,
    payload: str,
    *,
    status_code: int | None,
    success: bool,
    attempts: int,
    error: str | None,
) -> None:
    with db.write_tx() as conn:
        conn.execute(
            """
            INSERT INTO webhook_deliveries
                (webhook_id, event, payload, status_code, success, attempts, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (webhook_id, event, payload, status_code, int(success), attempts, error, time.time()),
        )


def _normalize_event(raw: dict[str, Any]) -> str | None:
    """Map an EventBus message onto a webhook event name.

    The bus emits low-level types like `update`/`new` per channel; we want
    higher-level names like `trajectory.resolved` for subscribers.
    """
    msg_type = raw.get("type", "")
    if msg_type == "new":
        return "trajectory.completed"
    if msg_type == "update":
        if (
            raw.get("exit_status_changed")
            and raw.get("exit_status")
            and raw.get("exit_status") != "running"
        ):
            if raw.get("eval_resolved") is True:
                return "trajectory.resolved"
            return "trajectory.completed"
        return "trajectory.updated"
    if msg_type == "summary_generated":
        return "summary.generated"
    if msg_type == "bookmark_created":
        return "bookmark.created"
    if msg_type == "showcase_created":
        return "showcase.created"
    return None


async def _dispatch(event: str, raw: dict[str, Any]) -> None:
    hooks = list_webhooks()
    if not hooks:
        return
    envelope = {
        "id": str(uuid.uuid4()),
        "event": event,
        "timestamp": time.time(),
        "data": raw,
    }
    payload_str = json.dumps(envelope, separators=(",", ":"))
    payload_bytes = payload_str.encode()

    async def _send(hook: Webhook) -> None:
        if not hook.active or not _matches(hook.events, event):
            return
        attempts, status_code, error = await _post_with_retry(hook.url, hook.secret, payload_bytes)
        success = 200 <= (status_code or 0) < 300
        _record_delivery(
            hook.id,
            event,
            payload_str,
            status_code=status_code,
            success=success,
            attempts=attempts,
            error=error if not success else None,
        )

    await asyncio.gather(*(_send(h) for h in hooks), return_exceptions=True)


async def delivery_worker() -> None:
    """Long-running task. Cancel to stop."""
    logger.info("Webhook delivery worker started")
    try:
        async for raw in bus.stream(channel_firehose()):
            event = _normalize_event(raw)
            if not event:
                continue
            try:
                await _dispatch(event, raw)
            except Exception:
                logger.exception("Webhook dispatch crashed for event %s", event)
    except asyncio.CancelledError:
        logger.info("Webhook delivery worker cancelled")
        raise


async def dispatch_for_test(event: str, data: dict[str, Any]) -> None:
    """Test hook — fire-and-await a single delivery without going through the bus."""
    await _dispatch(event, data)
