"""
Crash recovery, re-drive, reconciliation — the stale in-flight cases.

Scenarios to cover (documentation only — not implemented yet):

- simulate a crash: leave a key IN-FLIGHT past the recovery timeout (stale).
- LAZY recovery: the next retry re-drives with the SAME processor key ->
  the idempotent processor dedupes -> no double charge -> key reaches SUCCEEDED.
- PROACTIVE recovery: the worker sweeps a stale in-flight key nobody returned to.
- RECONCILIATION: an abandoned PENDING payment (client gave up, money maybe
  moved) is resolved by the worker querying the processor for its processor_key.
- ATOMICITY: the terminal write lands state + cached response together; a
  rolled-back terminal write leaves the key IN-FLIGHT (recoverable), never a
  SUCCEEDED-with-no-response.
- fresh vs stale split: an in-flight key YOUNGER than the recovery timeout is
  NOT re-driven (owner presumed alive -> "come back").
"""


def test_stale_in_flight_is_redriven_lazily():
    """A retry landing on a stale in-flight key takes over and finishes it."""
    ...


def test_redrive_does_not_double_charge():
    """Re-driving with the same processor key produces exactly one charge."""
    ...


def test_worker_reconciles_abandoned_payment():
    """The worker resolves a pending payment nobody returned to by asking the processor."""
    ...


def test_terminal_write_is_atomic():
    """A failed terminal write leaves IN-FLIGHT, never SUCCEEDED-without-response."""
    ...


def test_fresh_in_flight_is_not_redriven():
    """An in-flight key younger than the recovery timeout gets 'come back', not takeover."""
    ...
