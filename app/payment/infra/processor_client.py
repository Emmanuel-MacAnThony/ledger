"""Processor client — the external side effect. Sends a charge with the per-payment
processor_key (which the processor dedups) and does the bounded backoff retry: it
returns a DEFINITE outcome, or UNKNOWN if retries are exhausted without one."""

import time

import httpx

from app.payment.domain.states import ChargeOutcome


class HttpProcessorClient:
    def __init__(self, base_url: str, max_attempts: int = 3,
                 base_backoff: float = 0.2, cap: float = 2.0, timeout: float = 5.0):
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._cap = cap
        self._timeout = timeout

    def charge(self, processor_key: str, amount: int, currency: str,
               user_id: str) -> ChargeOutcome:
        backoff = self._base_backoff
        for attempt in range(self._max_attempts):
            outcome = self._try_once(processor_key, amount, currency, user_id)
            if outcome is not None:
                return outcome            # DEFINITE (success / declined) — stop
            # ambiguous (no response OR 5xx: maybe charged) -> retry, same key -> dedup
            if attempt < self._max_attempts - 1:
                time.sleep(backoff)
                backoff = min(backoff * 2, self._cap)

        # Couldn't decide in this request. The caller leaves the key IN_FLIGHT; the
        # client's own later retry re-drives it once past the recovery timeout (the
        # worker is only a backstop if the client never comes back).
        return ChargeOutcome.UNKNOWN

    def _try_once(self, processor_key, amount, currency, user_id) -> ChargeOutcome | None:
        """A DEFINITE ChargeOutcome, or None if AMBIGUOUS (caller should retry)."""
        try:
            resp = httpx.post(
                f"{self._base_url}/charge",
                json={"processor_key": processor_key, "amount": amount,
                      "currency": currency, "user_id": user_id},
                timeout=self._timeout,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return None                   # no response at all — did it charge? unknown

        if resp.status_code == 200:       # definite: the processor decided
            return (ChargeOutcome.SUCCESS
                    if resp.json()["outcome"] == "success"
                    else ChargeOutcome.DECLINED)

        # 5xx (or anything non-200): the processor errored — it MAY have charged
        # before failing. Same unknown as a timeout -> ambiguous, retry.
        return None
