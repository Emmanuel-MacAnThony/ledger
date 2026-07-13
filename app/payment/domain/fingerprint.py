import hashlib
import json


def fingerprint(amount: int, currency: str, user_id: str) -> str:
    # Canonicalize to a stable JSON string (sorted keys, no whitespace) so the
    # hash depends only on the values, not on field order or formatting. JSON
    # escaping also stops a value like "1|USD" from colliding with a delimiter.
    canonical = json.dumps(
        {"amount": amount, "currency": currency, "user_id": user_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
