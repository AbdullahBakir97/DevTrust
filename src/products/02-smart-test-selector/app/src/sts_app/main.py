"""FastAPI application for sts-app.

Routes:

  GET  /                  - friendly landing JSON
  GET  /health            - liveness probe
  GET  /version           - service version + sts engine version
  POST /webhooks/github   - GitHub webhook receiver (sig-verified)

Production deploys typically front this with NGINX or a managed load
balancer that handles TLS termination and forwards the X-Hub-Signature-256
header verbatim.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from sts import __version__ as sts_version

from sts_app import __version__
from sts_app.config import Settings, get_settings
from sts_app.handlers import handle_pull_request
from sts_app.security import SIGNATURE_HEADER, verify

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Tests call this with an explicit Settings instance."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Smart Test Selector",
        description=(
            "GitHub App that runs the `sts` engine on PR events "
            "and posts the verdict as a sticky comment."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )
    # Stash settings on the app so dependencies / tests can read it cleanly.
    app.state.settings = settings

    router = APIRouter()

    @router.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "sts-app",
            "version": __version__,
            "sts_engine_version": sts_version,
        }

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/version")
    async def version() -> dict[str, str]:
        return {
            "sts_app": __version__,
            "sts_engine": sts_version,
        }

    @router.post("/webhooks/github")
    async def webhook(
        request: Request,
        x_github_event: str = Header(default=""),
        x_hub_signature_256: str = Header(default=""),
    ) -> dict[str, Any]:
        # We need the raw body for HMAC verification, so we read once
        # and parse JSON ourselves rather than relying on FastAPI's
        # Body parsing.
        raw = await request.body()

        secret_obj = settings.webhook_secret
        secret = secret_obj.get_secret_value() if secret_obj is not None else None

        if not verify(secret, raw, x_hub_signature_256 or request.headers.get(SIGNATURE_HEADER)):
            raise HTTPException(status_code=401, detail="invalid webhook signature")

        if secret is None:
            logger.warning(
                "Webhook signature verification SKIPPED - "
                "STS_APP_WEBHOOK_SECRET is not set. Do not run this in production."
            )

        # Parse JSON manually after we've used the raw bytes.
        import json as _json

        try:
            payload = _json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"bad JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be a JSON object")

        event = (x_github_event or "").lower()

        # We only handle pull_request events in v0.0.1 alpha.
        if event != "pull_request":
            return {"status": "ignored", "reason": f"event={event!r} not handled"}

        return await handle_pull_request(payload, settings)

    app.include_router(router)
    return app


# Module-level app for `uvicorn sts_app.main:app`
app = create_app()
