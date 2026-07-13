"""Standard API response envelope + Result -> HTTP mapping. Every handler uses
this so success and error responses share one shape and one place sets the status.

  success -> {"data": <payload>, "error": null}
  failure -> {"data": null, "error": {"code": <ErrorName>, "message": <text>}}
"""

from typing import Any, Callable, TypeVar

from fastapi.responses import JSONResponse

from app.shared.result import Result

T = TypeVar("T")
E = TypeVar("E")


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": data, "error": None})


def error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": None, "error": {"code": code, "message": message}},
    )


def from_result(
    result: Result[T, E],
    *,
    serialize: Callable[[T], Any],
    status_for_error: Callable[[E], int],
    success_status: int = 200,
) -> JSONResponse:
    if result.is_ok:
        return ok(serialize(result.value), success_status)
    err = result.error
    # every declared error carries a .message; its class name is the stable code
    return error(type(err).__name__, getattr(err, "message", str(err)), status_for_error(err))
