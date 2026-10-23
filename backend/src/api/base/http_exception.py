from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse


async def http_except_custom(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap HTTPException in the API envelope while keeping its real status code."""
    errors = [
        {
            "loc": None,
            "msg": None,
            "detail": f"{exc.detail}",
        }
    ]

    return JSONResponse(
        content={"data": None, "errors": errors},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )
