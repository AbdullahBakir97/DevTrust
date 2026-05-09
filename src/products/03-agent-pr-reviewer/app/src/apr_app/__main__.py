"""Entry point: `python -m apr_app` and the `apr-app` console script."""

from __future__ import annotations

import uvicorn

from apr_app.config import get_settings


def main() -> None:
    """Start uvicorn with sane defaults for development and production."""
    settings = get_settings()
    uvicorn.run(
        "apr_app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
