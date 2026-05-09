"""GitHub App authentication: JWT signing and installation tokens.

Mirror of sts_app.auth -- same API surface so we can extract this into
a shared `devtrust_app_kit` package later without changing either app.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
import jwt

if TYPE_CHECKING:
    from apr_app.config import Settings

logger = logging.getLogger(__name__)

_JWT_TTL_SECONDS = 9 * 60
_INSTALLATION_REFRESH_MARGIN_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when we cannot mint a usable installation token."""


@dataclass
class _CachedToken:
    token: str
    expires_at: float

    def is_fresh(self, now: float) -> bool:
        return now < (self.expires_at - _INSTALLATION_REFRESH_MARGIN_SECONDS)


class GitHubAppAuth:
    """Mint and cache GitHub App installation tokens."""

    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        api_base_url: str = "https://api.github.com",
        timeout: float = 20.0,
    ) -> None:
        self.app_id = app_id
        self.private_key_pem = private_key_pem
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self._cache: dict[str, _CachedToken] = {}

    def sign_app_jwt(self, now: float | None = None) -> str:
        issued_at = int(now or time.time())
        payload = {
            "iat": issued_at - 60,
            "exp": issued_at + _JWT_TTL_SECONDS,
            "iss": self.app_id,
        }
        token: str = jwt.encode(payload, self.private_key_pem, algorithm="RS256")
        return token

    async def installation_token(self, installation_id: str | int) -> str:
        key = str(installation_id)
        now = time.time()
        cached = self._cache.get(key)
        if cached is not None and cached.is_fresh(now):
            return cached.token

        app_jwt = self.sign_app_jwt(now)
        async with httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "apr-app/0.0.1",
            },
        ) as client:
            resp = await client.post(f"/app/installations/{key}/access_tokens")
            if resp.status_code >= 400:
                raise AuthError(
                    f"installations/access_tokens returned {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()

        token = data.get("token")
        expires_at_raw = data.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at_raw, str):
            raise AuthError("response missing token / expires_at")

        try:
            iso = expires_at_raw.replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(iso).timestamp()
        except ValueError as exc:
            raise AuthError(f"unparseable expires_at {expires_at_raw!r}") from exc

        self._cache[key] = _CachedToken(token=token, expires_at=expires_at)
        return token

    def invalidate(self, installation_id: str | int) -> None:
        self._cache.pop(str(installation_id), None)


def auth_from_settings(settings: Settings) -> GitHubAppAuth | None:
    """Build a GitHubAppAuth from settings; None when credentials missing."""
    if settings.app_id is None or settings.private_key_pem is None:
        return None
    pem = settings.private_key_pem.get_secret_value()
    if not pem.strip():
        return None
    return GitHubAppAuth(
        app_id=settings.app_id,
        private_key_pem=pem,
        api_base_url=settings.github_api_url,
        timeout=settings.request_timeout_seconds,
    )
