"""Composition root — build config + infra once, wire the factory into handlers,
register routes. Nothing deep in the code opens connections or reads env itself."""

import os

from fastapi import FastAPI
from psycopg import Connection

from app.api.handlers.payment_handler import PaymentHandler, PaymentHandlerDeps
from app.api.router import RouterDeps, register_routes
from app.config import Config
from app.db.connection import create_pool
from app.payment.infra.clock import SystemClock
from app.payment.infra.idgen import UuidGen
from app.payment.infra.processor_client import HttpProcessorClient
from app.payment.infra.repositories.payments_repo import PostgresPaymentsRepo
from app.payment.infra.unit_of_work import PostgresUnitOfWork
from app.payment.usecases.create_payment.service import CreatePayment
from app.payment.usecases.drive_payment.service import DrivePayment
from app.payment.usecases.get_payment.service import GetPayment


def create_app() -> FastAPI:
    dsn = os.getenv("DATABASE_URL", "postgres://ledger:ledger@localhost:5432/ledger")
    processor_url = os.getenv("PROCESSOR_URL", "http://localhost:9000")

    config = Config.from_env()
    pool = create_pool(dsn)
    clock, idgen = SystemClock(), UuidGen()
    processor = HttpProcessorClient(processor_url)

    # Per-request use cases: bind a request-scoped connection to the singletons.
    def make_create_payment(conn: Connection) -> CreatePayment:
        uow = PostgresUnitOfWork(conn)                 # shared by the claim + the driver
        driver = DrivePayment(uow, processor)
        return CreatePayment(uow, driver, clock, idgen, config)

    def make_get_payment(conn: Connection) -> GetPayment:
        return GetPayment(PostgresPaymentsRepo(conn))

    app = FastAPI(title="ledger")
    register_routes(app, RouterDeps(
        payment=PaymentHandler(PaymentHandlerDeps(
            pool=pool,
            make_create_payment=make_create_payment,
            make_get_payment=make_get_payment,
        )),
    ))
    return app


app = create_app()
