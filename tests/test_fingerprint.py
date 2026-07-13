"""
Request fingerprinting — same key must mean the same operation.

Scenarios to cover (documentation only — not implemented yet):

- same key + DIFFERENT body (amount or recipient changed) -> 409
  idempotency_key_reused; no charge, no cached response returned.
- same key + same body but with reordered / re-whitespaced fields -> treated as
  IDENTICAL (canonicalized before hashing) -> replays, no 409.
- missing Idempotency-Key header -> 400 (header is required).
- the 409 body never echoes the original request (no data leak).
"""


def test_same_key_different_body_returns_409():
    """Reusing a key with a different amount/recipient is rejected with 409."""
    ...


def test_reordered_but_identical_body_is_same():
    """Field order / whitespace differences hash the same and are treated as a retry."""
    ...


def test_missing_key_header_returns_400():
    """A request without the Idempotency-Key header is rejected with 400."""
    ...
