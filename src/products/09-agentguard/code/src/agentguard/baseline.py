"""Baseline policies — opinionated starting points users can compose.

The OWASP Top-10 for Agentic Applications (December 2025) names ten
recurring failure modes for production agents. v0.0.1 ships a small
representative subset of deterministic deny rules covering the categories
most easily expressible without an expression DSL. v0.1 ships the
complete pack with finer-grained predicates.

Use these as building blocks: import a baseline policy, then add your
own allow rules at the top to whitelist the actions YOUR agent should
perform. Anything not explicitly allowed falls through to the conservative
default-deny.
"""

from __future__ import annotations

from agentguard.models import Policy, Rule


def deny_money_movement() -> Policy:
    """Block actions that move real money without explicit approval.

    Rules in this policy match common payment-processor tool names. Any
    agent attempting to charge a card, transfer funds, or refund through
    a covered tool is denied. Lift specific cases by adding your own
    Rule(effect='allow', tool='stripe.charge', when={'approval': True})
    BEFORE this policy in your composed rules list.
    """
    return Policy(
        name="deny-money-movement",
        description=(
            "Block payments, transfers, refunds. OWASP Top-10 for Agentic "
            "Applications: LLM05 (sensitive operations without authorization)."
        ),
        rules=[
            Rule(
                name="deny-stripe-charge",
                effect="deny",
                tool="stripe.*",
                reason=(
                    "Money movement via Stripe requires explicit human "
                    "approval. Add a top-of-policy allow rule with an "
                    "approval predicate to permit specific cases."
                ),
                tags=["owasp:llm05", "money", "stripe"],
            ),
            Rule(
                name="deny-bank-transfer",
                effect="deny",
                tool="bank.*",
                reason="Bank transfers require human approval per default policy.",
                tags=["owasp:llm05", "money", "bank"],
            ),
            Rule(
                name="deny-paypal-payout",
                effect="deny",
                tool="paypal.*",
                reason="PayPal payouts require human approval per default policy.",
                tags=["owasp:llm05", "money", "paypal"],
            ),
        ],
    )


def deny_destructive_filesystem() -> Policy:
    """Block destructive filesystem operations.

    Recursive deletion of arbitrary paths is the canonical "agent mishap"
    that ends up on Hacker News. v0.0.1 covers the obvious tool-name
    shapes; v0.1 adds path-pattern predicates so you can allow deletes
    inside scratch directories while denying everywhere else.
    """
    return Policy(
        name="deny-destructive-filesystem",
        description="Block recursive deletes, drops, and forced overwrites.",
        rules=[
            Rule(
                name="deny-fs-delete-recursive",
                effect="deny",
                tool="fs.delete",
                when={"recursive": True},
                reason=(
                    "Recursive deletion is destructive. Enumerate the "
                    "specific files to delete instead, or scope to a "
                    "scratch directory with an explicit allow rule."
                ),
                tags=["owasp:llm07", "filesystem", "destructive"],
            ),
            Rule(
                name="deny-fs-rmtree",
                effect="deny",
                tool="fs.rmtree",
                reason="rmtree is unconditionally destructive — denied by default.",
                tags=["owasp:llm07", "filesystem", "destructive"],
            ),
            Rule(
                name="deny-db-drop",
                effect="deny",
                tool="db.drop_*",
                reason="Database drops require human approval.",
                tags=["owasp:llm07", "database", "destructive"],
            ),
        ],
    )


def deny_credential_disclosure() -> Policy:
    """Block tool calls that would exfiltrate credentials or PII."""
    return Policy(
        name="deny-credential-disclosure",
        description="Block sending credentials / PII to external destinations.",
        rules=[
            Rule(
                name="deny-mail-send-with-secret",
                effect="deny",
                tool="mail.send",
                when={"contains_secret": True},
                reason=(
                    "Outbound mail flagged as containing a secret is "
                    "denied by default. The agent should redact before "
                    "constructing the call, or your runtime should pre-"
                    "screen and set contains_secret=True on detection."
                ),
                tags=["owasp:llm02", "secrets", "mail"],
            ),
            Rule(
                name="deny-http-post-credentials",
                effect="deny",
                tool="http.post",
                when={"body_contains_credentials": True},
                reason=(
                    "HTTP POST flagged as carrying credentials in the body is denied by default."
                ),
                tags=["owasp:llm02", "secrets", "http"],
            ),
        ],
    )


def baseline_starter_policy() -> Policy:
    """A small composed policy combining the three baseline groups.

    Drop this into your agent runtime and you get conservative defaults:
    no money movement, no destructive filesystem ops, no credential
    exfiltration. Add your own allow rules ABOVE these in your final
    composed Policy to permit whatever your agent legitimately needs to
    do.
    """
    rules: list[Rule] = []
    for sub in (
        deny_money_movement(),
        deny_destructive_filesystem(),
        deny_credential_disclosure(),
    ):
        rules.extend(sub.rules)
    return Policy(
        name="agentguard-baseline-starter",
        description=(
            "Composed baseline policy: deny money movement, destructive "
            "filesystem ops, and credential disclosure. Compose with your "
            "own allow rules placed BEFORE these to permit specific cases."
        ),
        rules=rules,
    )
