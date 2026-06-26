from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import ActivityType, VisitStatus
from app.models import Visit


def _valid_body(customer_id: int) -> dict[str, object]:
    return {
        "customer_id": customer_id,
        "activity_type": "visit",
        "status": "done",
        "visited_at": "2026-06-01T09:00:00Z",
        "memo": "訪問メモ",
    }


def _create_visit_row(
    db_session: Session, customer_id: int, **overrides: object
) -> Visit:
    values: dict[str, object] = {
        "customer_id": customer_id,
        "user_id": 1,
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


# --- POST ---


def test_create_visit_returns_201(client: TestClient, customer_factory):
    customer = customer_factory()
    res = client.post("/api/visits", json=_valid_body(customer.id))
    assert res.status_code == 201
    body = res.json()
    assert body["customer_id"] == customer.id
    assert body["user_id"] == 1  # ボディで受けず現在ユーザー
    assert body["visited_at"] == "2026-06-01T09:00:00Z"
    assert body["memo"] == "訪問メモ"
    assert body["created_at"] == body["updated_at"]


def test_create_visit_ignores_user_id_in_body(client: TestClient, customer_factory):
    customer = customer_factory()
    res = client.post(
        "/api/visits", json={**_valid_body(customer.id), "user_id": 3}
    )
    assert res.status_code == 201
    assert res.json()["user_id"] == 1


def test_create_visit_unknown_customer_is_422(client: TestClient, base_users):
    res = client.post("/api/visits", json=_valid_body(999))
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail[0]["loc"] == ["body", "customer_id"]
    assert "input" not in res.text


def test_create_visit_naive_datetime_is_422(client: TestClient, customer_factory):
    customer = customer_factory()
    res = client.post(
        "/api/visits",
        json={**_valid_body(customer.id), "visited_at": "2026-06-01T09:00:00"},
    )
    assert res.status_code == 422


def test_create_visit_memo_length_boundary(client: TestClient, customer_factory):
    customer = customer_factory()
    ok = client.post(
        "/api/visits", json={**_valid_body(customer.id), "memo": "あ" * 2000}
    )
    assert ok.status_code == 201
    ng = client.post(
        "/api/visits", json={**_valid_body(customer.id), "memo": "あ" * 2001}
    )
    assert ng.status_code == 422


def test_create_visit_offset_datetime_is_normalized_to_utc(
    client: TestClient, customer_factory
):
    customer = customer_factory()
    res = client.post(
        "/api/visits",
        json={**_valid_body(customer.id), "visited_at": "2026-06-01T18:00:00+09:00"},
    )
    assert res.status_code == 201
    # +09:00 は UTC に正規化して格納・返却される
    assert res.json()["visited_at"] == "2026-06-01T09:00:00Z"


# --- GET / PATCH / DELETE ---


def test_get_visit_detail_includes_memo(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    visit = _create_visit_row(db_session, customer.id, memo="詳細メモ")
    res = client.get(f"/api/visits/{visit.id}")
    assert res.status_code == 200
    assert res.json()["memo"] == "詳細メモ"


def test_get_visit_404(client: TestClient, base_users):
    assert client.get("/api/visits/999").status_code == 404


def test_patch_visit_updates_allowed_fields(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    visit = _create_visit_row(db_session, customer.id, status=VisitStatus.planned)
    before = client.get(f"/api/visits/{visit.id}").json()

    res = client.patch(
        f"/api/visits/{visit.id}",
        json={"status": "done", "memo": "実施済みに更新"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "done"
    assert body["memo"] == "実施済みに更新"
    assert body["updated_at"] > before["updated_at"]


def test_patch_visit_ignores_customer_and_user_change(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="元の顧客")
    other = customer_factory(name="別の顧客")
    visit = _create_visit_row(db_session, customer.id)

    res = client.patch(
        f"/api/visits/{visit.id}",
        json={"customer_id": other.id, "user_id": 3},
    )
    assert res.status_code == 200
    # 記録者・対象顧客の付け替えはしない
    assert res.json()["customer_id"] == customer.id
    assert res.json()["user_id"] == 1


def test_patch_visit_noop_keeps_updated_at(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    visit = _create_visit_row(db_session, customer.id)
    before = client.get(f"/api/visits/{visit.id}").json()

    res = client.patch(f"/api/visits/{visit.id}", json={})
    assert res.status_code == 200
    assert res.json()["updated_at"] == before["updated_at"]


def test_patch_visit_null_for_required_field_is_422(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    visit = _create_visit_row(db_session, customer.id)
    for field in ("activity_type", "status", "visited_at"):
        res = client.patch(f"/api/visits/{visit.id}", json={field: None})
        assert res.status_code == 422


def test_delete_visit_returns_204(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    visit = _create_visit_row(db_session, customer.id)
    assert client.delete(f"/api/visits/{visit.id}").status_code == 204
    assert client.get(f"/api/visits/{visit.id}").status_code == 404


# --- GET /api/customers/{id}/visits ---


def test_customer_visits_sorted_desc_without_memo(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="履歴顧客")
    _create_visit_row(
        db_session, customer.id, visited_at=datetime(2026, 5, 1, 9, 0, 0)
    )
    _create_visit_row(
        db_session, customer.id, visited_at=datetime(2026, 6, 1, 9, 0, 0), user_id=2
    )

    res = client.get(f"/api/customers/{customer.id}/visits")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    # visited_at 降順固定
    assert [item["visited_at"] for item in body["items"]] == [
        "2026-06-01T09:00:00Z",
        "2026-05-01T09:00:00Z",
    ]
    first = body["items"][0]
    # join 済み表示名を含み、memo は含めない
    assert first["customer_name"] == "履歴顧客"
    assert first["user_name"] == "営業ユーザーA"
    assert first["owner_id"] == customer.owner_id
    assert "memo" not in first


def test_customer_visits_pagination(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    for day in range(1, 13):
        _create_visit_row(
            db_session, customer.id, visited_at=datetime(2026, 5, day, 9, 0, 0)
        )

    res = client.get(
        f"/api/customers/{customer.id}/visits",
        params={"page": 2, "page_size": 10},
    )
    body = res.json()
    assert body["total"] == 12
    assert len(body["items"]) == 2
    assert body["page"] == 2


def test_customer_visits_unknown_customer_is_404(client: TestClient, base_users):
    assert client.get("/api/customers/999/visits").status_code == 404


# --- GET /api/visits（顧客横断一覧） ---


def test_visits_list_sorted_desc_with_filters(
    client: TestClient, db_session: Session, customer_factory
):
    customer_a = customer_factory(name="顧客A")
    customer_b = customer_factory(name="顧客B")
    _create_visit_row(
        db_session, customer_a.id, visited_at=datetime(2026, 5, 1, 9, 0, 0), user_id=2
    )
    _create_visit_row(
        db_session,
        customer_b.id,
        visited_at=datetime(2026, 5, 2, 9, 0, 0),
        status=VisitStatus.planned,
    )
    _create_visit_row(
        db_session, customer_b.id, visited_at=datetime(2026, 5, 3, 9, 0, 0), user_id=3
    )

    res_all = client.get("/api/visits")
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 3
    assert [item["visited_at"] for item in res_all.json()["items"]] == [
        "2026-05-03T09:00:00Z",
        "2026-05-02T09:00:00Z",
        "2026-05-01T09:00:00Z",
    ]

    res_status = client.get("/api/visits", params={"status": "planned"})
    assert res_status.json()["total"] == 1

    res_user = client.get("/api/visits", params={"user_id": 3})
    assert res_user.json()["total"] == 1

    res_customer = client.get("/api/visits", params={"customer_id": customer_b.id})
    assert res_customer.json()["total"] == 2

    res_range = client.get(
        "/api/visits",
        params={"from": "2026-05-02T00:00:00Z", "to": "2026-05-02T23:59:59Z"},
    )
    assert res_range.json()["total"] == 1


def test_visits_list_naive_range_is_422(client: TestClient, base_users):
    res = client.get("/api/visits", params={"from": "2026-05-02T00:00:00"})
    assert res.status_code == 422


def test_visits_list_from_after_to_is_422(client: TestClient, base_users):
    res = client.get(
        "/api/visits",
        params={"from": "2026-05-03T00:00:00Z", "to": "2026-05-01T00:00:00Z"},
    )
    assert res.status_code == 422
    assert "input" not in res.text


def test_visits_list_unrecorded_overrides_status_and_range(
    client: TestClient, db_session: Session, customer_factory
):
    from datetime import timedelta

    from app.timeutil import utcnow_naive

    customer = customer_factory()
    other = customer_factory(name="別顧客")
    now = utcnow_naive()
    overdue = _create_visit_row(
        db_session,
        customer.id,
        status=VisitStatus.planned,
        visited_at=now - timedelta(days=2),
    )
    _create_visit_row(
        db_session,
        other.id,
        status=VisitStatus.planned,
        visited_at=now - timedelta(days=3),
    )
    # 未来の planned と完了済みは入力漏れに含めない
    _create_visit_row(
        db_session, customer.id, status=VisitStatus.planned, visited_at=now + timedelta(days=1)
    )
    _create_visit_row(
        db_session, customer.id, status=VisitStatus.done, visited_at=now - timedelta(days=1)
    )

    # unrecorded=true 時は status / from / to を無視する
    res = client.get(
        "/api/visits",
        params={
            "unrecorded": "true",
            "status": "done",
            "from": "2030-01-01T00:00:00Z",
            "to": "2030-12-31T00:00:00Z",
        },
    )
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # customer_id は unrecorded と AND 併用
    res_and = client.get(
        "/api/visits", params={"unrecorded": "true", "customer_id": customer.id}
    )
    assert res_and.json()["total"] == 1
    assert res_and.json()["items"][0]["id"] == overdue.id
