"""AUTH_MODE=clerk の検証ロジック。

ローカル生成の RSA 鍵で署名した JWT と JWKS クライアントの差し替えにより、
外部サービスなしで検証経路を実テストする。
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.auth as auth_module
from app.models import User

# テスト専用の鍵ペア（モジュールで1回だけ生成）
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

AUTHORIZED_PARTY = "http://localhost:5173"
AUDIENCE = "saleslog-api"
KNOWN_SUB = "user_e2e_manager"


class _FakeSigningKey:
    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self.key = key.public_key()


class _FakeJWKSClient:
    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, _token: str) -> _FakeSigningKey:
        return _FakeSigningKey(self._key)


class _BrokenJWKSClient:
    def get_signing_key_from_jwt(self, _token: str) -> _FakeSigningKey:
        raise ConnectionError("jwks unreachable")


def make_token(
    *,
    key: rsa.RSAPrivateKey = _PRIVATE_KEY,
    sub: str = KNOWN_SUB,
    azp: str | None = AUTHORIZED_PARTY,
    iss: str | None = None,
    aud: str | list[str] | None = None,
    expires_in: int = 300,
    not_before_in: int = -10,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": sub,
        "exp": now + timedelta(seconds=expires_in),
        "nbf": now + timedelta(seconds=not_before_in),
        "iat": now,
    }
    if azp is not None:
        payload["azp"] = azp
    if iss is not None:
        payload["iss"] = iss
    if aud is not None:
        payload["aud"] = aud
    return jwt.encode(payload, key, algorithm="RS256")


@pytest.fixture()
def clerk_mode(
    monkeypatch: pytest.MonkeyPatch, db_session: Session, base_users: list[User]
):
    monkeypatch.setenv("AUTH_MODE", "clerk")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", AUTHORIZED_PARTY)
    monkeypatch.setenv("CLERK_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.setattr(
        auth_module, "_get_jwks_client", lambda: _FakeJWKSClient(_PRIVATE_KEY)
    )
    # manager(id=1) に既知の sub を紐付ける
    user = db_session.get(User, 1)
    assert user is not None
    user.external_id = KNOWN_SUB
    db_session.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_resolves_user(client: TestClient, clerk_mode):
    res = client.get("/api/users", headers=_auth_header(make_token(aud=AUDIENCE)))
    assert res.status_code == 200


def test_missing_header_is_401(client: TestClient, clerk_mode):
    res = client.get("/api/users")
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}


def test_expired_token_is_401(client: TestClient, clerk_mode):
    res = client.get(
        "/api/users", headers=_auth_header(make_token(expires_in=-60))
    )
    assert res.status_code == 401


def test_not_yet_valid_token_is_401(client: TestClient, clerk_mode):
    res = client.get(
        "/api/users", headers=_auth_header(make_token(not_before_in=120))
    )
    assert res.status_code == 401


def test_wrong_signature_is_401(client: TestClient, clerk_mode):
    res = client.get(
        "/api/users", headers=_auth_header(make_token(key=_OTHER_KEY))
    )
    assert res.status_code == 401


def test_missing_azp_is_401(client: TestClient, clerk_mode):
    # azp は存在自体を必須にする。
    res = client.get("/api/users", headers=_auth_header(make_token(azp=None)))
    assert res.status_code == 401


def test_wrong_azp_is_401(client: TestClient, clerk_mode):
    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(azp="https://evil.example.com")),
    )
    assert res.status_code == 401


def test_clerk_issuer_が一致したら認証できる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.test")

    res = client.get(
        "/api/users",
        headers=_auth_header(
            make_token(iss="https://clerk.example.test", aud=AUDIENCE)
        ),
    )

    assert res.status_code == 200


def test_clerk_issuer_が違ったら401になる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.test")

    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(iss="https://other.example.test")),
    )

    assert res.status_code == 401


def test_clerk_issuer_必須設定でclaimがなければ401になる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.test")

    res = client.get("/api/users", headers=_auth_header(make_token()))

    assert res.status_code == 401


def test_clerk_audience_が一致したら認証できる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_AUDIENCE", "saleslog-api")

    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(aud="saleslog-api")),
    )

    assert res.status_code == 200


def test_clerk_audience_候補のどれかに一致したら認証できる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_AUDIENCE", "saleslog-api, saleslog-web")

    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(aud="saleslog-web")),
    )

    assert res.status_code == 200


def test_clerk_audience_未設定なら401になる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)

    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(aud="custom-template")),
    )

    assert res.status_code == 401


def test_clerk_audience_が違ったら401になる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_AUDIENCE", "saleslog-api")

    res = client.get(
        "/api/users",
        headers=_auth_header(make_token(aud="other-api")),
    )

    assert res.status_code == 401


def test_clerk_audience_必須設定でclaimがなければ401になる(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CLERK_AUDIENCE", "saleslog-api")

    res = client.get("/api/users", headers=_auth_header(make_token()))

    assert res.status_code == 401


def test_unknown_sub_is_401(client: TestClient, clerk_mode):
    # 未登録 sub は 401（JIT 作成なし）。
    res = client.get(
        "/api/users", headers=_auth_header(make_token(sub="user_unknown", aud=AUDIENCE))
    )
    assert res.status_code == 401


def test_jwks_failure_is_401(
    client: TestClient, clerk_mode, monkeypatch: pytest.MonkeyPatch
):
    # JWKS 取得失敗は fail-closed。
    monkeypatch.setattr(auth_module, "_get_jwks_client", lambda: _BrokenJWKSClient())
    res = client.get("/api/users", headers=_auth_header(make_token()))
    assert res.status_code == 401


def test_error_response_does_not_leak_reason(client: TestClient, clerk_mode):
    res = client.get(
        "/api/users", headers=_auth_header(make_token(azp="https://evil.example.com"))
    )
    assert res.json() == {"detail": "Unauthorized"}
    assert "azp" not in res.text


def test_missing_auth_mode_requires_authorization(
    client: TestClient, base_users, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    res = client.get("/api/users")
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}


def test_fixed_mode_requires_explicit_auth_mode(
    client: TestClient, base_users, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AUTH_MODE", "fixed")
    res = client.get("/api/users")
    assert res.status_code == 200


def test_fixed_mode_rejects_non_local_request_host(
    client: TestClient, base_users, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AUTH_MODE", "fixed")
    res = client.get("/api/users", headers={"host": "example.com"})
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}
