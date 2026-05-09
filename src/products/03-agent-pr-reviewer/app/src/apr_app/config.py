"""Environment-driven settings for the apr-app service.

All settings are namespaced with the `APR_APP_` prefix.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service configuration. All fields have safe development defaults."""

    model_config = SettingsConfigDict(
        env_prefix="APR_APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---------------------------------------------------------
    host: str = Field(default="127.0.0.1", description="Address to bind.")
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    reload: bool = Field(default=False, description="Auto-reload on code change.")

    # --- GitHub App auth (production) ----------------------------------
    app_id: str | None = Field(
        default=None,
        description="Numeric GitHub App ID.",
    )
    private_key_pem: SecretStr | None = Field(
        default=None,
        description="The App's RSA private key in PEM form (paste contents).",
    )
    github_token: SecretStr | None = Field(
        default=None,
        description=("DEV ONLY: GitHub PAT. Ignored when app_id + private_key_pem are set."),
    )
    github_api_url: str = Field(
        default="https://api.github.com",
        description="Base URL for the GitHub REST API. Override for GHES.",
    )

    # --- Webhook security ----------------------------------------------
    webhook_secret: SecretStr | None = Field(
        default=None,
        description=(
            "HMAC secret for X-Hub-Signature-256 verification. "
            "If unset, signature verification is skipped (DEV ONLY)."
        ),
    )

    # --- Comment behavior ----------------------------------------------
    sticky_comment_marker: str = Field(
        default="<!-- apr-app:sticky -->",
        description=(
            "Hidden HTML comment that identifies this bot's sticky comment "
            "on a PR so subsequent runs update instead of duplicating."
        ),
    )

    # --- Limits ---------------------------------------------------------
    max_changed_files: int = Field(
        default=100,
        ge=1,
        description=(
            "If a PR changes more than this, apr-app falls back to "
            "metadata-only review (no per-file rules)."
        ),
    )
    max_file_bytes: int = Field(
        default=512_000,
        ge=1,
        description="Skip per-file rules on files larger than this.",
    )
    request_timeout_seconds: float = Field(default=20.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor. Settings are read once per process."""
    return Settings()


def reset_settings_cache() -> None:
    """Test helper - clear the cached Settings instance."""
    get_settings.cache_clear()
