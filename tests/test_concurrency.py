"""
The race — concurrent requests with the SAME key.

This is the test that proves the whole design. If only one of these matters,
it's this file.

Scenarios to cover (documentation only — not implemented yet):

- Fire N simultaneous requests, same key + same body, via asyncio.gather.
  Assert EXACTLY ONE payments row is created (the UNIQUE constraint is the lock).
- Assert EXACTLY ONE charge reached the processor (no double charge).
- The winner returns 200; the losers get either the cached response (if the
  winner already finished) or "in-flight / come back" (if still processing).
- No loser ever creates a second payment or a second charge.
"""


def test_simultaneous_same_key_creates_one_payment():
    """N parallel same-key requests -> exactly one payments row."""
    ...


def test_simultaneous_same_key_charges_once():
    """N parallel same-key requests -> the processor is hit exactly once."""
    ...


def test_losers_get_cached_or_come_back():
    """Losing racers receive the cached response or an in-flight 409, never a new charge."""
    ...
