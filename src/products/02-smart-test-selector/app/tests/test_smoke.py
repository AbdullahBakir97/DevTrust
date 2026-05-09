"""Smoke + unit tests for sts-app v0.0.1.

Coverage:
  - security.verify         HMAC signature handling (good, bad, missing, dev mode)
  - handlers._format_comment Sticky comment Markdown formatting
  - GET /, /health, /version
  - POST /webhooks/github   Signed-webhook handling end-to-end:
                              - rejects unsigned and badly-signed requests
                              - ignores non-pull_request events
                              - on a valid pull_request payload, creates
                                a comment when none exists and updates
                                the existing one when it does
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sts_app import __version__ as app_version
from sts_app.handlers import _format_comment
from sts_app.security import compute_signature, verify

from tests.conftest import WEBHOOK_SECRET, make_pull_request_payload

# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------


def test_verify_accepts_correct_signature() -> None:
    payload = b'{"hello":"world"}'
    sig = compute_signature(WEBHOOK_SECRET, payload)
    assert verify(WEBHOOK_SECRET, payload, sig) is True


def test_verify_rejects_wrong_signature() -> None:
    payload = b'{"hello":"world"}'
    bad = "sha256=" + "0" * 64
    assert verify(WEBHOOK_SECRET, payload, bad) is False


def test_verify_rejects_missing_signature() -> None:
    assert verify(WEBHOOK_SECRET, b"x", None) is False
    assert verify(WEBHOOK_SECRET, b"x", "") is False


def test_verify_rejects_wrong_prefix() -> None:
    payload = b"x"
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    assert verify(WEBHOOK_SECRET, payload, "sha1=" + mac) is False


def test_verify_dev_mode_returns_true_when_secret_is_none() -> None:
    assert verify(None, b"anything", None) is True
    assert verify(None, b"anything", "sha256=garbage") is True


# ---------------------------------------------------------------------------
# comment formatting
# ---------------------------------------------------------------------------


class _FakeStats:
    def __init__(self, must: int, should: int, total: int) -> None:
        self.must_run = must
        self.should_run = should
        self.can_skip = 0
        self.total_tests_in_repo = total


class _FakeTest:
    def __init__(self, path: str, framework: str = "pytest") -> None:
        self.path = path
        self.framework = framework
        self.kind = "unit"


class _FakeSel:
    def __init__(self, test: _FakeTest, priority: str, reason: str) -> None:
        self.test = test
        self.priority = priority
        self.reason = reason


class _FakeReport:
    def __init__(
        self,
        *,
        must_paths: list[str],
        total: int,
        fallback: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        self.tool_version = "0.0.2"
        self.schema_version = "0.1.0"
        self.stats = _FakeStats(must=len(must_paths), should=0, total=total)
        self.selections = [
            _FakeSel(_FakeTest(p), "must", "sibling test in same directory") for p in must_paths
        ]
        self.fallback_run_all = fallback
        self.fallback_reason = fallback_reason
        self.inputs = type("Inp", (), {"changed_files": []})()


def test_format_comment_includes_marker_and_must_run_tests() -> None:
    rpt = _FakeReport(must_paths=["tests/test_a.py", "tests/test_b.py"], total=5)
    body = _format_comment(rpt, "<!-- sts-app:sticky -->")
    assert "<!-- sts-app:sticky -->" in body
    assert "tests/test_a.py" in body
    assert "tests/test_b.py" in body
    assert "Smart Test Selector" in body
    assert "2 must-run" in body


def test_format_comment_fallback_run_all() -> None:
    rpt = _FakeReport(
        must_paths=[],
        total=42,
        fallback=True,
        fallback_reason="manifest changed",
    )
    body = _format_comment(rpt, "<!-- sts-app:sticky -->")
    assert "run all 42 tests" in body
    assert "manifest changed" in body


# ---------------------------------------------------------------------------
# basic HTTP routes
# ---------------------------------------------------------------------------


def test_root_endpoint(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "sts-app"
    assert body["version"] == app_version


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_version_endpoint(client: TestClient) -> None:
    resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "sts_app" in body and "sts_engine" in body


# ---------------------------------------------------------------------------
# webhook
# ---------------------------------------------------------------------------


def _signed_post(
    client: TestClient,
    payload: dict[str, Any],
    *,
    event: str = "pull_request",
    secret: str | None = WEBHOOK_SECRET,
) -> Any:
    raw = json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {
        "X-GitHub-Event": event,
        "Content-Type": "application/json",
    }
    if secret is not None:
        headers["X-Hub-Signature-256"] = compute_signature(secret, raw)
    return client.post("/webhooks/github", content=raw, headers=headers)


def test_webhook_rejects_missing_signature(client: TestClient) -> None:
    payload = make_pull_request_payload()
    resp = _signed_post(client, payload, secret=None)
    assert resp.status_code == 401


def test_webhook_rejects_wrong_signature(client: TestClient) -> None:
    payload = make_pull_request_payload()
    raw = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=" + "0" * 64,
        "Content-Type": "application/json",
    }
    resp = client.post("/webhooks/github", content=raw, headers=headers)
    assert resp.status_code == 401


def test_webhook_ignores_non_pull_request_events(client: TestClient) -> None:
    payload = {"zen": "Practicality beats purity."}
    resp = _signed_post(client, payload, event="ping")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ignored"


def test_webhook_ignores_unhandled_pr_actions(client: TestClient) -> None:
    payload = make_pull_request_payload(action="closed")
    resp = _signed_post(client, payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ignored"


def test_webhook_creates_comment_on_opened_pr(
    client: TestClient, mock_github: dict[str, Any]
) -> None:
    mock_github["pr_files"] = ["packages/a/src/core.py"]
    mock_github["tree_files"] = [
        "packages/a/pyproject.toml",
        "packages/a/src/core.py",
        "packages/a/tests/test_a.py",
        "packages/b/pyproject.toml",
        "packages/b/tests/test_b.py",
    ]
    mock_github["existing_comment_id"] = None

    payload = make_pull_request_payload(action="opened")
    resp = _signed_post(client, payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["action"] == "created"
    assert body["must_run"] >= 1
    assert len(mock_github["created_bodies"]) == 1
    assert "<!-- sts-app:sticky -->" in mock_github["created_bodies"][0]


def test_webhook_updates_existing_sticky_comment(
    client: TestClient, mock_github: dict[str, Any]
) -> None:
    mock_github["pr_files"] = ["packages/a/src/core.py"]
    mock_github["tree_files"] = [
        "packages/a/pyproject.toml",
        "packages/a/src/core.py",
        "packages/a/tests/test_a.py",
    ]
    mock_github["existing_comment_id"] = 555

    payload = make_pull_request_payload(action="synchronize")
    resp = _signed_post(client, payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["action"] == "updated"
    assert mock_github["created_bodies"] == []
    assert len(mock_github["updated_bodies"]) == 1
    cid, posted = mock_github["updated_bodies"][0]
    assert cid == 555
    assert "<!-- sts-app:sticky -->" in posted


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
def test_webhook_handled_actions_match_design(
    client: TestClient, mock_github: dict[str, Any], action: str
) -> None:
    mock_github["pr_files"] = ["src/foo.py"]
    mock_github["tree_files"] = ["pyproject.toml", "src/foo.py", "tests/test_foo.py"]
    mock_github["existing_comment_id"] = None

    payload = make_pull_request_payload(action=action)
    resp = _signed_post(client, payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# v0.0.2: GitHub App JWT auth + installation tokens
# ---------------------------------------------------------------------------


def _generate_test_rsa_pem() -> str:
    """Generate a fresh 2048-bit RSA private key for the duration of one test."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return pem


def test_sign_app_jwt_round_trips_with_public_key() -> None:
    """The JWT signed by sign_app_jwt verifies against the matching public key."""
    import jwt as _jwt
    from cryptography.hazmat.primitives import serialization
    from sts_app.auth import GitHubAppAuth

    pem = _generate_test_rsa_pem()
    auth = GitHubAppAuth(app_id="12345", private_key_pem=pem)
    token = auth.sign_app_jwt(now=1_700_000_000.0)

    # Decode with the corresponding public key
    private_key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # We pass a fixed `now` to sign_app_jwt for determinism, so the
    # exp claim is in the past from PyJWT.decode's perspective.
    # Disable exp validation -- we're testing signature round-trip.
    payload = _jwt.decode(
        token,
        public_pem,
        algorithms=["RS256"],
        options={"verify_exp": False},
    )
    assert payload["iss"] == "12345"
    assert payload["iat"] <= payload["exp"]
    assert payload["exp"] - payload["iat"] <= 11 * 60  # 9-min TTL + 60s slack


def test_installation_token_caches_until_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call within the freshness window returns the cached token without
    making another HTTP request."""
    import asyncio

    from sts_app.auth import GitHubAppAuth

    pem = _generate_test_rsa_pem()
    auth = GitHubAppAuth(
        app_id="42",
        private_key_pem=pem,
        api_base_url="https://api.github.test",
    )

    call_count = {"n": 0}

    def _handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(
            201,
            json={
                "token": f"ghs_inst_{call_count['n']}",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )

    transport = httpx.MockTransport(_handler)
    real_async_client = httpx.AsyncClient

    def patched_async_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched_async_client)

    async def run() -> None:
        t1 = await auth.installation_token("99")
        t2 = await auth.installation_token("99")
        assert t1 == t2  # cached
        assert call_count["n"] == 1

    asyncio.run(run())


def test_auth_from_settings_returns_none_without_credentials() -> None:
    """When app_id / private_key_pem aren't set, auth_from_settings returns None."""
    from sts_app.auth import auth_from_settings
    from sts_app.config import Settings

    s = Settings()  # all defaults
    assert auth_from_settings(s) is None


def test_auth_from_settings_returns_instance_when_configured() -> None:
    from pydantic import SecretStr
    from sts_app.auth import GitHubAppAuth, auth_from_settings
    from sts_app.config import Settings

    s = Settings(
        app_id="12345",
        private_key_pem=SecretStr(_generate_test_rsa_pem()),
    )
    out = auth_from_settings(s)
    assert isinstance(out, GitHubAppAuth)
    assert out.app_id == "12345"


def test_handler_skips_when_no_auth_configured(client: TestClient) -> None:
    """With neither App auth nor PAT, the handler returns a clear `skipped` status.

    We rebuild the client with a Settings that has nothing -- the
    default `client` fixture provides a fake PAT.
    """
    from pydantic import SecretStr
    from sts_app.config import Settings, reset_settings_cache
    from sts_app.main import create_app

    reset_settings_cache()
    s = Settings(webhook_secret=SecretStr(WEBHOOK_SECRET))
    bare_client = TestClient(create_app(s))

    payload = make_pull_request_payload(action="opened")
    raw = json.dumps(payload).encode("utf-8")
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": compute_signature(WEBHOOK_SECRET, raw),
        "Content-Type": "application/json",
    }
    resp = bare_client.post("/webhooks/github", content=raw, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "skipped"
    assert "no auth configured" in body["reason"]
    reset_settings_cache()


# ---------------------------------------------------------------------------
# v0.0.3: clone safety
# ---------------------------------------------------------------------------


def test_clone_extract_rejects_path_escape(tmp_path: Path) -> None:
    """A tarball with `../escape.txt` MUST be rejected, not extract outside dest."""
    import io
    import tarfile

    from sts_app.clone import CloneError, extract_safely

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # First a single root dir like GitHub's tarballs
        info = tarfile.TarInfo("repo-root/")
        info.type = tarfile.DIRTYPE
        tf.addfile(info)
        # Then a malicious entry that escapes
        bad = tarfile.TarInfo("repo-root/../escape.txt")
        bad.size = 4
        tf.addfile(bad, io.BytesIO(b"boom"))
    buf.seek(0)
    with pytest.raises(CloneError):
        extract_safely(buf, tmp_path)


def test_clone_extract_skips_symlinks(tmp_path: Path) -> None:
    """Symlinks are silently skipped (we don't need them for repo analysis)."""
    import io
    import tarfile

    from sts_app.clone import extract_safely

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        root = tarfile.TarInfo("repo-root/")
        root.type = tarfile.DIRTYPE
        tf.addfile(root)
        # A regular file that should extract
        f = tarfile.TarInfo("repo-root/keep.py")
        f.size = 4
        tf.addfile(f, io.BytesIO(b"x=1\n"))
        # A symlink that should be skipped
        sym = tarfile.TarInfo("repo-root/sneak")
        sym.type = tarfile.SYMTYPE
        sym.linkname = "/etc/passwd"
        tf.addfile(sym)
    buf.seek(0)
    root = extract_safely(buf, tmp_path)
    assert (root / "keep.py").is_file()
    assert not (root / "sneak").exists()


def test_clone_diff_filenames_skips_removed_and_dedupes() -> None:
    """The PR-files response cleaner skips removed files and dedupes."""
    from sts_app.clone import diff_filenames_to_repo_paths

    rows = [
        {"filename": "src/a.py", "status": "modified"},
        {"filename": "src/b.py", "status": "added"},
        {"filename": "src/old.py", "status": "removed"},  # skipped
        {"filename": "src/a.py", "status": "renamed"},  # duped -- skipped
        {"filename": "src/c.py", "status": "modified"},
    ]
    out = diff_filenames_to_repo_paths(rows)
    assert out == ["src/a.py", "src/b.py", "src/c.py"]


def test_clone_size_cap_aborts_download(tmp_path: Path) -> None:
    """When the streamed tarball exceeds max_bytes, we raise TarballTooLargeError."""
    import asyncio

    import httpx as _httpx
    from sts_app.clone import TarballTooLargeError, stream_tarball_to_buffer

    big_chunk = b"X" * 1024
    chunks_streamed = [big_chunk] * 50  # 50 KB total

    async def _hand(_request: _httpx.Request) -> _httpx.Response:
        return _httpx.Response(200, stream=_httpx.ByteStream(b"".join(chunks_streamed)))

    transport = _httpx.MockTransport(
        lambda req: _httpx.Response(200, content=b"".join(chunks_streamed))
    )

    async def run() -> None:
        async with _httpx.AsyncClient(
            base_url="https://api.github.test", transport=transport
        ) as client:
            with pytest.raises(TarballTooLargeError):
                await stream_tarball_to_buffer(client, "octo", "demo", "abc", max_bytes=10_000)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# v0.0.3: review.py orchestration (uses a stub repox.analyze)
# ---------------------------------------------------------------------------


class _StubFile:
    def __init__(self, path: str) -> None:
        self.path = path


class _StubImport:
    def __init__(self, source_file: str, target_file: str | None) -> None:
        self.source_file = source_file
        self.target_file = target_file


class _StubCallGraph:
    def __init__(self, imports: list[_StubImport]) -> None:
        self.imports = imports
        self.symbols: list[Any] = []
        self.edges: list[Any] = []


class _StubArchitecture:
    def __init__(
        self,
        files: list[str],
        imports: list[tuple[str, str | None]],
    ) -> None:
        self.files = [_StubFile(p) for p in files]
        self.call_graph = _StubCallGraph([_StubImport(s, t) for s, t in imports])
        self.schema_version = "0.3.0"
        self.tool_version = "0.3.0"


def test_review_select_with_full_review_uses_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """select_with_full_review must build a RepoxArtifact whose
    imports_by_source matches the architecture's call_graph.imports."""
    from sts_app import review as review_mod

    arch = _StubArchitecture(
        files=["app.py", "core.py", "tests/test_app.py"],
        imports=[
            ("app.py", "core.py"),
            ("tests/test_app.py", "app.py"),
            ("app.py", None),  # external import -- filtered out
        ],
    )

    def fake_analyze(_root: Path) -> Any:
        return arch

    monkeypatch.setattr(review_mod, "_run_repox_analyze", fake_analyze)

    report = review_mod.select_with_full_review(tmp_path, ["core.py"])
    # The transitive-import heuristic should fire: tests/test_app.py
    # imports app.py which imports core.py.
    must_paths = {s.test.path for s in report.selections if s.priority == "must"}
    assert "tests/test_app.py" in must_paths
    # The repox_artifact flag is captured in the report
    assert report.inputs.used_repox_artifact is True
