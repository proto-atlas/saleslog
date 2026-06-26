import os
from collections.abc import Awaitable, Callable

import truststore
from fastapi import FastAPI, Request, Response

# OS の証明書ストアを SSL 検証に使う（JWKS 取得が TLS 検査型 AV 環境で失敗するため。
# certifi 同梱のままだとローカル CA を信頼できない）
truststore.inject_into_ssl()
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import agent_runs, customers, dashboard, users, visits

app = FastAPI(title="Saleslog API")


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 422 の public response から input / url を除去する（loc / msg / type のみ返す。仕様）
    detail = [
        {key: value for key, value in error.items() if key in ("loc", "msg", "type")}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.middleware("http")
async def demo_read_only_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # DEMO_READ_ONLY=true のとき全書き込みメソッドを 405 にする（既定 off。仕様）
    if request.method in ("POST", "PATCH", "DELETE") and (
        os.environ.get("DEMO_READ_ONLY") == "true"
    ):
        return JSONResponse(status_code=405, content={"detail": "Method Not Allowed"})
    return await call_next(request)


app.include_router(users.router)
app.include_router(users.me_router)
app.include_router(agent_runs.router)
app.include_router(customers.router)
app.include_router(visits.router)
app.include_router(dashboard.router)
