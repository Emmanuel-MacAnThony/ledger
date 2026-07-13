"""App-wide configuration. Built once at the app entrance (main.py) and passed
down to the use cases — never read from the environment deep inside the code."""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Config:
    # idempotency key reuse window: past this, a key reclaims as a new payment
    key_ttl: timedelta = timedelta(hours=24)
    # in-flight age past which the owner is presumed dead -> re-drive
    recovery_timeout: timedelta = timedelta(minutes=5)

    @classmethod
    def from_env(cls) -> "Config":
        # env overrides the defaults; wired up at the app entrance. TODO as needed.
        return cls()
