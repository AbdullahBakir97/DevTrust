"""GitHubDeploymentsProvider - real deploy events from the GitHub API.

GitHub's Deployments API records every deploy event a CI/CD pipeline
posts (Render, Vercel, Heroku, custom GitHub Actions workflows, etc.).
This provider reads `GET /repos/{owner}/{repo}/deployments` in a time
window and maps each deployment to a `Change` with kind="deploy".

The local `GitChangeProvider` (commits-as-deploys) remains the LCD
fallback. Most teams will run BOTH providers in parallel: GitHub
Deployments for the production-deploy story, git log for the "what
landed on main since yesterday" story.

Auth (v0.1):
  - Personal Access Token via the `WHYCHANGED_GITHUB_TOKEN` env var,
    or `GITHUB_TOKEN` for compatibility with most CI runtimes.
  - GitHub App installation tokens land in v0.2 alongside webhook mode.

Pagination:
  GitHub returns up to 100 deployments per page. We page until we hit
  a deployment older than `since` OR until `max_pages` is exhausted.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from whychanged.models import Change

logger = logging.getLogger(__name__)


_DEFAULT_API_URL = "https://api.github.com"
_USER_AGENT = "whychanged/0.1 (+https://github.com/AbdullahBakir97/whychanged)"


def _read_token() -> str | None:
    """Pick up the auth token from the conventional env vars."""
    return os.environ.get("WHYCHANGED_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


class GitHubDeploymentsProvider:
    """Fetch recent deployments from a GitHub repo as Change rows.

    Construction is cheap; the network round-trip happens only when
    `changes()` is called.

    Parameters:
        owner / repo    The repo coordinates (e.g. "AbdullahBakir97" / "DevTrust").
        token           Bearer token. Falls back to env vars when None.
        environment     Optional filter (e.g. "production", "staging").
        api_base_url    Override for GitHub Enterprise Server.
        max_pages       Safety cap on pagination depth.
        timeout         Per-request timeout in seconds.
    """

    name = "github-deployments"

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        token: str | None = None,
        environment: str | None = None,
        api_base_url: str = _DEFAULT_API_URL,
        max_pages: int = 5,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token if token is not None else _read_token()
        self.environment = environment
        self.api_base_url = api_base_url.rstrip("/")
        self.max_pages = max_pages
        self.timeout = timeout
        # Tests inject `client`; production builds one per call.
        self._client = client

    # --- network ------------------------------------------------------

    def _build_client(self) -> httpx.Client:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": _USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.Client(
            base_url=self.api_base_url,
            headers=headers,
            timeout=self.timeout,
        )

    def _list_deployments_page(self, client: httpx.Client, page: int) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {"per_page": 100, "page": page}
        if self.environment:
            params["environment"] = self.environment
        try:
            resp = client.get(
                f"/repos/{self.owner}/{self.repo}/deployments",
                params=params,
            )
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("GitHub deployments fetch failed: %s", exc)
            return []
        if resp.status_code >= 400:
            logger.warning(
                "GitHub deployments returned %d: %s",
                resp.status_code,
                resp.text[:200],
            )
            return []
        body = resp.json()
        if not isinstance(body, list):
            return []
        return [item for item in body if isinstance(item, dict)]

    # --- mapping ------------------------------------------------------

    @staticmethod
    def _to_change(dep: dict[str, Any]) -> Change | None:
        created_at_raw = dep.get("created_at")
        if not isinstance(created_at_raw, str):
            return None
        try:
            iso = created_at_raw.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(iso)
        except ValueError:
            return None

        ref = dep.get("ref") or dep.get("sha", "?")
        env = dep.get("environment") or "?"
        description = dep.get("description") or ""
        summary_parts = [f"deploy to `{env}` of `{ref}`"]
        if description:
            summary_parts.append(f"-- {description}")
        summary = " ".join(summary_parts)

        creator = dep.get("creator")
        actor: str | None = None
        if isinstance(creator, dict):
            login = creator.get("login")
            if isinstance(login, str):
                actor = login

        url = dep.get("url") if isinstance(dep.get("url"), str) else None

        return Change(
            kind="deploy",
            source="github-deployments",
            timestamp=timestamp,
            summary=summary,
            actor=actor,
            files=[],  # deployments don't carry file lists; the commit linked from `sha` does
            url=url,
        )

    # --- public API ---------------------------------------------------

    def changes(self, since: datetime, until: datetime) -> list[Change]:
        """Page through deployments and return those in [since, until]."""
        client = self._client or self._build_client()
        owns_client = self._client is None
        out: list[Change] = []
        try:
            for page in range(1, self.max_pages + 1):
                batch = self._list_deployments_page(client, page)
                if not batch:
                    break
                exhausted_window = False
                for dep in batch:
                    change = self._to_change(dep)
                    if change is None:
                        continue
                    if change.timestamp < since:
                        # Deployments are returned newest-first; once we
                        # cross `since`, the rest of this page (and all
                        # later pages) are out of window.
                        exhausted_window = True
                        continue
                    if change.timestamp > until:
                        # Newer than the window -- skip but keep paging.
                        continue
                    out.append(change)
                if exhausted_window:
                    break
                if len(batch) < 100:
                    break
        finally:
            if owns_client:
                client.close()
        return out
