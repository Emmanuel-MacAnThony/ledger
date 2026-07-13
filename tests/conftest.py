"""
Shared pytest fixtures for the Ledger suite.

Fixtures to provide (documentation only — not implemented yet):

- db          : a clean Postgres schema per test — truncate idempotency_keys,
                payments, idempotency_attempts between tests so state never leaks.
- client      : an httpx.AsyncClient bound to the FastAPI app (in-process ASGI).
- processor   : handle to the mock processor, toggleable to SLOW / FAIL so tests
                can open the race window and exercise failure caching.
- make_payload: helper that builds a canonical {amount, currency, userId} body.
- idem_key    : helper that mints a fresh UUID per test.
"""
