"""
Happy path — a single, well-behaved payment.

Scenarios to cover (documentation only — not implemented yet):

- new key -> claim -> charge -> SUCCEEDED; returns 200 with the payment body.
- exact same key + same body, after completion -> replays the CACHED response
  verbatim, and the processor is NOT called a second time (one charge total).
- GET /payments/{id} returns the payment with its final status.
- the audit table records one attempt per hit, anchored on payment_id.
"""


def test_new_key_creates_payment():
    """First request with a fresh key creates one payment and returns 200."""
    ...


def test_repeat_same_request_replays_cached_response():
    """Same key + same body after completion returns the cached response, no 2nd charge."""
    ...


def test_get_payment_by_id():
    """GET /payments/{id} returns the payment and its terminal status."""
    ...
