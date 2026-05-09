"""Shared pytest fixtures for sts-app tests.

The fixtures here build a fully-configured FastAPI TestClient that has
its GitHub HTTP traffic mocked. We don't talk to api.github.com from
the test suite - every test runs in milliseconds.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sts_app.config import Settings, reset_settings_cache
from sts_app.main import create_app

WEBHOOK_SECRET = "test-secret-please-rotate"


@pytest.fixture
def settings() -> Iterator[Settings]:
    """Per-test Settings with a known secret and a fake GitHub token.

    pydantic-settings caches with @lru_cache; we reset both before and
    after the test so other test files don't see leaked state.
    """
    reset_settings_cache()
    s = Settings(
        webhook_secret=SecretStr(WEBHOOK_SECRET),
        github_token=SecretStr("fake-token"),
        github_api_url="https://api.github.test",
        log_level="warning",
    )
    yield s
    reset_settings_cache()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def mock_github(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace httpx.AsyncClient with one that routes to in-memory handlers.

    The fixture returns a dict of `state` the test can populate or assert
    against:

      state["pr_files"]   -> list[str]   what list_pr_files returns
      state["tree_files"] -> list[str]   what list_tree returns
      state["existing_comment_id"] -> int | None  for find_sticky_comment
      state["created_bodies"] -> list[str]   bodies passed to create_comment
      state["updated_bodies"] -> list[tuple[int, str]]   for update_comment
    """
    state: dict[str, Any] = {
        "pr_files": [],
        "tree_files": [],
        "existing_comment_id": None,
        "created_bodies": [],
        "updated_bodies": [],
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        method = request.method

        # GET /repos/{owner}/{repo}/pulls/{n}/files
        if method == "GET" and "/pulls/" in url and "/files" in url:
            paths = state["pr_files"]
            return httpx.Response(200, json=[{"filename": p} for p in paths])

        # GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
        if method == "GET" and "/git/trees/" in url:
            paths = state["tree_files"]
            return httpx.Response(
                200,
                json={
                    "sha": "abc123",
                    "tree": [{"path": p, "type": "blob", "mode": "100644"} for p in paths],
                },
            )

        # GET /repos/{owner}/{repo}/issues/{n}/comments
        if (
            method == "GET"
            and "/issues/" in url
            and (url.rstrip("?&").endswith("/comments") or "/comments?" in url)
        ):
            cid = state["existing_comment_id"]
            if cid is None:
                return httpx.Response(200, json=[])
            return httpx.Response(
                200,
                json=[
                    {
                        "id": cid,
                        "body": "<!-- sts-app:sticky -->\nold body",
                    }
                ],
            )

        # POST /repos/{owner}/{repo}/issues/{n}/comments
        if method == "POST" and "/issues/" in url and "/comments" in url:
            body_obj = request.read().decode("utf-8")
            import json as _json

            data = _json.loads(body_obj)
            state["created_bodies"].append(data.get("body", ""))
            return httpx.Response(201, json={"id": 999, "body": data["body"]})

        # PATCH /repos/{owner}/{repo}/issues/comments/{cid}
        if method == "PATCH" and "/issues/comments/" in url:
            comment_id = int(url.rsplit("/", 1)[-1])
            body_obj = request.read().decode("utf-8")
            import json as _json

            data = _json.loads(body_obj)
            state["updated_bodies"].append((comment_id, data.get("body", "")))
            return httpx.Response(200, json={"id": comment_id, "body": data["body"]})

        return httpx.Response(404, json={"message": f"unmocked: {method} {url}"})

    transport = httpx.MockTransport(_handler)

    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_async_client)
    return state


def make_pull_request_payload(
    *,
    action: str = "opened",
    owner: str = "octo",
    repo: str = "demo",
    number: int = 7,
    head_sha: str = "deadbeefcafe",
) -> dict[str, Any]:
    """Build a minimal-but-realistic pull_request webhook payload."""
    return {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "head": {"sha": head_sha, "ref": "feature/x"},
            "base": {"ref": "main"},
        },
        "repository": {
            "full_name": f"{owner}/{repo}",
            "name": repo,
            "owner": {"login": owner},
        },
    }
