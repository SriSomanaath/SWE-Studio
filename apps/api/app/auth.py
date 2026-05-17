"""Optional API-key gate for write endpoints.

When `settings.api_keys` is empty, every request passes (default local-dev
behavior). When it's non-empty, any non-GET/HEAD/OPTIONS request must include
an `X-API-Key` header that matches one of the configured keys; otherwise the
middleware returns 401 before the route is invoked.

Read endpoints stay public so the trajectory pages, sitemap, and OG images
remain embeddable / shareable.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

# Routes that are read-only by intent but use POST/PUT/PATCH/DELETE-like verbs
# for non-mutating reasons — none today, but keep the constant for future use.
_PUBLIC_WRITE_ROUTES: frozenset[str] = frozenset()

# Routes that should bypass auth entirely (health probes, metrics scrapers).
_AUTH_BYPASS_PATHS: frozenset[str] = frozenset({"/health", "/metrics"})


async def api_key_middleware(request: Request, call_next):
    keys = [k for k in settings.api_keys if k]
    if not keys:
        return await call_next(request)

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)

    if request.url.path in _AUTH_BYPASS_PATHS:
        return await call_next(request)

    if request.url.path in _PUBLIC_WRITE_ROUTES:
        return await call_next(request)

    header = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if header and header in keys:
        return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"detail": "Missing or invalid X-API-Key for a write endpoint."},
    )
