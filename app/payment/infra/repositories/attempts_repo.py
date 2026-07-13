from app.payment.domain.entities.attempt import Attempt


class PostgresAttemptsRepo:
    def __init__(self, conn):
        self._conn = conn

    def record(self, attempt: Attempt) -> None:
        # id is a BIGSERIAL and created_at defaults to now() — the DB fills them in.
        self._conn.execute(
            "INSERT INTO idempotency_attempts (payment_id, key, seen_state, source_ip)"
            " VALUES (%s, %s, %s, %s)",
            (attempt.payment_id, attempt.key, attempt.seen_state, attempt.source_ip),
        )
