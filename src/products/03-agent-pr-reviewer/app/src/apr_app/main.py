"""FastAPI application for apr-app.

Routes:

  GET  /                  - friendly landing JSON
  GET  /health            - liveness probe
  GET  /version           - service version + apr engine version
  POST /webhooks/github   - GitHub webhook receiver (sig-verified)
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from apr import __version__ as apr_version
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request

from apr_app import __version__
from apr_app.config import Settings, get_settings
from apr_app.handlers import handle_pull_request
from apr_app.security import SIGNATURE_HEADER, verify

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Tests pass an explicit Settings."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Agent-PR Reviewer",
        description=(
            "GitHub App that runs the `apr` engine on PR events and "
            "posts findings as a sticky comment."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = settings

    router = APIRouter()

    @router.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "apr-app",
            "version": __version__,
            "apr_engine_version": apr_version,
        }

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/version")
    async def version() -> dict[str, str]:
        return {
            "apr_app": __version__,
            "apr_engine": apr_version,
        }

    @router.post("/webhooks/github")
    async def webhook(
        request: Request,
        x_github_event: str = Header(default=""),
        x_hub_signature_256: str = Header(default=""),
    ) -> dict[str, Any]:
        raw = await request.body()

        secret_obj = settings.webhook_secret
        secret = secret_obj.get_secret_value() if secret_obj is not None else None

        if not verify(
            secret,
            raw,
            x_hub_signature_256 or request.headers.get(SIGNATURE_HEADER),
        ):
            raise HTTPException(status_code=401, detail="invalid webhook signature")

        if secret is None:
            logger.warning(
                "Webhook signature verification SKIPPED - "
                "APR_APP_WEBHOOK_SECRET is not set. Do not run this in production."
            )

        try:
            payload = _json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"bad JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be a JSON object")

        event = (x_github_event or "").lower()

        # We only handle pull_request events in v0.0.1.
        if event != "pull_request":
            return {"status": "ignored", "reason": f"event={event!r} not handled"}

        return await handle_pull_request(payload, settings)

    app.include_router(router)
    return app


# Module-level app for `uvicorn apr_app.main:app`
app = create_app()
