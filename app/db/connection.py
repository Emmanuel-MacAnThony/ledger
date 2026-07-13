"""Shared DB connectivity. The pool is built once at the app entrance (main.py)
from Config and injected down — use cases never open connections themselves.
Per request, `with pool.connection() as conn:` checks one out and returns it."""

from psycopg_pool import ConnectionPool


def create_pool(dsn: str, min_size: int = 1, max_size: int = 10) -> ConnectionPool:
    # autocommit stays OFF on pooled connections so the UnitOfWork owns the
    # transaction boundaries (BEGIN on first statement, explicit commit/rollback).
    return ConnectionPool(conninfo=dsn, min_size=min_size, max_size=max_size, open=True)
