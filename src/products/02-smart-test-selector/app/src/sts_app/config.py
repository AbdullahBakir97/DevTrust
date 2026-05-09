"""Environment-driven settings for the sts-app service.

We use `pydantic-settings` so config is typed, validated, and easy to
override via env vars or a .env file. Every setting is namespaced with
the `STS_APP_` prefix to avoid collisions with other services.

Examples:
  STS_APP_HOST=0.0.0.0
  STS_APP_PORT=8080
  STS_APP_WEBHOOK_SECRET=...      (REQUIRED in production)
  STS_APP_GITHUB_TOKEN=ghp_...    (REQUIRED to read PRs and post comments)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration. All fields have safe development defaults."""

    model_config = SettingsConfigDict(
        env_prefix="STS_APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---------------------------------------------------------
    host: str = Field(default="127.0.0.1", description="Address to bind.")
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    reload: bool = Field(default=False, description="Auto-reload on code change.")

    # --- GitHub integration ---------------------------------------------
    # PRODUCTION: GitHub App auth via JWT-signed installation tokens.
    # Set BOTH `app_id` and `private_key_pem` to enable. Dev mode
    # falls back to `github_token` (PAT) when these are unset.
    app_id: str | None = Field(
        default=None,
        description="Numeric GitHub App ID (visible on the App settings page).",
    )
    private_key_pem: SecretStr | None = Field(
        default=None,
        description="The App's RSA private key in PEM form (paste contents).",
    )
    github_token: SecretStr | None = Field(
        default=None,
        description=(
            "DEV ONLY: GitHub PAT with repo scope. Ignored when app_id + private_key_pem are set."
        ),
    )
    github_api_url: str = Field(
        default="https://api.github.com",
        description="Base URL for the GitHub REST API. Override for GHES.",
    )

    # --- Webhook security ----------------------------------------------
    webhook_secret: SecretStr | None = Field(
        default=None,
        description=(
            "HMAC secret configured in the GitHub webhook settings. "
            "If unset, signature verification is skipped (dev mode only)."
        ),
    )

    # --- Comment behavior ----------------------------------------------
    sticky_comment_marker: str = Field(
        default="<!-- sts-app:sticky -->",
        description=(
            "Hidden HTML comment used to identify the bot's sticky comment "
            "on a PR so subsequent runs update instead of duplicating."
        ),
    )

    # --- Limits ---------------------------------------------------------
    max_changed_files: int = Field(
        default=2000,
        ge=1,
        description=(
            "If a PR changes more than this, sts-app falls back to "
            "'run all tests' instead of doing a per-file affecting pass."
        ),
    )
    request_timeout_seconds: float = Field(default=60.0, gt=0)

    # --- Full review path (v0.0.3) -------------------------------------
    # When enabled, sts-app downloads the PR head as a tarball, extracts
    # it to a temp dir, runs `repox build` for the call graph, then
    # `sts select` with transitive-import affecting. Disabled in dev by
    # default to avoid the network round-trips during local poking.
    enable_full_review: bool = Field(
        default=True,
        description=(
            "Clone the repo at the PR head SHA via the GitHub tarball "
            "endpoint and run repox + sts against the actual files. "
            "Disable to keep the v0.0.2 Tree-API-only path."
        ),
    )
    max_repo_bytes: int = Field(
        default=200 * 1024 * 1024,  # 200 MB
        ge=1,
        description=(
            "Reject tarballs above this size. Defends against denial-of-"
            "service attacks via maliciously huge repositories."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor. Settings are read once per process."""
    return Settings()


def reset_settings_cache() -> None:
    """Test helper - clear the cached Settings instance."""
    get_settings.cache_clear()
