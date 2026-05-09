"""Smoke + unit tests for whychanged v0.0.1."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from whychanged import __version__
from whychanged.cli import _parse_window, app
from whychanged.engine import (
    _describe_recency,
    _file_bonus,
    _recency_score,
)
from whychanged.engine import (
    explain as run_explain,
)
from whychanged.models import (
    SCHEMA_VERSION,
    Change,
)
from whychanged.providers import GitChangeProvider, _parse_git_log

runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI window parsing
# ---------------------------------------------------------------------------


def test_parse_window_minutes_default() -> None:
    assert _parse_window("30") == timedelta(minutes=30)


def test_parse_window_explicit_minutes() -> None:
    assert _parse_window("90m") == timedelta(minutes=90)


def test_parse_window_hours() -> None:
    assert _parse_window("2h") == timedelta(hours=2)


def test_parse_window_days() -> None:
    assert _parse_window("3d") == timedelta(days=3)


def test_parse_window_rejects_garbage() -> None:
    import typer

    with pytest.raises(typer.BadParameter):
        _parse_window("yesterday")


# ---------------------------------------------------------------------------
# Engine ranking
# ---------------------------------------------------------------------------


def test_recency_score_decays_over_time(now: datetime) -> None:
    s_now = _recency_score(now, now)
    s_15 = _recency_score(now - timedelta(minutes=15), now)
    s_60 = _recency_score(now - timedelta(minutes=60), now)
    assert s_now == pytest.approx(1.0)
    assert s_15 < s_now
    assert s_60 < s_15


def test_recency_score_zero_for_post_incident_changes(now: datetime) -> None:
    """Changes AFTER the incident never get credit."""
    score = _recency_score(now + timedelta(minutes=5), now)
    assert score == 0.0


def test_file_bonus_fires_when_files_overlap() -> None:
    bonus, reason = _file_bonus(
        ["src/api/models.py", "tests/test_models.py"],
        {"src/api/models.py"},
    )
    assert bonus > 0
    assert reason is not None
    assert "src/api/models.py" in reason


def test_file_bonus_zero_when_no_overlap() -> None:
    bonus, reason = _file_bonus(["src/other.py"], {"src/api/models.py"})
    assert bonus == 0.0
    assert reason is None


def test_describe_recency_human_readable(now: datetime) -> None:
    assert "before incident" in _describe_recency(now - timedelta(minutes=2), now)
    assert "before incident" in _describe_recency(now - timedelta(hours=3), now)
    assert "before incident" in _describe_recency(now - timedelta(days=2), now)


def test_explain_ranks_recent_change_higher_than_old(
    sample_changes: list[Change], now: datetime, empty_repo: Path
) -> None:
    """The 2-min-ago commit must outrank the 8-hour-ago flag toggle."""

    class _Static:
        name = "static"

        def __init__(self, changes: list[Change]) -> None:
            self._changes = changes

        def changes(self, since: datetime, until: datetime) -> list[Change]:
            return [c for c in self._changes if since <= c.timestamp <= until]

    report = run_explain(
        repo_root=empty_repo,
        providers=[_Static(sample_changes)],
        incident_at=now,
        service="api",
        window=timedelta(hours=12),
    )
    assert report.total >= 3
    top = report.top_culprit
    assert top is not None
    assert top.change.summary.startswith("Tighten validation")


def test_explain_service_files_boost_score(
    sample_changes: list[Change], now: datetime, empty_repo: Path
) -> None:
    """The config change touches our service file -> score outranks the
    older deps bump even though it's slightly older than the deploy."""

    class _Static:
        name = "static"

        def __init__(self, changes: list[Change]) -> None:
            self._changes = changes

        def changes(self, since: datetime, until: datetime) -> list[Change]:
            return [c for c in self._changes if since <= c.timestamp <= until]

    report = run_explain(
        repo_root=empty_repo,
        providers=[_Static(sample_changes)],
        incident_at=now,
        service="api",
        service_files={"k8s/api/deployment.yaml"},
        window=timedelta(hours=12),
    )
    # The config change with file overlap should outrank the dep bump.
    by_kind = {rc.change.kind: rc.score for rc in report.ranked}
    assert by_kind["config"] > by_kind["dependency"]


def test_explain_handles_provider_exception(now: datetime, empty_repo: Path) -> None:
    """A provider that raises must not crash the report."""

    class _Boom:
        name = "boom"

        def changes(self, since: datetime, until: datetime) -> list[Change]:
            raise RuntimeError("provider down")

    class _Working:
        name = "ok"

        def changes(self, since: datetime, until: datetime) -> list[Change]:
            return [
                Change(
                    kind="deploy",
                    source="git",
                    timestamp=now - timedelta(minutes=3),
                    summary="ok one",
                ),
            ]

    report = run_explain(
        repo_root=empty_repo,
        providers=[_Boom(), _Working()],
        incident_at=now,
        window=timedelta(hours=1),
    )
    assert report.total == 1
    assert report.ranked[0].change.summary == "ok one"


# ---------------------------------------------------------------------------
# Git provider
# ---------------------------------------------------------------------------


def test_git_provider_returns_empty_when_not_a_repo(empty_repo: Path) -> None:
    p = GitChangeProvider(repo_root=empty_repo)
    out = p.changes(datetime.now(UTC) - timedelta(hours=1), datetime.now(UTC))
    assert out == []


def test_git_provider_parses_log_output() -> None:
    raw = (
        "abc1234567890abcdef1234567890abcdef123456\t2026-05-08T14:25:00+00:00\tabdullah\tTighten validation\n"
        "src/api/models.py\n"
        "src/api/views.py\n"
        "\n"
        "def4567890abcdef1234567890abcdef12345678\t2026-05-08T13:00:00+00:00\trenovate[bot]\tBump httpx\n"
        "pyproject.toml\n"
    )
    changes = _parse_git_log(raw)
    assert len(changes) == 2
    first = changes[0]
    assert first.summary == "Tighten validation"
    assert first.actor == "abdullah"
    assert first.files == ["src/api/models.py", "src/api/views.py"]
    assert first.kind == "deploy"


def test_git_provider_handles_empty_output() -> None:
    assert _parse_git_log("") == []


def test_git_provider_uses_subprocess(empty_repo: Path) -> None:
    """Confirms GitChangeProvider invokes git log when the repo looks like one."""
    (empty_repo / ".git").mkdir()
    raw = (
        "abc1234567890abcdef1234567890abcdef123456\t2026-05-08T14:25:00+00:00\tabdullah\tTighten validation\n"
        "src/api/models.py\n\n"
    )

    class _Result:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    with patch.object(subprocess, "run", return_value=_Result(raw)) as mock_run:
        p = GitChangeProvider(repo_root=empty_repo)
        out = p.changes(
            datetime(2026, 5, 8, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 8, 23, 59, tzinfo=UTC),
        )
    assert mock_run.called
    assert len(out) == 1
    assert out[0].source == "git"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_version_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_explain_writes_artifacts(tmp_path: Path) -> None:
    """Run against a non-git tmp_path -- producer returns [] but we should
    still write a valid JSON + Markdown."""
    result = runner.invoke(
        app,
        ["explain", "--repo", str(tmp_path), "--since", "1h"],
    )
    assert result.exit_code == 0, result.stdout
    json_path = tmp_path / ".whychanged" / "report.json"
    md_path = tmp_path / ".whychanged" / "report.md"
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.0.1"
    assert data["tool_version"] == __version__


def test_cli_explain_quiet_is_quiet(tmp_path: Path) -> None:
    result = runner.invoke(app, ["explain", "--repo", str(tmp_path), "--since", "1h", "--quiet"])
    assert result.exit_code == 0
    assert "WhyChanged" not in result.stdout


def test_schema_version_pinned_and_tool_version_is_semver() -> None:
    """Schema is a stability contract -- pin it strictly. Tool version
    moves forward independently, so just sanity-check the shape."""
    import re as _re

    assert SCHEMA_VERSION == "0.0.1"
    assert _re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", __version__) is not None


def test_cli_explain_rejects_bad_incident_at(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["explain", "--repo", str(tmp_path), "--incident-at", "yesterday"],
    )
    assert result.exit_code != 0


def test_cli_explain_with_service_file_does_not_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "explain",
            "--repo",
            str(tmp_path),
            "--since",
            "1h",
            "--service",
            "api",
            "--service-file",
            "src/api/models.py",
            "--service-file",
            "src/api/views.py",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# v0.1.0: GitHubDeploymentsProvider
# ---------------------------------------------------------------------------


def _gh_deployment(
    *,
    created_at: str,
    ref: str = "main",
    environment: str = "production",
    description: str = "Deploy from CI",
    creator_login: str | None = "abdullah",
    url: str = "https://api.github.test/repos/o/r/deployments/1",
) -> dict[str, object]:
    """Build a GitHub-API-shaped deployment dict for tests."""
    creator: dict[str, object] | None = None
    if creator_login is not None:
        creator = {"login": creator_login, "id": 1}
    return {
        "id": 1,
        "ref": ref,
        "environment": environment,
        "description": description,
        "created_at": created_at,
        "creator": creator,
        "url": url,
    }


def test_github_provider_maps_deployment_to_change() -> None:
    """One deployment row produces one well-formed Change."""
    import httpx as _httpx
    from whychanged.providers_github import GitHubDeploymentsProvider

    transport = _httpx.MockTransport(
        lambda req: _httpx.Response(
            200,
            json=[
                _gh_deployment(
                    created_at="2026-05-08T14:25:00Z",
                    ref="abc1234",
                    description="Deploy commit abc1234",
                ),
            ],
        )
    )
    client = _httpx.Client(base_url="https://api.github.test", transport=transport)
    provider = GitHubDeploymentsProvider(owner="o", repo="r", token="fake", client=client)

    since = datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
    until = datetime(2026, 5, 8, 23, 59, tzinfo=UTC)
    changes = provider.changes(since, until)
    assert len(changes) == 1
    c = changes[0]
    assert c.kind == "deploy"
    assert c.source == "github-deployments"
    assert c.actor == "abdullah"
    assert "production" in c.summary
    assert "abc1234" in c.summary
    assert c.url is not None


def test_github_provider_filters_by_window() -> None:
    """Deployments outside [since, until] are dropped; pagination stops
    once we cross `since` (deployments come newest-first)."""
    import httpx as _httpx
    from whychanged.providers_github import GitHubDeploymentsProvider

    rows = [
        _gh_deployment(created_at="2026-05-09T12:00:00Z"),  # too new
        _gh_deployment(created_at="2026-05-08T15:00:00Z"),  # in window
        _gh_deployment(created_at="2026-05-08T13:00:00Z"),  # in window
        _gh_deployment(created_at="2026-05-01T10:00:00Z"),  # too old -> stops paging
    ]
    transport = _httpx.MockTransport(lambda req: _httpx.Response(200, json=rows))
    client = _httpx.Client(base_url="https://api.github.test", transport=transport)
    provider = GitHubDeploymentsProvider(owner="o", repo="r", token="fake", client=client)

    since = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    until = datetime(2026, 5, 9, 0, 0, tzinfo=UTC)
    changes = provider.changes(since, until)
    # Only the two in-window deployments survive.
    assert len(changes) == 2
    timestamps = [c.timestamp for c in changes]
    assert all(since <= t <= until for t in timestamps)


def test_github_provider_handles_api_error_silently() -> None:
    """A 401/500 from GitHub must reduce to [] -- never break the report."""
    import httpx as _httpx
    from whychanged.providers_github import GitHubDeploymentsProvider

    transport = _httpx.MockTransport(lambda req: _httpx.Response(500, json={"message": "boom"}))
    client = _httpx.Client(base_url="https://api.github.test", transport=transport)
    provider = GitHubDeploymentsProvider(owner="o", repo="r", token="fake", client=client)
    out = provider.changes(
        datetime(2026, 5, 8, 0, 0, tzinfo=UTC),
        datetime(2026, 5, 9, 0, 0, tzinfo=UTC),
    )
    assert out == []


def test_github_provider_handles_network_failure_silently() -> None:
    """A connection error must reduce to [], not propagate."""
    import httpx as _httpx
    from whychanged.providers_github import GitHubDeploymentsProvider

    def boom(_req: _httpx.Request) -> _httpx.Response:
        raise _httpx.ConnectError("dns down")

    transport = _httpx.MockTransport(boom)
    client = _httpx.Client(base_url="https://api.github.test", transport=transport)
    provider = GitHubDeploymentsProvider(owner="o", repo="r", token="fake", client=client)
    assert (
        provider.changes(
            datetime(2026, 5, 8, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 9, 0, 0, tzinfo=UTC),
        )
        == []
    )


def test_github_provider_token_picked_up_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """When `token=None`, the conventional env var fills in."""
    from whychanged.providers_github import GitHubDeploymentsProvider

    monkeypatch.setenv("WHYCHANGED_GITHUB_TOKEN", "from-env")
    provider = GitHubDeploymentsProvider(owner="o", repo="r")
    assert provider.token == "from-env"


def test_github_provider_token_falls_back_to_github_token_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whychanged.providers_github import GitHubDeploymentsProvider

    monkeypatch.delenv("WHYCHANGED_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ci-token")
    provider = GitHubDeploymentsProvider(owner="o", repo="r")
    assert provider.token == "ci-token"


def test_cli_explain_rejects_bad_github_repo_format(tmp_path: Path) -> None:
    """`--github-repo no-slash-here` must be rejected with a clear error."""
    result = runner.invoke(
        app,
        [
            "explain",
            "--repo",
            str(tmp_path),
            "--since",
            "1h",
            "--github-repo",
            "no-slash-here",
        ],
    )
    assert result.exit_code != 0


def test_whychanged_version_is_valid_semver() -> None:
    """Don't hardcode the version -- bumps shouldn't need test edits."""
    import re as _re

    from whychanged import __version__

    assert _re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", __version__) is not None
