"""The worker deployable — a standalone process (python -m worker.main), separate
from the API. Runs recover_stale on a timer: build infra once, sweep, sleep, repeat."""

import os
import time

from app.config import Config
from app.db.connection import create_pool
from app.payment.infra.clock import SystemClock
from app.payment.infra.processor_client import HttpProcessorClient
from app.payment.infra.unit_of_work import PostgresUnitOfWork
from app.payment.usecases.drive_payment.service import DrivePayment
from app.payment.usecases.recover_stale.service import RecoverStale


def run_once(pool, processor, clock, config) -> None:
    # One pooled connection per sweep. The reader (uow.payments) and the driver
    # share it; each re-drive is its own transaction inside.
    with pool.connection() as conn:
        uow = PostgresUnitOfWork(conn)
        driver = DrivePayment(uow, processor)
        result = RecoverStale(uow.payments, driver, clock, config).execute()
    print(f"[recover_stale] processed={result.processed} "
          f"settled={result.settled} unresolved={result.unresolved}", flush=True)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "postgres://ledger:ledger@localhost:5432/ledger")
    processor_url = os.getenv("PROCESSOR_URL", "http://localhost:9000")
    interval = float(os.getenv("SWEEP_INTERVAL_SECONDS", "10"))

    config = Config.from_env()
    pool = create_pool(dsn)
    processor = HttpProcessorClient(processor_url)
    clock = SystemClock()

    print("[worker] recover_stale loop starting", flush=True)
    while True:
        try:
            run_once(pool, processor, clock, config)
        except Exception as e:  # a sweep failure must not kill the loop
            print(f"[worker] sweep error: {e}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
