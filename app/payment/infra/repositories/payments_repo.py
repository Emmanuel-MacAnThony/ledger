from datetime import datetime

from app.payment.domain.entities.payment import Payment
from app.payment.domain.states import PaymentStatus


class PostgresPaymentsRepo:
    def __init__(self, conn):
        self._conn = conn

    def get(self, payment_id: str) -> Payment | None:
        row = self._conn.execute(
            "SELECT id, idempotency_key, processor_key, amount, currency, user_id, status, created_at"
            " FROM payments WHERE id = %s",
            (payment_id,),
        ).fetchone()
        if row is None:
            return None
        return Payment(
            id=row[0], idempotency_key=row[1], processor_key=row[2],
            amount=row[3], currency=row[4], user_id=row[5],
            status=PaymentStatus(row[6]), created_at=row[7],
        )

    def insert_pending(self, payment: Payment) -> None:
        self._conn.execute(
            "INSERT INTO payments"
            " (id, idempotency_key, processor_key, amount, currency, user_id, status, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (payment.id, payment.idempotency_key, payment.processor_key,
             payment.amount, payment.currency, payment.user_id,
             payment.status.value, payment.created_at),
        )

    def set_status(self, payment_id: str, status: PaymentStatus) -> None:
        self._conn.execute(
            "UPDATE payments SET status = %s WHERE id = %s",
            (status.value, payment_id),
        )

    def stale_in_flight(self, cutoff: datetime) -> list[Payment]:
        # Used by the worker (not create_payment). Pending payments older than cutoff.
        rows = self._conn.execute(
            "SELECT id, idempotency_key, processor_key, amount, currency, user_id, status, created_at"
            " FROM payments WHERE status = 'pending' AND created_at < %s",
            (cutoff,),
        ).fetchall()
        return [
            Payment(
                id=r[0], idempotency_key=r[1], processor_key=r[2],
                amount=r[3], currency=r[4], user_id=r[5],
                status=PaymentStatus(r[6]), created_at=r[7],
            )
            for r in rows
        ]
