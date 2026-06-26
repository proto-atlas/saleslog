import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.enums import UserRole
from app.models import User
from app.routers.users import _demote_manager_if_allowed

USERS_API = "/api/users"


def user_api_path(user_id: int) -> str:
    return f"{USERS_API}/{user_id}"


def test_users_are_sorted_by_id(client: TestClient, db_session: Session):
    # 挿入順に依らず id 昇順固定
    db_session.add_all(
        [
            User(id=3, name="営業ユーザーB", role=UserRole.sales),
            User(id=1, name="管理者ユーザー", role=UserRole.manager),
            User(id=2, name="営業ユーザーA", role=UserRole.sales),
        ]
    )
    db_session.commit()

    res = client.get(USERS_API)
    assert res.status_code == 200
    assert [item["id"] for item in res.json()["items"]] == [1, 2, 3]


def test_users_role_filter(client: TestClient, base_users: list[User]):
    res = client.get(USERS_API, params={"role": "sales"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert [item["id"] for item in items] == [2, 3]
    assert all(item["role"] == "sales" for item in items)


def test_users_invalid_role_is_422(client: TestClient, base_users: list[User]):
    res = client.get(USERS_API, params={"role": "boss"})
    assert res.status_code == 422


def test_me_returns_current_user(client: TestClient, base_users: list[User]):
    # fixed モードでは固定ユーザー（id=1 manager）が返る
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == 1
    assert body["role"] == "manager"


# --- ユーザー管理 ---


def test_manager_can_create_and_update_user(
    client: TestClient, base_users: list[User]
):
    res = client.post(USERS_API, json={"name": "追加ユーザーA", "role": "sales"})
    assert res.status_code == 201
    new_id = res.json()["id"]

    res_patch = client.patch(
        user_api_path(new_id), json={"name": "追加ユーザーB", "role": "manager"}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["name"] == "追加ユーザーB"
    assert res_patch.json()["role"] == "manager"


def test_manager_can_link_and_unlink_external_id(
    client: TestClient, base_users: list[User]
):
    res = client.patch(user_api_path(2), json={"external_id": "user_abc123"})
    assert res.status_code == 200
    assert res.json()["linked"] is True
    res_unlink = client.patch(user_api_path(2), json={"external_id": None})
    assert res_unlink.status_code == 200
    assert res_unlink.json()["linked"] is False


def test_self_external_id_change_is_422(client: TestClient, base_users: list[User]):
    # 自分自身の紐付け変更・解除は拒否（clerk モードでの自己締め出し防止）
    assert client.patch(user_api_path(1), json={"external_id": None}).status_code == 422
    assert (
        client.patch(user_api_path(1), json={"external_id": "user_self"}).status_code
        == 422
    )


def test_external_id_empty_string_is_422(client: TestClient, base_users: list[User]):
    # 空文字は紐付け値として受けない（min_length=1。解除は null で行う）
    res = client.patch(user_api_path(2), json={"external_id": ""})
    assert res.status_code == 422


def test_external_id_whitespace_is_422(client: TestClient, base_users: list[User]):
    res = client.patch(user_api_path(2), json={"external_id": "   "})
    assert res.status_code == 422


def test_users_lookup_hides_linked_for_sales(
    client: TestClient, db_session: Session, base_users: list[User]
):
    from app.deps import get_current_user
    from app.main import app

    # manager には紐付け状況（bool）が見える
    res_manager = client.get(USERS_API)
    assert all(item["linked"] is not None for item in res_manager.json()["items"])

    # sales の担当者 lookup には管理用属性を返さない
    sales = db_session.get(User, 2)
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        res_sales = client.get(USERS_API)
        assert all(item["linked"] is None for item in res_sales.json()["items"])
        assert all(item["role"] is None for item in res_sales.json()["items"])
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_sales_role_filter_is_404(
    client: TestClient, db_session: Session, base_users: list[User]
):
    from app.deps import get_current_user
    from app.main import app

    sales = db_session.get(User, 2)
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        res = client.get(USERS_API, params={"role": "sales"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 404


def test_duplicate_external_id_is_422(client: TestClient, base_users: list[User]):
    assert (
        client.patch(user_api_path(2), json={"external_id": "user_dup"}).status_code
        == 200
    )
    res = client.patch(user_api_path(3), json={"external_id": "user_dup"})
    assert res.status_code == 422


def test_external_id_is_trimmed_before_duplicate_check(
    client: TestClient, base_users: list[User]
):
    assert (
        client.patch(user_api_path(2), json={"external_id": "user_trim"}).status_code
        == 200
    )
    res = client.patch(user_api_path(3), json={"external_id": "  user_trim  "})
    assert res.status_code == 422


def test_self_role_change_is_422(client: TestClient, base_users: list[User]):
    # 固定ユーザー（id=1）自身の役割変更は拒否
    res = client.patch(user_api_path(1), json={"role": "sales"})
    assert res.status_code == 422


def test_demotion_allowed_while_other_manager_remains(
    client: TestClient, base_users: list[User]
):
    # manager が複数いる間は他の manager を降格できる（ の正方向）。
    # 「最後の 1 人の降格拒否」の分岐は、操作者自身が manager である限り
    # 降格対象の manager が常に 2 人目以降になるため、この API 経路では発生しない
    # （自分自身は test_self_role_change_is_422 が先に拒否する）。実装の
    # manager_count チェックは将来の経路追加に備えた防御として残している
    res = client.post(USERS_API, json={"name": "二人目", "role": "manager"})
    new_id = res.json()["id"]
    assert (
        client.patch(user_api_path(new_id), json={"role": "sales"}).status_code
        == 200
    )


def test_manager_demotion_rechecks_manager_count_in_update(
    db_session: Session, base_users: list[User]
):
    db_session.add(User(id=4, name="二人目", role=UserRole.manager))
    db_session.commit()

    first_session = SessionLocal()
    second_session = SessionLocal()
    try:
        first_manager = first_session.get(User, 4)
        stale_last_manager = second_session.get(User, 1)
        assert first_manager is not None
        assert stale_last_manager is not None

        _demote_manager_if_allowed(first_session, first_manager)
        first_session.commit()

        with pytest.raises(HTTPException) as error:
            _demote_manager_if_allowed(second_session, stale_last_manager)
        assert error.value.status_code == 422
    finally:
        first_session.close()
        second_session.close()

    manager_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.manager)
    )
    assert manager_count == 1


def test_sales_cannot_manage_users(
    client: TestClient, db_session: Session, base_users: list[User]
):
    from app.deps import get_current_user
    from app.main import app

    sales = db_session.get(User, 2)
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        res_post = client.post(
            USERS_API, json={"name": "不可", "role": "sales"}
        )
        assert res_post.status_code == 404
        res_patch = client.patch(user_api_path(3), json={"name": "不可"})
        assert res_patch.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
