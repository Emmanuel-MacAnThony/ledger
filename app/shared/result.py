"""Result[T, E] — a use case returns EITHER a success value T OR one of its
declared errors E (a closed union, not an opaque object). Expected failures are
values, not exceptions; unexpected ones still raise. The API layer maps each Err
to an HTTP status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass
class Result(Generic[T, E]):
    value: T | None = None
    error: E | None = None

    @property
    def is_ok(self) -> bool:
        return self.error is None

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        return cls(value=value)

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        return cls(error=error)
