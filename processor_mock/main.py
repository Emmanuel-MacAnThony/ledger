"""The fake 'bank' — a standalone, controllable, idempotent processor.

Controlled by env PROCESSOR_MODE:
  success  (default) -> charges, returns success
  decline            -> definite "no", no money moved
  fail               -> transient 5xx (the client sees it as UNKNOWN)

Idempotent on processor_key: a key already charged replays its outcome and does
NOT charge again. That's the safety net the whole ledger design leans on.
"""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="processor-mock")

# processor_key -> definite outcome ("success" | "declined"). In-memory is fine for a mock.
_charged: dict[str, str] = {}


class ChargeRequest(BaseModel):
    processor_key: str
    amount: int
    currency: str
    user_id: str


@app.post("/charge")
def charge(req: ChargeRequest):
    # Dedup first: a known key replays its outcome, no second charge.
    if req.processor_key in _charged:
        return {"outcome": _charged[req.processor_key], "deduped": True}

    mode = os.getenv("PROCESSOR_MODE", "success")
    if mode == "fail":
        # transient failure — NOT remembered, so a retry can still resolve it
        raise HTTPException(status_code=500, detail="processor unavailable")

    outcome = "declined" if mode == "decline" else "success"
    _charged[req.processor_key] = outcome
    return {"outcome": outcome, "deduped": False}


@app.get("/charge/{processor_key}")
def get_charge(processor_key: str):
    # For reconciliation: "did this key charge?"
    if processor_key in _charged:
        return {"outcome": _charged[processor_key]}
    raise HTTPException(status_code=404, detail="not found")


@app.get("/health")
def health():
    return {"ok": True}
