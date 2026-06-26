import logging
import os
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthError, verify_token
from app.db import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)

# AUTH_MODE=fixed: 固定シードユーザーでローカル実行できる。
# 未設定時は clerk 扱いにして、固定ユーザーへの暗黙フォールバックを避ける。
FIXED_USER_ID = 1
AUTH_MODE_CLERK = "clerk"
AUTH_MODE_FIXED = "fixed"
FIXED_AUTH_LOCAL_CLIENTS = {"127.0.0.1", "::1", "testclient"}
FIXED_AUTH_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _unauthorized() -> HTTPException:
    # 失敗理由の詳細・token 内容は返さない。
    return HTTPException(status_code=401, detail="Unauthorized")


def _fixed_auth_request_is_local(request: Request) -> bool:
    client_host = request.client.host if request.client is not None else ""
    request_host = request.url.hostname or ""
    return (
        client_host.lower() in FIXED_AUTH_LOCAL_CLIENTS
        and request_host.lower() in FIXED_AUTH_LOCAL_HOSTS
    )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    auth_mode = os.environ.get("AUTH_MODE", AUTH_MODE_CLERK).strip().lower()
    if auth_mode == AUTH_MODE_FIXED:
        if not _fixed_auth_request_is_local(request):
            logger.warning("AUTH_MODE=fixed はローカルリクエストのみ許可します")
            raise _unauthorized()
        user = db.get(User, FIXED_USER_ID)
        if user is None:
            # seed 未投入のままの起動は構成ミスとして扱う
            raise HTTPException(status_code=500, detail="Internal Server Error")
        return user

    if auth_mode != AUTH_MODE_CLERK:
        logger.error("AUTH_MODE の値が不正です")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    if authorization is None or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.removeprefix("Bearer ")
    try:
        sub = verify_token(token)
    except AuthError as error:
        # サーバログにはエラー種別のみ記録する（token / payload は出さない。仕様）
        logger.warning("認証失敗: %s", error.reason)
        raise _unauthorized() from None

    # sub → users.external_id で解決。未登録は 401（JIT 作成なし。仕様）
    user = db.scalar(select(User).where(User.external_id == sub))
    if user is None:
        logger.warning("認証失敗: unknown sub")
        raise _unauthorized()
    return user
