"""Shared pytest fixtures for apr-app tests.

Builds a fully-mocked TestClient where outbound httpx traffic is routed
to in-memory handlers. No real network I/O.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from apr_app.config import Settings, reset_settings_cache
from apr_app.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr

WEBHOOK_SECRET = "test-secret-please-rotate"


@pytest.fixture
def settings() -> Iterator[Settings]:
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

    Tests populate `state` to script the GitHub responses:

      state["pr"]               -> dict returned by GET /pulls/{n}
      state["pr_files"]         -> rows returned by GET /pulls/{n}/files
      state["file_contents"]    -> dict[path -> bytes] for GET /contents/{path}
      state["existing_comment_id"] -> int | None for find_sticky_comment
      state["created_bodies"]   -> bodies passed to create_comment
      state["updated_bodies"]   -> tuples passed to update_comment
    """
    state: dict[str, Any] = {
        "pr": {
            "number": 7,
            "title": "Add transitive-import affecting",
            "body": "Wires sts.selector through repox v0.3 imports for deeper test selection.",
            "head": {"sha": "deadbeefcafe"},
        },
        "pr_files": [],
        "file_contents": {},
        "existing_comment_id": None,
        "created_bodies": [],
        "updated_bodies": [],
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        method = request.method

        # GET /repos/{o}/{r}/pulls/{n}/files
        if method == "GET" and "/pulls/" in url and "/files" in url:
            paths = state["pr_files"]
            return httpx.Response(200, json=paths)

        # GET /repos/{o}/{r}/pulls/{n}  (no /files suffix)
        if method == "GET" and "/pulls/" in url:
            return httpx.Response(200, json=state["pr"])

        # GET /repos/{o}/{r}/contents/{path}
        if method == "GET" and "/contents/" in url:
            # Extract the path portion after '/contents/'
            tail = url.split("/contents/", 1)[1]
            path = tail.split("?", 1)[0]
            data = state["file_contents"].get(path)
            if data is None:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(
                200,
                json={
                    "name": path.rsplit("/", 1)[-1],
                    "path": path,
                    "encoding": "base64",
                    "content": base64.b64encode(data).decode("ascii"),
                    "type": "file",
                },
            )

        # GET /repos/.../issues/{n}/comments
        if method == "GET" and "/issues/" in url and "/comments" in url:
            cid = state["existing_comment_id"]
            if cid is None:
                return httpx.Response(200, json=[])
            return httpx.Response(
                200,
                json=[
                    {
                        "id": cid,
                        "body": "<!-- apr-app:sticky -->\nold body",
                    }
                ],
            )

        # POST /repos/.../issues/{n}/comments
        if method == "POST" and "/issues/" in url and "/comments" in url:
            data = json.loads(request.read().decode("utf-8"))
            state["created_bodies"].append(data.get("body", ""))
            return httpx.Response(201, json={"id": 555, "body": data["body"]})

        # PATCH /repos/.../issues/comments/{id}
        if method == "PATCH" and "/issues/comments/" in url:
            comment_id = int(url.rsplit("/", 1)[-1])
            data = json.loads(request.read().decode("utf-8"))
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
    title: str = "Add transitive-import affecting",
    body: str = "Wires sts.selector through repox v0.3 imports for deeper test selection.",
) -> dict[str, Any]:
    return {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "head": {"sha": head_sha, "ref": "feature/x"},
            "base": {"ref": "main"},
            "title": title,
            "body": body,
        },
        "repository": {
            "full_name": f"{owner}/{repo}",
            "name": repo,
            "owner": {"login": owner},
        },
    }
