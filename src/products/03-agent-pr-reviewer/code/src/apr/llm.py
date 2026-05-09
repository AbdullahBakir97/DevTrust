"""LLM provider interface for AI-backed apr rules.

  - `LLMProvider`        Protocol every backend implements
  - `NullProvider`       returns no findings; used when AI is disabled
  - `AnthropicProvider`  Claude-backed provider (real, v0.1.1+)

The rule modules talk to this interface, never to a vendor SDK directly.
Swapping providers (Anthropic / OpenAI / Bedrock / a local model) is a
matter of writing a new `LLMProvider` implementation -- not touching the
rule code or the engine.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from apr.models import Finding
from apr.prompts import (
    DEFAULT_MAX_DIFF_CHARS,
    DEFAULT_MAX_TOKENS,
    SYSTEM_PROMPT,
    build_prompt,
    parse_response,
)

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Anything that can answer 'does this PR description match the diff'."""

    name: str

    def analyze_diff(
        self,
        diff: str,
        pr_title: str | None,
        pr_description: str | None,
    ) -> list[Finding]:
        """Return findings (possibly empty) about diff/description coherence.

        Implementations MUST be idempotent and side-effect-free other than
        outbound HTTP. They MUST handle their own timeouts and rate limits;
        the engine treats any exception as 'no findings' and continues.
        """
        ...


class NullProvider:
    """No-op provider. Returned when AI is disabled or no key configured."""

    name = "null"

    def analyze_diff(
        self,
        diff: str,
        pr_title: str | None,
        pr_description: str | None,
    ) -> list[Finding]:
        return []


class AnthropicProvider:
    """Anthropic Claude as the LLM backend.

    Uses the official `anthropic` Python SDK (Messages API, non-streaming).
    The provider builds a JSON-shaped prompt via `apr.prompts.build_prompt`,
    parses the reply via `apr.prompts.parse_response`, and returns
    `Finding` rows that the engine re-namespaces under
    `ai-review:diff-comprehension`.

    Cost / safety:
      - Diff is truncated to `max_diff_chars` (default 60,000) before
        sending. A typical PR fits comfortably; runaway lockfile diffs
        are bounded.
      - `max_tokens` on the reply is capped (default 1024). Plenty for
        a JSON list of findings; not enough for the model to spiral.
      - On any SDK exception (auth, rate limit, network), we log and
        return [] rather than letting the engine die.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS,
        client: Any | None = None,
    ) -> None:
        try:
            import anthropic  # noqa: F401  -- intentional probe
        except ImportError as exc:
            raise RuntimeError(
                "AnthropicProvider requires the `anthropic` package. "
                "Install with `pip install apr[ai]` or "
                "`uv add anthropic` in this workspace."
            ) from exc
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.max_diff_chars = max_diff_chars
        # Tests inject `client`. Production builds a fresh client per provider.
        self._client = client

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from anthropic import Anthropic

        self._client = Anthropic(api_key=self.api_key)
        return self._client

    def analyze_diff(
        self,
        diff: str,
        pr_title: str | None,
        pr_description: str | None,
    ) -> list[Finding]:
        prompt = build_prompt(
            diff=diff,
            pr_title=pr_title,
            pr_description=pr_description,
            max_diff_chars=self.max_diff_chars,
        )
        try:
            client = self._ensure_client()
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            logger.warning("AnthropicProvider request failed: %s", exc)
            return []

        text = _extract_text(resp)
        if text is None:
            return []
        return parse_response(text)


def _extract_text(resp: Any) -> str | None:
    """Pull the text body out of an `anthropic.Message` response.

    The SDK exposes `.content` as a list of content blocks; the simplest
    case is one `text` block. We concatenate all text-shaped blocks
    together for robustness against future models that prepend a
    'thinking' segment or similar.
    """
    content = getattr(resp, "content", None)
    if content is None:
        return None
    pieces: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", None)
            if isinstance(text, str):
                pieces.append(text)
    if not pieces:
        return None
    return "\n".join(pieces)


def build_provider(name: str | None, api_key: str | None) -> LLMProvider:
    """Map a provider name to a concrete provider instance.

    Returns NullProvider when the input doesn't name a real provider or
    when credentials are missing -- the engine never raises because the
    operator forgot to set an env var.
    """
    if not name or name == "null":
        return NullProvider()
    if name == "anthropic":
        # Allow a per-process model override via env var.
        model = os.environ.get("APR_ANTHROPIC_MODEL", "claude-sonnet-4-6")
        if not api_key:
            return NullProvider()
        try:
            return AnthropicProvider(api_key=api_key, model=model)
        except RuntimeError:
            return NullProvider()
    return NullProvider()
