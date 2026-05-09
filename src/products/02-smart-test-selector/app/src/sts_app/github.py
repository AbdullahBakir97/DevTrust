"""Minimal async GitHub REST client - just the endpoints sts-app needs.

We avoid importing a heavy GitHub SDK so the dependency surface stays
small and mypy-strict-friendly. httpx is more than enough for v0.0.x.

Endpoints used:

  GET  /repos/{owner}/{repo}/pulls/{number}/files
       List files changed in a PR. Returns up to 30 per page; we paginate.

  GET  /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
       Full file list at a given commit. Used as the "all tests in repo" set.

  GET  /repos/{owner}/{repo}/issues/{number}/comments
       List comments on a PR (PRs are issues for the comments API).
       Used to find our sticky comment to update.

  POST /repos/{owner}/{repo}/issues/{number}/comments
       Create a new comment.

  PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}
        Update an existing comment.

All methods raise GitHubError on non-2xx responses.
"""

from __future__ import annotations

from typing import Any

import httpx

USER_AGENT = "sts-app/0.0.1 (+https://github.com/AbdullahBakir97/sts)"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns a non-2xx status."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"GitHub API returned {status}: {body[:200]}")
        self.status = status
        self.body = body


class GitHubClient:
    """Thin async wrapper around httpx.AsyncClient.

    Caller supplies a token; the client adds the right Authorization +
    Accept headers. Use as an async context manager so connections close
    cleanly:

        async with GitHubClient(token, base_url) as gh:
            files = await gh.list_pr_files("owner", "repo", 42)
    """

    def __init__(
        self,
        token: str | None,
        base_url: str = "https://api.github.com",
        timeout: float = 20.0,
    ) -> None:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        )

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *_excinfo: object) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _check(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise GitHubError(resp.status_code, resp.text)

    async def list_pr_files(self, owner: str, repo: str, pr_number: int) -> list[str]:
        """Return changed file paths for a PR. Paginates as needed."""
        page = 1
        per_page = 100
        out: list[str] = []
        while True:
            resp = await self._client.get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={"per_page": per_page, "page": page},
            )
            await self._check(resp)
            raw = resp.json()
            if not isinstance(raw, list):
                raise GitHubError(resp.status_code, "expected JSON array of files")
            batch: list[dict[str, Any]] = raw
            for entry in batch:
                p = entry.get("filename")
                if isinstance(p, str):
                    out.append(p)
            if len(batch) < per_page:
                break
            page += 1
        return out

    async def list_tree(self, owner: str, repo: str, sha: str) -> list[str]:
        """Return all file paths in the repo at the given commit SHA."""
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/git/trees/{sha}",
            params={"recursive": "1"},
        )
        await self._check(resp)
        body: dict[str, Any] = resp.json()
        if not isinstance(body, dict):
            raise GitHubError(resp.status_code, "expected JSON object for tree")
        tree = body.get("tree", [])
        if not isinstance(tree, list):
            return []
        out: list[str] = []
        for entry in tree:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "blob":
                continue
            path = entry.get("path")
            if isinstance(path, str):
                out.append(path)
        return out

    async def find_sticky_comment(
        self, owner: str, repo: str, pr_number: int, marker: str
    ) -> int | None:
        """Return the comment_id of the sticky comment, or None."""
        page = 1
        per_page = 100
        while True:
            resp = await self._client.get(
                f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
                params={"per_page": per_page, "page": page},
            )
            await self._check(resp)
            raw = resp.json()
            batch: list[dict[str, Any]] = raw if isinstance(raw, list) else []
            for c in batch:
                body = c.get("body", "")
                cid = c.get("id")
                if isinstance(body, str) and marker in body and isinstance(cid, int):
                    return cid
            if len(batch) < per_page:
                return None
            page += 1

    async def create_comment(self, owner: str, repo: str, pr_number: int, body: str) -> int:
        resp = await self._client.post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        await self._check(resp)
        data: dict[str, Any] = resp.json()
        cid = data.get("id")
        if not isinstance(cid, int):
            raise GitHubError(resp.status_code, "comment id missing in response")
        return cid

    async def update_comment(self, owner: str, repo: str, comment_id: int, body: str) -> None:
        resp = await self._client.patch(
            f"/repos/{owner}/{repo}/issues/comments/{comment_id}",
            json={"body": body},
        )
        await self._check(resp)
