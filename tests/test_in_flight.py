"""
In-flight coordination — a retry arrives while the original is still processing.

Scenarios to cover (documentation only — not implemented yet):

- processor set to SLOW; original request is mid-charge (state IN-FLIGHT, fresh).
  A concurrent retry with the same key gets "in progress / come back" (409),
  NOT a second charge.
- once the original completes, a later retry replays the cached response.
- the "come back" response is polite, not terminal — it never tells the client
  to stop retrying.
"""


def test_retry_during_processing_gets_come_back():
    """A fresh in-flight key returns 'come back' to a concurrent retry, no 2nd charge."""
    ...


def test_retry_after_completion_replays():
    """Once the original finishes, the next retry replays the cached response."""
    ...
