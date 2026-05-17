from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app import webhooks as svc
from app.schemas import Webhook, WebhookCreate, WebhookDelivery, WebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=list[Webhook])
def get_webhooks() -> list[Webhook]:
    return svc.list_webhooks()


@router.post("", response_model=Webhook, status_code=201)
def post_webhook(payload: WebhookCreate) -> Webhook:
    return svc.create_webhook(
        url=payload.url,
        events=payload.events,
        description=payload.description,
    )


@router.get("/{webhook_id}", response_model=Webhook)
def get_webhook(webhook_id: int) -> Webhook:
    return svc.get_webhook(webhook_id)


@router.patch("/{webhook_id}", response_model=Webhook)
def patch_webhook(webhook_id: int, payload: WebhookUpdate) -> Webhook:
    return svc.update_webhook(
        webhook_id,
        url=payload.url,
        events=payload.events,
        active=payload.active,
        description=payload.description,
    )


@router.delete("/{webhook_id}", status_code=204)
def delete_webhook(webhook_id: int) -> None:
    svc.delete_webhook(webhook_id)


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDelivery])
def get_deliveries(
    webhook_id: int,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[WebhookDelivery]:
    return svc.list_deliveries(webhook_id, limit)
