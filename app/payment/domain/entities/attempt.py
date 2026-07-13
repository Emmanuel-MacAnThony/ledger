from dataclasses import dataclass
from datetime import datetime


@dataclass
class Attempt:
    id: str
    payment_id: str                 # anchor — the audit hangs off the payment, not the reused key
    key: str                        # the client key sent (context)
    seen_state: str                 # a KeyState value, or "new" for the first hit
    source_ip: str
    created_at: datetime
