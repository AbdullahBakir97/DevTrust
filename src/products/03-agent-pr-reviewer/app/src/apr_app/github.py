"""Async GitHub REST client - just the endpoints apr-app needs.

Different from sts-app's client because apr cares about file *contents*
(it runs rules over them), not just file *paths*. Endpoints used:

  GET  /repos/{owner}/{repo}/pulls/{n}                  PR title + body
  GET  /repos/{owner}/{repo}/pulls/{n}/files            list of changed files
  GET  /repos/{owner}/{repo}/contents/{path}?ref=SHA    file content (base64)
  GET  /repos/{owner}/{repo}/issues/{n}/comments        find sticky comment
  POST /repos/{owner}/{repo}/issues/{n}/comments        create comment
  PATCH /repos/{owner}/{repo}/issues/comments/{id}      update comment

All methods raise GitHubError on non-2xx responses.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

USER_AGENT = "apr-app/0.0.1 (+https://github.com/AbdullahBakir97/apr)"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns a non-2xx status."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"GitHub API returned {status}: {body[:200]}")
        self.status = status
        self.body = body


class GitHubClient:
    """Thin async wrapper around httpx.AsyncClient."""

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

    async def get_pr(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Return the PR object (title, body, head.sha, etc.)."""
        resp = await self._client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        await self._check(resp)
        body: dict[str, Any] = resp.json()
        if not isinstance(body, dict):
            raise GitHubError(resp.status_code, "expected JSON object for PR")
        return body

    async def list_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Return changed file rows for a PR. Each row has `filename` + `status`."""
        page = 1
        per_page = 100
        out: list[dict[str, Any]] = []
        while True:
            resp = await self._client.get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={"per_page": per_page, "page": page},
            )
            await self._check(resp)
            raw = resp.json()
            if not isinstance(raw, list):
                raise GitHubError(resp.status_code, "expected JSON array of files")
            out.extend(item for item in raw if isinstance(item, dict))
            if len(raw) < per_page:
                break
            page += 1
        return out

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> bytes | None:
        """Return raw bytes of a file at a given ref, or None on 404 / oversize.

        The Contents API returns base64-encoded content for files <=1 MB.
        For larger files it returns 'too_large' content and a 200 status;
        we treat that as a None (caller skips per-file rules)."""
        resp = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        if resp.status_code == 404:
            return None
        await self._check(resp)
        body = resp.json()
        if not isinstance(body, dict):
            return None
        encoding = body.get("encoding")
        content = body.get("content")
        if encoding == "base64" and isinstance(content, str):
            try:
                return base64.b64decode(content)
            except (ValueError, TypeError):
                return None
        # 'too_large' or 'none' encoding -> caller skips this file
        return None

    async def find_sticky_comment(
        self, owner: str, repo: str, pr_number: int, marker: str
    ) -> int | None:
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
                cid = c.get("id")
                body = c.get("body", "")
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
        data = resp.json()
        if not isinstance(data, dict):
            raise GitHubError(resp.status_code, "create_comment: bad JSON")
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
