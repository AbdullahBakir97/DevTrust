"""Entry point: `python -m sts_app` and the `sts-app` console script.

Runs the FastAPI app under uvicorn. Configuration is via environment
variables (see `sts_app.config`).
"""

from __future__ import annotations

import uvicorn

from sts_app.config import get_settings


def main() -> None:
    """Start uvicorn with sane defaults for development and production."""
    settings = get_settings()
    uvicorn.run(
        "sts_app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
