import typing
from starlette import routing
from starlette.concurrency import run_in_threadpool
from starlette.routing import iscoroutinefunction_or_partial
from starlette.types import ASGIApp, Receive, Scope, Send
from src.utils.functions import now
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.openapi import utils
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.api.v1.endpoints import router as v1_router

from src.settings.config import APPLICATION
from src.settings.event import (
    create_start_app_handler, create_stop_app_handler,
)
# from app.settings.middleware import middleware_setting
from src.utils.error_messages import VALIDATE_ERROR


def request_response(func: typing.Callable) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    is_coroutine = iscoroutinefunction_or_partial(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive=receive, send=send)
        request.start_time = now()

        if is_coroutine:
            response = await func(request)
        else:
            response = await run_in_threadpool(func, request)

        await response(scope, receive, send)

    return app


# gán thêm start_time cho từng request để khi ghi log thì lấy start_time ra
routing.request_response = request_response


app = FastAPI(
    title=APPLICATION["project_name"],
    debug=APPLICATION["debug"],
    version=APPLICATION["version"],
    docs_url="/",
    default_response_class=ORJSONResponse,
    openapi_url="/openapi.json" if APPLICATION["debug"] else None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# run after start server
app.add_event_handler("startup", create_start_app_handler(app))
# run before shutdown server
app.add_event_handler("shutdown", create_stop_app_handler(app))

app.include_router(router=v1_router.router, prefix="/v1")

# handler exception
@app.exception_handler(RequestValidationError)
async def request_validation_except_custom(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    if exc.errors():
        for temp in exc.errors():
            errors.append(
                {
                    "loc": " -> ".join([str(err) for err in temp["loc"]]) if len(temp["loc"]) != 0 else None,
                    "msg": VALIDATE_ERROR,
                    "detail": f"{temp['msg']}",
                }
            )

    response_body = jsonable_encoder({"data": None, "errors": errors})

    return JSONResponse(
        content=response_body,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(HTTPException)
async def http_except_custom(request: Request, exc: HTTPException) -> JSONResponse:
    errors = [
        {
            "loc": None,
            "msg": None,
            "detail": f"{exc.detail}",
        }
    ]

    response_body = {"data": None, "errors": errors}

    return JSONResponse(
        content=response_body,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


utils.HTTP_422_UNPROCESSABLE_ENTITY = status.HTTP_400_BAD_REQUEST
