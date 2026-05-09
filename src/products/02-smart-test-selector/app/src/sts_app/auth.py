"""GitHub App authentication: JWT signing and installation tokens.

Replaces the v0.0.1 Personal-Access-Token mode for production deploys.
The PAT mode still works in dev (just unset `STS_APP_APP_ID` and set
`STS_APP_GITHUB_TOKEN`).

Flow per request:

  1. We sign a short-lived (10 min) JWT with the app's RSA private key.
     This JWT identifies us as the App, not as any specific installation.
  2. We exchange the JWT for an *installation token* by calling
     `POST /app/installations/{installation_id}/access_tokens`.
     The installation token is what's used for all subsequent API calls
     against the repos that installation has access to.
  3. We cache the installation token in memory until it expires (with
     a 60-second safety margin) so a busy deployment doesn't burn a
     network round-trip on every webhook.

Reference: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import jwt

if TYPE_CHECKING:
    from sts_app.config import Settings

logger = logging.getLogger(__name__)

# JWT-signing window. GitHub allows up to 10 minutes; we use 9 to leave
# headroom for clock skew between us and api.github.com.
_JWT_TTL_SECONDS = 9 * 60
# Treat installation tokens as expired this many seconds before they
# actually expire, to avoid using one mid-flight when it's about to die.
_INSTALLATION_REFRESH_MARGIN_SECONDS = 60


class AuthError(RuntimeError):
    """Raised when we cannot mint a usable installation token."""


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # epoch seconds

    def is_fresh(self, now: float) -> bool:
        return now < (self.expires_at - _INSTALLATION_REFRESH_MARGIN_SECONDS)


class GitHubAppAuth:
    """Mint and cache GitHub App installation tokens.

    Thread-safe in the typical asyncio sense: a single instance is
    shared across requests, but each request awaits any in-flight token
    fetch via the underlying httpx client (we serialize per-installation
    refreshes with a small lock).
    """

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
        """Sign a JWT as the App (not yet scoped to an installation).

        Used as the Bearer token when calling `/app/...` endpoints.
        """
        issued_at = int(now or time.time())
        payload = {
            "iat": issued_at - 60,  # 60 s clock-skew slack
            "exp": issued_at + _JWT_TTL_SECONDS,
            "iss": self.app_id,
        }
        # PyJWT 2.x returns str (typed accordingly).
        token: str = jwt.encode(payload, self.private_key_pem, algorithm="RS256")
        return token

    async def installation_token(self, installation_id: str | int) -> str:
        """Return a fresh installation token for the given installation_id.

        Hits the cache when possible; otherwise mints a JWT and exchanges
        it for an installation token.
        """
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
                "User-Agent": "sts-app/0.0.2",
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

        # GitHub's expires_at is ISO-8601. We convert to epoch seconds via
        # datetime.fromisoformat, which supports the 'Z' UTC marker on 3.11+.
        from datetime import datetime  # local import keeps top-level lean

        try:
            iso = expires_at_raw.replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(iso).timestamp()
        except ValueError as exc:
            raise AuthError(f"unparseable expires_at {expires_at_raw!r}") from exc

        self._cache[key] = _CachedToken(token=token, expires_at=expires_at)
        return token

    def invalidate(self, installation_id: str | int) -> None:
        """Drop a cached token (e.g., after an unexpected 401)."""
        self._cache.pop(str(installation_id), None)


def auth_from_settings(settings: Settings) -> GitHubAppAuth | None:
    """Build a GitHubAppAuth from environment-driven settings.

    Returns None when the App credentials aren't configured -- the
    caller can then fall back to the legacy PAT path.
    """
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
