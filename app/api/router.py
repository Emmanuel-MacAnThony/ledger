from dataclasses import dataclass

from fastapi import FastAPI

from app.api.handlers.admin_handler import AdminHandler
from app.api.handlers.payment_handler import PaymentHandler


@dataclass
class RouterDeps:
    payment: PaymentHandler
    admin: AdminHandler


def register_routes(app: FastAPI, deps: RouterDeps) -> None:
    # Each handler owns its own route registration.
    deps.payment.register_routes(app)
    deps.admin.register_routes(app)
