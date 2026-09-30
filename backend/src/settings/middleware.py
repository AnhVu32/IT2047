import time

from fastapi import Request


async def add_process_time_header(response, start_time):
    process_time = time.time() - start_time
    response.headers["Server-Execute-Time"] = str(process_time)
    return response


async def middleware_setting(request: Request, call_next):
    start_time = time.time()
    # check auth
    response = await call_next(request)
    # add header time
    response = await add_process_time_header(response=response, start_time=start_time)
    return response
