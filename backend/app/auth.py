"""Clerk JWT の検証。

AUTH_MODE=clerk のときだけ使われる。検証失敗・構成不備・JWKS 取得失敗は
すべて呼び出し側で 401 に変換する（fail-closed）。
"""

import logging
import os

import jwt
from jwt import PyJWKClient
from jwt.types import Options

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


class AuthError(Exception):
    """401 に変換する内部例外。reason はサーバログ専用（レスポンスへ出さない）。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _get_jwks_client() -> PyJWKClient:
    # JWKS はプロセス内でキャッシュし、リクエスト毎に取得しない。
    global _jwks_client
    if _jwks_client is None:
        url = os.environ.get("CLERK_JWKS_URL", "")
        if url == "":
            raise AuthError("config: CLERK_JWKS_URL is not set")
        _jwks_client = PyJWKClient(url)
    return _jwks_client


def _authorized_parties() -> list[str]:
    raw = os.environ.get("CLERK_AUTHORIZED_PARTIES", "")
    return [party.strip() for party in raw.split(",") if party.strip() != ""]


def _clerk_issuer() -> str | None:
    value = os.environ.get("CLERK_ISSUER", "").strip()
    return value if value != "" else None


def _clerk_audience() -> str | list[str] | None:
    raw = os.environ.get("CLERK_AUDIENCE", "")
    values = [audience.strip() for audience in raw.split(",") if audience.strip() != ""]
    if len(values) == 0:
        raise AuthError("config: CLERK_AUDIENCE is not set")
    if len(values) == 1:
        return values[0]
    return values


def _required_claims(issuer: str | None, audience: str | list[str] | None) -> list[str]:
    claims = ["exp", "nbf", "sub", "azp"]
    if issuer is not None:
        claims.append("iss")
    if audience is not None:
        claims.append("aud")
    return claims


def verify_token(token: str) -> str:
    """token を検証して subject（Clerk のユーザー ID）を返す。

    検証内容: RS256 固定 / exp / nbf / sub / azp / aud の存在必須 /
    azp が許可 origin のいずれかと一致。issuer は設定時だけ検証する。
    """
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        issuer = _clerk_issuer()
        audience = _clerk_audience()
        options: Options = {"require": _required_claims(issuer, audience)}
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # azp は「存在時のみ照合」だと省いた token が素通りするため存在も必須にする
            options=options,
            issuer=issuer,
            audience=audience,
        )
    except AuthError:
        raise
    except jwt.PyJWTError as error:
        raise AuthError(f"jwt: {type(error).__name__}") from error
    except Exception as error:  # JWKS 取得失敗（ネットワーク等）も fail-closed
        raise AuthError(f"jwks: {type(error).__name__}") from error

    if payload["azp"] not in _authorized_parties():
        raise AuthError("azp: not in authorized parties")
    return str(payload["sub"])


def reset_jwks_client_cache() -> None:
    """テスト・設定変更時にキャッシュを破棄する。"""
    global _jwks_client
    _jwks_client = None
