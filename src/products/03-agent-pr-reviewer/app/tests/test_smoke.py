"""Smoke + unit tests for apr-app v0.0.1.

Coverage:
  - security.verify          HMAC signature handling (good/bad/missing/dev)
  - handlers._format_comment Sticky comment formatting + emoji ladder
  - GET /, /health, /version routes
  - POST /webhooks/github    full flow with mocked GitHub: signed/unsigned,
                              opened vs synchronize, create + update comment,
                              file-content download triggers per-file rules
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from apr_app import __version__ as app_version
from apr_app.handlers import _format_comment, _verdict_emoji
from apr_app.security import compute_signature, verify
from fastapi.testclient import TestClient

from tests.conftest import WEBHOOK_SECRET, make_pull_request_payload

# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------


def test_verify_accepts_correct_signature() -> None:
    payload = b'{"hello":"world"}'
    sig = compute_signature(WEBHOOK_SECRET, payload)
    assert verify(WEBHOOK_SECRET, payload, sig) is True


def test_verify_rejects_wrong_signature() -> None:
    bad = "sha256=" + "0" * 64
    assert verify(WEBHOOK_SECRET, b"x", bad) is False


def test_verify_dev_mode_returns_true_when_secret_is_none() -> None:
    assert verify(None, b"anything", None) is True


def test_verify_rejects_wrong_prefix() -> None:
    payload = b"x"
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    assert verify(WEBHOOK_SECRET, payload, "sha1=" + mac) is False


# ---------------------------------------------------------------------------
# comment formatting
# ---------------------------------------------------------------------------


class _FakeStats:
    def __init__(
        self, *, info: int = 0, warning: int = 0, error: int = 0, critical: int = 0
    ) -> None:
        self.info = info
        self.warning = warning
        self.error = error
        self.critical = critical
        self.total = info + warning + error + critical
        self.blocking = error + critical


class _FakeFinding:
    def __init__(self, severity: str, file: str, line: int, rule_id: str, message: str) -> None:
        self.severity = severity
        self.file = file
        self.line = line
        self.rule_id = rule_id
        self.message = message


class _FakeReport:
    def __init__(
        self,
        *,
        stats: _FakeStats,
        findings: list[_FakeFinding],
    ) -> None:
        self.tool_version = "0.1.0"
        self.schema_version = "0.0.1"
        self.stats = stats
        self.findings = findings
        self.inputs = type("Inp", (), {"changed_files": ["x.py"]})()


def test_format_comment_clean_run_emits_no_findings_message() -> None:
    rpt = _FakeReport(stats=_FakeStats(), findings=[])
    body = _format_comment(rpt, "<!-- apr-app:sticky -->")
    assert "<!-- apr-app:sticky -->" in body
    assert "No findings" in body
    assert _verdict_emoji(rpt) == "✅"


def test_format_comment_with_findings_renders_table() -> None:
    rpt = _FakeReport(
        stats=_FakeStats(warning=1, error=1),
        findings=[
            _FakeFinding(
                "error",
                "src/foo.py",
                10,
                "syntax-error",
                "Python file does not parse: invalid syntax",
            ),
            _FakeFinding(
                "warning",
                "src/foo.py",
                3,
                "bare-except",
                "bare `except:` swallows all exceptions",
            ),
        ],
    )
    body = _format_comment(rpt, "<!-- apr-app:sticky -->")
    assert "src/foo.py" in body
    assert "syntax-error" in body
    assert "bare-except" in body
    assert "blocking finding" in body  # error counts as blocking


def test_verdict_emoji_ladder() -> None:
    assert _verdict_emoji(_FakeReport(stats=_FakeStats(critical=1), findings=[])) == "🛑"
    assert _verdict_emoji(_FakeReport(stats=_FakeStats(error=1), findings=[])) == "❌"
    assert _verdict_emoji(_FakeReport(stats=_FakeStats(warning=1), findings=[])) == "⚠️"
    assert _verdict_emoji(_FakeReport(stats=_FakeStats(info=1), findings=[])) == "ℹ️"  # noqa: RUF001
    assert _verdict_emoji(_FakeReport(stats=_FakeStats(), findings=[])) == "✅"


# ---------------------------------------------------------------------------
# basic HTTP routes
# ---------------------------------------------------------------------------


def test_root_endpoint(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "apr-app"
    assert body["version"] == app_version


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_version_endpoint(client: TestClient) -> None:
    resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "apr_app" in body and "apr_engine" in body


# ---------------------------------------------------------------------------
# webhook flow
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
    resp = _signed_post(client, make_pull_request_payload(), secret=None)
    assert resp.status_code == 401


def test_webhook_rejects_wrong_signature(client: TestClient) -> None:
    raw = json.dumps(make_pull_request_payload()).encode("utf-8")
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=" + "0" * 64,
        "Content-Type": "application/json",
    }
    resp = client.post("/webhooks/github", content=raw, headers=headers)
    assert resp.status_code == 401


def test_webhook_ignores_non_pull_request_events(client: TestClient) -> None:
    resp = _signed_post(client, {"zen": "..."}, event="ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_ignores_unhandled_pr_actions(client: TestClient) -> None:
    resp = _signed_post(client, make_pull_request_payload(action="closed"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_creates_comment_on_clean_pr(
    client: TestClient, mock_github: dict[str, Any]
) -> None:
    """A PR with one clean Python file should create a comment with 0 findings."""
    mock_github["pr_files"] = [
        {"filename": "good.py", "status": "modified"},
    ]
    mock_github["file_contents"] = {
        "good.py": b"def helper() -> int:\n    return 1\n",
    }
    mock_github["existing_comment_id"] = None

    resp = _signed_post(client, make_pull_request_payload(action="opened"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["action"] == "created"
    assert body["total"] == 0
    posted = mock_github["created_bodies"]
    assert len(posted) == 1
    assert "<!-- apr-app:sticky -->" in posted[0]


def test_webhook_creates_comment_with_findings_for_bad_file(
    client: TestClient, mock_github: dict[str, Any]
) -> None:
    """A PR touching a file with a bare-except clause should produce a finding."""
    mock_github["pr_files"] = [
        {"filename": "bad.py", "status": "modified"},
    ]
    mock_github["file_contents"] = {
        "bad.py": (
            b"def boom():\n    try:\n        return 1 / 0\n    except:\n        return -1\n"
        ),
    }

    resp = _signed_post(client, make_pull_request_payload(action="opened"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["warning"] >= 1
    posted = mock_github["created_bodies"][0]
    assert "bare-except" in posted


def test_webhook_updates_existing_sticky_comment(
    client: TestClient, mock_github: dict[str, Any]
) -> None:
    mock_github["pr_files"] = [{"filename": "good.py", "status": "modified"}]
    mock_github["file_contents"] = {"good.py": b"def f(): pass\n"}
    mock_github["existing_comment_id"] = 444

    resp = _signed_post(client, make_pull_request_payload(action="synchronize"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "updated"
    assert mock_github["created_bodies"] == []
    assert len(mock_github["updated_bodies"]) == 1
    cid, posted = mock_github["updated_bodies"][0]
    assert cid == 444
    assert "<!-- apr-app:sticky -->" in posted


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened", "ready_for_review"])
def test_webhook_handled_actions_match_design(
    client: TestClient, mock_github: dict[str, Any], action: str
) -> None:
    mock_github["pr_files"] = []
    resp = _signed_post(client, make_pull_request_payload(action=action))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_skipped_when_no_auth_configured() -> None:
    """Bare Settings (no PAT, no App auth) -> handler returns skipped, not 500."""
    from apr_app.config import Settings, reset_settings_cache
    from apr_app.main import create_app
    from pydantic import SecretStr

    reset_settings_cache()
    s = Settings(webhook_secret=SecretStr(WEBHOOK_SECRET))
    bare_client = TestClient(create_app(s))

    raw = json.dumps(make_pull_request_payload()).encode("utf-8")
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
