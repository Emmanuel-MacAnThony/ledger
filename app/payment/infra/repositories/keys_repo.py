from app.payment.domain.entities.idempotency_key import IdempotencyKey
from app.payment.domain.states import ClaimOutcome, KeyState


class PostgresKeysRepo:
    """Satisfies create_payment's KeysRepo interface structurally (no import of it)."""

    def __init__(self, conn):
        self._conn = conn

    def get(self, key: str) -> IdempotencyKey | None:
        row = self._conn.execute(
            "SELECT key, state, request_hash, payment_id, created_at, started_at"
            " FROM idempotency_keys WHERE key = %s",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return IdempotencyKey(
            key=row[0], state=KeyState(row[1]), request_hash=row[2],
            payment_id=row[3], created_at=row[4], started_at=row[5],
        )

    def insert(self, key: IdempotencyKey) -> ClaimOutcome:
        # ON CONFLICT DO NOTHING = the UNIQUE claim without an exception aborting the
        # transaction. rowcount tells us whether WE won the insert or lost the race.
        cur = self._conn.execute(
            "INSERT INTO idempotency_keys"
            " (key, state, request_hash, payment_id, created_at, started_at)"
            " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (key) DO NOTHING",
            (key.key, key.state.value, key.request_hash, key.payment_id,
             key.created_at, key.started_at),
        )
        return ClaimOutcome.WON if cur.rowcount == 1 else ClaimOutcome.LOST

    def reset(self, key: IdempotencyKey) -> None:
        # Reclaim: overwrite the expired row in place (keeps the UNIQUE key unique).
        self._conn.execute(
            "UPDATE idempotency_keys SET state = %s, request_hash = %s, payment_id = %s,"
            " created_at = %s, started_at = %s WHERE key = %s",
            (key.state.value, key.request_hash, key.payment_id,
             key.created_at, key.started_at, key.key),
        )

    def set_terminal(self, key: str, state: KeyState) -> None:
        self._conn.execute(
            "UPDATE idempotency_keys SET state = %s WHERE key = %s",
            (state.value, key),
        )
