"""Postgres UnitOfWork — wraps the three repos over one connection so multi-table
writes (claim, terminal) commit together. Satisfies create_payment's UnitOfWork
interface structurally."""

from app.payment.infra.repositories.attempts_repo import PostgresAttemptsRepo
from app.payment.infra.repositories.keys_repo import PostgresKeysRepo
from app.payment.infra.repositories.payments_repo import PostgresPaymentsRepo


class PostgresUnitOfWork:
    def __init__(self, conn):
        # conn is checked out of the pool for the request; autocommit is OFF, so a
        # transaction opens on the first statement and lasts until commit/rollback.
        self._conn = conn
        self._committed = False
        self.keys = PostgresKeysRepo(conn)
        self.payments = PostgresPaymentsRepo(conn)
        self.attempts = PostgresAttemptsRepo(conn)

    def __enter__(self) -> "PostgresUnitOfWork":
        self._committed = False
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Roll back on exception or if the block never committed.
        if exc_type is not None or not self._committed:
            self._conn.rollback()
        return False

    def commit(self) -> None:
        self._conn.commit()
        self._committed = True

    def rollback(self) -> None:
        self._conn.rollback()
