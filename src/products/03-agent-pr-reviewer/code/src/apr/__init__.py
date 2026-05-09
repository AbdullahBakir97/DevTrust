"""Agent-PR Reviewer (`apr`) - the Wave 2 lead bet of the DevTrust platform.

Consolidates the patterns from three existing GitHub Apps into one
deterministic, fast, AI-pattern-aware PR reviewer:

  - ai-quality-gate    -> AI-likelihood + verbose-pattern detection
  - pr-coach           -> coaching feedback (description quality, TODOs)
  - commit-craft       -> commit-message review and normalization

v0.0.1 ships the deterministic rule layer; LLM-backed review is layered
on top in v0.1+ once the rule output is stable enough to grade against.
"""

__version__ = "0.2.0"
