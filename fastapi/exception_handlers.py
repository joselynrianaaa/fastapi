import math

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.utils import is_body_allowed_for_status_code
from fastapi.websockets import WebSocket
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import WS_1008_POLICY_VIOLATION


def _encode_non_finite_float(value: float) -> float | str:
    # The rejected `input` echoed in a validation error can be NaN or +/-Infinity
    # (Python's JSON parser accepts those tokens in a request body). They are not
    # valid strict JSON, which `JSONResponse` enforces, so serializing them would
    # raise and turn a 422 into a 500. Represent them as strings, the same way the
    # offending value shows up for query parameters (e.g. "nan").
    if math.isfinite(value):
        return value
    return str(value)


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=headers
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(
                exc.errors(), custom_encoder={float: _encode_non_finite_float}
            )
        },
    )


async def websocket_request_validation_exception_handler(
    websocket: WebSocket, exc: WebSocketRequestValidationError
) -> None:
    await websocket.close(
        code=WS_1008_POLICY_VIOLATION, reason=jsonable_encoder(exc.errors())
    )