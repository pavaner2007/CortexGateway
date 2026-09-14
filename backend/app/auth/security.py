"""
Cortex Gateway — API Key Security Utilities (Phase 5).

Provides:
  generate_api_key()     — cryptographically secure key generation
  extract_key_prefix()   — safe non-secret identifier for display/logs
  hash_api_key()         — HMAC-SHA256 with server-side pepper
  verify_api_key()       — constant-time comparison

## Hashing Strategy

We use HMAC-SHA256 with a server-side pepper (secret stored in env config)
rather than bcrypt or argon2:

- API keys have 256 bits of entropy (secrets.token_urlsafe(32) = 43 chars,
  ~258 bits). At this entropy level bcrypt's slowness provides no additional
  security — an attacker who steals the DB also needs the pepper.
- HMAC-SHA256 is fast enough to compute on every request without latency impact.
- The pepper means a DB-only breach reveals nothing; the attacker needs the
  pepper AND the DB to attempt any verification.
- hmac.compare_digest() ensures constant-time comparison, preventing
  timing-based side-channel attacks.

Key format:
  cxg_<secrets.token_urlsafe(32)>
  e.g. cxg_xK9mP2nRvQw1sYdFaBcD3eEfGhIjKlMnOpQ

Prefix stored in DB (first 20 chars of full key):
  cxg_xK9mP2nRvQw1sYdF  (safe to display; NOT the secret)
"""

from __future__ import annotations

import hmac
import hashlib
import secrets


# API key prefix identifies Cortex Gateway keys visually in logs / UIs
_KEY_PREFIX = "cxg_"
# Number of random bytes → token_urlsafe produces ~1.33× this in chars
_KEY_RANDOM_BYTES = 32
# How many characters of the full key to store as the visible prefix
_PREFIX_DISPLAY_LENGTH = 20


def generate_api_key() -> str:
    """
    Generate a cryptographically secure API key.

    Uses Python's secrets module (CSPRNG) which reads from the OS
    entropy source (/dev/urandom on Linux, CryptGenRandom on Windows).

    Returns a URL/header-safe string. Never use timestamps, sequential IDs,
    or random.random() for key generation.
    """
    random_part = secrets.token_urlsafe(_KEY_RANDOM_BYTES)
    return f"{_KEY_PREFIX}{random_part}"


def extract_key_prefix(api_key: str) -> str:
    """
    Return the non-secret display prefix of an API key.

    This prefix is safe to store, log, and return in API responses.
    It allows administrators to identify a key without knowing the secret.

    Example:
        cxg_xK9mP2nRvQw1sYdFaBcD3eEfGhIjKlMnOpQ
        → cxg_xK9mP2nRvQw1sYdF
    """
    return api_key[:_PREFIX_DISPLAY_LENGTH]


def hash_api_key(plaintext_key: str, pepper: str) -> str:
    """
    Produce a deterministic HMAC-SHA256 hash of the API key.

    Args:
        plaintext_key: The full plaintext API key (never stored).
        pepper:        Server-side secret from environment config.
                       Never log or return this value.

    Returns:
        Hex-encoded HMAC-SHA256 digest suitable for database storage.
    """
    return hmac.new(
        key=pepper.encode("utf-8"),
        msg=plaintext_key.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_api_key(plaintext_key: str, stored_hash: str, pepper: str) -> bool:
    """
    Verify a plaintext API key against its stored hash.

    Uses hmac.compare_digest() for constant-time comparison, preventing
    timing-based side-channel attacks that could leak hash information.

    Args:
        plaintext_key: The raw API key from the Authorization header.
        stored_hash:   The HMAC-SHA256 digest stored in the database.
        pepper:        Server-side secret from environment config.

    Returns:
        True if the key is valid, False otherwise.
    """
    computed = hash_api_key(plaintext_key, pepper)
    return hmac.compare_digest(computed, stored_hash)
