"""Prompt templates + response parsing for `ai-review:diff-comprehension`.

Kept in its own module so we can unit-test the prompt construction +
JSON parsing logic without ever instantiating the Anthropic SDK.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from apr.models import Finding, Severity

logger = logging.getLogger(__name__)


# Hard cap on diff size we send to the LLM. Diffs larger than this get
# truncated with a clear marker -- spending 50K input tokens on a
# generated lockfile change is rarely worth the cost.
DEFAULT_MAX_DIFF_CHARS = 60_000

# Cap on the LLM's reply size. v0.1.1 keeps it conservative so cost is
# predictable; bumps come once we have data.
DEFAULT_MAX_TOKENS = 1024


SYSTEM_PROMPT = (
    "You are a careful code reviewer. Your job is to identify places where "
    "a pull request's description does not accurately describe the diff -- "
    "claims of behavior that aren't reflected in the changes, scope creep "
    "the description hides, or missing mentions of breaking changes that "
    "are visible in the diff. Be conservative: it is better to surface "
    "no findings than to invent ones."
)


def build_prompt(
    *,
    diff: str,
    pr_title: str | None,
    pr_description: str | None,
    max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS,
) -> str:
    """Render the user-facing prompt content.

    The template asks the model for STRICT JSON. Failures to parse are
    not silently ignored -- we log them and return [] so the engine
    treats the run as 'no findings' rather than crashing.
    """
    if len(diff) > max_diff_chars:
        truncated = diff[:max_diff_chars]
        diff_section = (
            truncated
            + f"\n\n[... diff truncated from {len(diff):,} to {max_diff_chars:,} chars ...]"
        )
    else:
        diff_section = diff

    title_section = pr_title or "(no title)"
    description_section = (pr_description or "(no description)").strip()

    parts = [
        "## PR title",
        title_section,
        "",
        "## PR description",
        description_section,
        "",
        "## Diff",
        "```diff",
        diff_section,
        "```",
        "",
        "## Task",
        "Identify any places where the title or description **does not** match the "
        "actual diff. Common patterns to flag:",
        "  - claims of behavior that aren't reflected in the changes",
        "  - scope creep (changes outside what the description describes)",
        "  - missing mentions of breaking changes that ARE visible in the diff",
        "",
        "Output a single JSON object with this exact shape and nothing else:",
        "",
        "```json",
        "{",
        '  "findings": [',
        "    {",
        '      "severity": "info" | "warning" | "error",',
        '      "message": "<one sentence describing the mismatch>",',
        '      "file": "<repo-relative path or null>",',
        '      "line": <integer line number or null>',
        "    }",
        "  ]",
        "}",
        "```",
        "",
        'If you find no mismatches, return `{"findings": []}`. Do not include '
        "any prose outside the JSON object.",
    ]
    return "\n".join(parts)


_VALID_SEVERITIES: frozenset[str] = frozenset({"info", "warning", "error"})


def parse_response(text: str) -> list[Finding]:
    """Parse the model's reply into Finding objects.

    Strategy:
      1. Try `json.loads` on the whole text (the model usually obeys).
      2. If that fails, look for the first balanced `{...}` block and
         try to parse just that. Reasoning models sometimes wrap the
         JSON in prose despite our instructions.
      3. If parsing still fails OR the shape doesn't match, log and
         return [].

    All findings emerge with rule_id `ai-review:diff-comprehension` --
    the engine re-tags them on the way out, but doing it here too keeps
    the unit tests honest.
    """
    parsed = _try_parse_json(text)
    if parsed is None:
        logger.warning("could not parse LLM response as JSON: %r", text[:200])
        return []

    raw_findings = parsed.get("findings") if isinstance(parsed, dict) else None
    if not isinstance(raw_findings, list):
        logger.warning("LLM response missing 'findings' array: %r", text[:200])
        return []

    out: list[Finding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        sev_raw = item.get("severity")
        if sev_raw not in _VALID_SEVERITIES:
            continue
        message = item.get("message")
        if not isinstance(message, str) or not message.strip():
            continue
        file_val: str | None = None
        if isinstance(item.get("file"), str):
            file_val = item["file"]
        line_val: int | None = None
        if isinstance(item.get("line"), int) and item["line"] >= 1:
            line_val = item["line"]
        out.append(
            Finding(
                rule_id="ai-review:diff-comprehension",
                severity=_coerce_severity(sev_raw),
                category="ai-pattern",
                message=message.strip(),
                file=file_val,
                line=line_val,
            )
        )
    return out


def _coerce_severity(raw: object) -> Severity:
    """Tighten the type narrowing for mypy strict."""
    if raw == "info":
        return "info"
    if raw == "warning":
        return "warning"
    return "error"


def _try_parse_json(text: str) -> Any | None:
    """First attempt strict; then look for the first balanced {...}."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find the first balanced JSON object substring.
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = -1
                    continue
    return None
