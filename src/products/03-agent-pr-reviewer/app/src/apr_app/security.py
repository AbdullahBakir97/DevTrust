"""HMAC signature verification for incoming GitHub webhooks.

Identical contract to sts-app's security module.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="


def compute_signature(secret: str, payload: bytes) -> str:
    """Return the expected `sha256=<hex>` value for the given payload."""
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return SIGNATURE_PREFIX + mac.hexdigest()


def verify(secret: str | None, payload: bytes, signature_header: str | None) -> bool:
    """Constant-time comparison; True when secret is None (dev mode)."""
    if secret is None:
        return True
    if not signature_header or not signature_header.startswith(SIGNATURE_PREFIX):
        return False
    expected = compute_signature(secret, payload)
    return hmac.compare_digest(expected, signature_header)
