"""role 別 access matrix のサーバ強制。

sales としての呼び出しは dependency_overrides で get_current_user を差し替える。
manager は fixed モードの既定ユーザー（id=1）。
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.enums import ActivityType, VisitStatus
from app.main import app
from app.models import User, Visit
from app.timeutil import utcnow_naive


@pytest.fixture()
def as_sales(db_session: Session, base_users: list[User]):
    sales = db_session.get(User, 2)
    assert sales is not None
    app.dependency_overrides[get_current_user] = lambda: sales
    yield sales
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def two_customers(db_session: Session, customer_factory):
    own = customer_factory(name="自分の顧客", owner_id=2)
    other = customer_factory(name="他担当の顧客", owner_id=3)
    return own, other


def _add_visit(db_session: Session, customer_id: int, user_id: int, **overrides):
    values = {
        "customer_id": customer_id,
        "user_id": user_id,
        "activity_type": ActivityType.visit,
        "status": VisitStatus.done,
        "visited_at": datetime(2026, 5, 1, 9, 0, 0),
    }
    values.update(overrides)
    visit = Visit(**values)
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


# --- customers（ / ） ---


def test_sales_list_is_scoped_to_own_customers(
    client: TestClient, as_sales, two_customers
):
    # クエリで他人の owner_id を指定しても自分のものしか返らない
    res = client.get("/api/customers", params={"owner_id": 3})
    assert res.status_code == 200
    names = [item["name"] for item in res.json()["items"]]
    assert names == ["自分の顧客"]


def test_sales_other_customer_detail_update_delete_are_404(
    client: TestClient, as_sales, two_customers
):
    _, other = two_customers
    assert client.get(f"/api/customers/{other.id}").status_code == 404
    assert (
        client.patch(f"/api/customers/{other.id}", json={"name": "x"}).status_code
        == 404
    )
    assert client.delete(f"/api/customers/{other.id}").status_code == 404
    assert client.get(f"/api/customers/{other.id}/visits").status_code == 404


def test_sales_can_edit_own_customer(client: TestClient, as_sales, two_customers):
    own, _ = two_customers
    res = client.patch(f"/api/customers/{own.id}", json={"status": "won"})
    assert res.status_code == 200


def test_sales_patch_with_owner_id_is_404(
    client: TestClient, as_sales, two_customers
):
    own, _ = two_customers
    # 担当者変更は manager のみ（owner_id を含む PATCH は 404 で明示拒否）
    res = client.patch(f"/api/customers/{own.id}", json={"owner_id": 2})
    assert res.status_code == 404


def test_sales_post_with_other_owner_is_422(client: TestClient, as_sales):
    res = client.post(
        "/api/customers",
        json={"name": "新規", "area": "tokyo", "status": "prospect", "owner_id": 3},
    )
    assert res.status_code == 422
    # 省略時は自分が owner になる
    res_ok = client.post(
        "/api/customers", json={"name": "新規2", "area": "tokyo", "status": "prospect"}
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["owner_id"] == 2


# --- visits（ / ） ---


def test_sales_visit_list_is_forced_to_own(
    client: TestClient, db_session: Session, as_sales, two_customers
):
    own, other = two_customers
    mine = _add_visit(db_session, own.id, user_id=2)
    _add_visit(db_session, other.id, user_id=3)

    # user_id=3 を指定しても自分の記録のみ（サーバ強制）
    res = client.get("/api/visits", params={"user_id": 3})
    assert res.status_code == 200
    assert [item["id"] for item in res.json()["items"]] == [mine.id]


def test_sales_post_visit_to_other_customer_is_404(
    client: TestClient, as_sales, two_customers
):
    _, other = two_customers
    res = client.post(
        "/api/visits",
        json={
            "customer_id": other.id,
            "activity_type": "visit",
            "status": "done",
            "visited_at": "2026-06-01T09:00:00Z",
        },
    )
    assert res.status_code == 404


def test_sales_other_users_visit_detail_is_404(
    client: TestClient, db_session: Session, as_sales, two_customers
):
    _, other = two_customers
    others_visit = _add_visit(db_session, other.id, user_id=3)
    assert client.get(f"/api/visits/{others_visit.id}").status_code == 404
    assert (
        client.patch(
            f"/api/visits/{others_visit.id}", json={"status": "done"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/visits/{others_visit.id}").status_code == 404


def test_sales_customer_visits_history_is_scoped_to_own(
    client: TestClient, db_session: Session, as_sales, two_customers
):
    # 自分担当顧客の履歴でも他人の記録は出さない・total にも含めない（）。
    # 履歴に出るのに個別 GET が 404 になる不整合の再発防止
    own, _ = two_customers
    mine = _add_visit(db_session, own.id, user_id=2)
    _add_visit(db_session, own.id, user_id=3)

    res = client.get(f"/api/customers/{own.id}/visits")
    assert res.status_code == 200
    body = res.json()
    assert [item["id"] for item in body["items"]] == [mine.id]
    assert body["total"] == 1


def test_sales_customer_list_last_visited_is_scoped_to_own(
    client: TestClient, db_session: Session, as_sales, two_customers, customer_factory
):
    # 派生値 last_visited_at にも他人の訪問日時を含めない（履歴 API と同じ強制）
    own, _ = two_customers
    own2 = customer_factory(name="自分の顧客2", owner_id=2)
    _add_visit(db_session, own.id, user_id=2, visited_at=datetime(2026, 5, 1, 9, 0, 0))
    _add_visit(db_session, own.id, user_id=3, visited_at=datetime(2026, 6, 1, 9, 0, 0))
    # own2 には他人の記録だけがある
    _add_visit(db_session, own2.id, user_id=3, visited_at=datetime(2026, 6, 2, 9, 0, 0))

    res = client.get("/api/customers")
    assert res.status_code == 200
    items = {item["name"]: item for item in res.json()["items"]}
    # 他人の 6/1 ではなく自分の 5/1
    assert items["自分の顧客"]["last_visited_at"] == "2026-05-01T09:00:00Z"
    # 自分の記録が無い顧客は null（他人の最新日時を見せない）
    assert items["自分の顧客2"]["last_visited_at"] is None


def test_sales_unrecorded_list_is_scoped_to_own(
    client: TestClient, db_session: Session, as_sales, two_customers
):
    # 入力漏れ（unrecorded=true）の分岐でも自分の記録のみ（スコープが外れない検査）
    own, other = two_customers
    past = utcnow_naive() - timedelta(days=3)
    mine = _add_visit(
        db_session, own.id, user_id=2, status=VisitStatus.planned, visited_at=past
    )
    _add_visit(
        db_session, other.id, user_id=3, status=VisitStatus.planned, visited_at=past
    )

    res = client.get("/api/visits", params={"unrecorded": "true"})
    assert res.status_code == 200
    body = res.json()
    assert [item["id"] for item in body["items"]] == [mine.id]
    assert body["total"] == 1


# --- dashboard（） ---


def test_sales_dashboard_is_scoped(
    client: TestClient, db_session: Session, as_sales, two_customers
):
    own, other = two_customers
    now = utcnow_naive()
    _add_visit(db_session, own.id, user_id=2, visited_at=now - timedelta(days=1))
    _add_visit(db_session, other.id, user_id=3, visited_at=now - timedelta(days=1))
    # 自分の入力漏れ1件・他人の入力漏れ1件
    _add_visit(
        db_session,
        own.id,
        user_id=2,
        status=VisitStatus.planned,
        visited_at=now - timedelta(days=2),
    )
    _add_visit(
        db_session,
        other.id,
        user_id=3,
        status=VisitStatus.planned,
        visited_at=now - timedelta(days=2),
    )

    body = client.get("/api/dashboard/summary").json()
    assert body["total_customers"] == 1  # 自分担当のみ
    assert body["visits_this_month"] == 2  # 自分の記録のみ（done+planned）
    assert body["unrecorded_count"] == 1
    # by_owner は自分のみに縮退（仕様）
    assert [entry["owner_id"] for entry in body["by_owner"]] == [2]


# --- manager ---


def test_manager_keeps_full_access(
    client: TestClient, db_session: Session, two_customers
):
    own, other = two_customers
    _add_visit(db_session, other.id, user_id=3)

    assert client.get(f"/api/customers/{other.id}").status_code == 200
    # 履歴は manager には全員分（。 の sales 絞り込みが波及しないこと）
    assert client.get(f"/api/customers/{other.id}/visits").json()["total"] == 1
    res_list = client.get("/api/customers")
    assert res_list.json()["total"] == 2
    res_patch = client.patch(
        f"/api/customers/{other.id}", json={"owner_id": 2}
    )
    assert res_patch.status_code == 200
    body = client.get("/api/dashboard/summary").json()
    assert body["total_customers"] == 2
