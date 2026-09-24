"""
Cortex Gateway — Auth Security Unit Tests (Phase 5).

Tests:
  - API key generation format and entropy
  - Key prefix extraction
  - HMAC-SHA256 hashing determinism
  - Constant-time verification (correct / incorrect key)
"""

from __future__ import annotations

import re

import pytest

from app.auth.security import (
    extract_key_prefix,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)

_TEST_PEPPER = "test-pepper-secret"


class TestAPIKeyGeneration:
    def test_key_starts_with_cxg_prefix(self):
        key = generate_api_key()
        assert key.startswith("cxg_"), f"Key should start with 'cxg_', got: {key[:10]}"

    def test_key_is_sufficiently_long(self):
        key = generate_api_key()
        # cxg_ (4) + token_urlsafe(32) gives ~43 chars → total ~47+
        assert len(key) >= 40, f"Key too short: {len(key)}"

    def test_key_is_url_safe(self):
        key = generate_api_key()
        # URL-safe base64 uses only A-Z, a-z, 0-9, -, _
        assert re.match(r"^cxg_[A-Za-z0-9_-]+$", key), f"Key has unsafe chars: {key}"

    def test_each_call_produces_unique_key(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100, "Duplicate keys generated — CSPRNG may be compromised"

    def test_no_sequential_pattern(self):
        """Keys must not be predictable from each other."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2
        # Verify random parts differ (strip the cxg_ prefix)
        assert key1[4:] != key2[4:]


class TestKeyPrefixExtraction:
    def test_prefix_is_first_20_chars(self):
        key = "cxg_xK9mP2nRvQw1sYdFaBcD"
        prefix = extract_key_prefix(key)
        assert prefix == "cxg_xK9mP2nRvQw1sYdF"
        assert len(prefix) == 20

    def test_prefix_starts_with_cxg(self):
        key = generate_api_key()
        prefix = extract_key_prefix(key)
        assert prefix.startswith("cxg_")

    def test_prefix_never_equals_full_key(self):
        key = generate_api_key()
        prefix = extract_key_prefix(key)
        assert prefix != key, "Prefix must not be the entire key"


class TestAPIKeyHashing:
    def test_same_key_same_hash(self):
        key = generate_api_key()
        h1 = hash_api_key(key, _TEST_PEPPER)
        h2 = hash_api_key(key, _TEST_PEPPER)
        assert h1 == h2, "Same key + pepper must always produce same hash"

    def test_different_keys_different_hashes(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        h1 = hash_api_key(key1, _TEST_PEPPER)
        h2 = hash_api_key(key2, _TEST_PEPPER)
        assert h1 != h2, "Different keys must produce different hashes"

    def test_different_pepper_different_hash(self):
        key = generate_api_key()
        h1 = hash_api_key(key, "pepper-a")
        h2 = hash_api_key(key, "pepper-b")
        assert h1 != h2, "Same key with different peppers must produce different hashes"

    def test_hash_is_hex_string(self):
        key = generate_api_key()
        h = hash_api_key(key, _TEST_PEPPER)
        assert re.match(r"^[0-9a-f]{64}$", h), f"Hash should be 64-char hex: {h}"

    def test_hash_is_sha256_length(self):
        key = generate_api_key()
        h = hash_api_key(key, _TEST_PEPPER)
        assert len(h) == 64, f"SHA-256 hex should be 64 chars, got {len(h)}"

    def test_plaintext_key_not_in_hash(self):
        """Hash must not contain any substring of the plaintext key."""
        key = generate_api_key()
        h = hash_api_key(key, _TEST_PEPPER)
        # The random part of the key should not appear in the hash
        assert key[4:20] not in h


class TestConstantTimeVerification:
    def test_correct_key_verifies_true(self):
        key = generate_api_key()
        stored = hash_api_key(key, _TEST_PEPPER)
        assert verify_api_key(key, stored, _TEST_PEPPER) is True

    def test_wrong_key_verifies_false(self):
        key = generate_api_key()
        wrong_key = generate_api_key()
        stored = hash_api_key(key, _TEST_PEPPER)
        assert verify_api_key(wrong_key, stored, _TEST_PEPPER) is False

    def test_wrong_pepper_verifies_false(self):
        key = generate_api_key()
        stored = hash_api_key(key, _TEST_PEPPER)
        assert verify_api_key(key, stored, "wrong-pepper") is False

    def test_empty_key_verifies_false(self):
        key = generate_api_key()
        stored = hash_api_key(key, _TEST_PEPPER)
        assert verify_api_key("", stored, _TEST_PEPPER) is False

    def test_tampered_hash_verifies_false(self):
        key = generate_api_key()
        stored = hash_api_key(key, _TEST_PEPPER)
        # Flip the last character
        tampered = stored[:-1] + ("a" if stored[-1] != "a" else "b")
        assert verify_api_key(key, tampered, _TEST_PEPPER) is False

    def test_uses_hmac_compare_digest(self):
        """Verify that the implementation uses hmac.compare_digest (not plain ==)."""
        import inspect

        from app.auth import security
        source = inspect.getsource(security.verify_api_key)
        assert "compare_digest" in source, (
            "verify_api_key must use hmac.compare_digest for constant-time comparison"
        )
