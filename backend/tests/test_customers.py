from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import ActivityType, CustomerArea, CustomerStatus, VisitStatus
from app.deps import get_current_user
from app.main import app
from app.models import Customer, User, Visit

VALID_BODY = {"name": "新規顧客", "area": "tokyo", "status": "prospect"}


def _assert_public_422(res) -> None:
    # 422 の public response に input / url を含めない
    assert res.status_code == 422
    for item in res.json()["detail"]:
        assert set(item.keys()) <= {"loc", "msg", "type"}


# --- POST ---


def test_create_customer_returns_201_and_persists(
    client: TestClient, base_users: list[User]
):
    res = client.post("/api/customers", json={**VALID_BODY, "owner_id": 2})
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "新規顧客"
    assert body["owner_id"] == 2
    assert body["created_at"] == body["updated_at"]
    assert body["created_at"].endswith("Z")

    res_get = client.get(f"/api/customers/{body['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "新規顧客"


def test_create_customer_owner_defaults_to_current_user(
    client: TestClient, base_users: list[User]
):
    # owner_id 省略時は現在ユーザーの id を採用する（テストでは fixed モードの id=1）。
    res = client.post("/api/customers", json=VALID_BODY)
    assert res.status_code == 201
    assert res.json()["owner_id"] == 1


def test_create_customer_unknown_owner_is_422(
    client: TestClient, base_users: list[User]
):
    res = client.post("/api/customers", json={**VALID_BODY, "owner_id": 999})
    _assert_public_422(res)
    assert res.json()["detail"][0]["loc"] == ["body", "owner_id"]


def test_create_customer_blank_name_is_422_without_input_echo(
    client: TestClient, base_users: list[User]
):
    res = client.post("/api/customers", json={**VALID_BODY, "name": "   "})
    _assert_public_422(res)
    # 送信した生値がレスポンスに反射しないこと
    assert "input" not in res.text


def test_create_customer_name_length_boundary(
    client: TestClient, base_users: list[User]
):
    ok = client.post("/api/customers", json={**VALID_BODY, "name": "あ" * 80})
    assert ok.status_code == 201
    ng = client.post("/api/customers", json={**VALID_BODY, "name": "あ" * 81})
    _assert_public_422(ng)


def test_create_customer_invalid_enum_is_422(
    client: TestClient, base_users: list[User]
):
    res = client.post("/api/customers", json={**VALID_BODY, "area": "osaka"})
    _assert_public_422(res)


def test_create_customer_ignores_readonly_fields(
    client: TestClient, base_users: list[User]
):
    # id / created_at / updated_at はリクエストで送られても無視する
    res = client.post(
        "/api/customers",
        json={**VALID_BODY, "id": 999, "created_at": "2000-01-01T00:00:00Z"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["id"] != 999
    assert not body["created_at"].startswith("2000-")


# --- GET 一覧 ---


def test_list_pagination_total_and_out_of_range_page(
    client: TestClient, customer_factory
):
    for i in range(25):
        customer_factory(name=f"顧客{i:02d}")

    res = client.get("/api/customers", params={"page": 2, "page_size": 10})
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 10
    assert body["total"] == 25
    assert body["page"] == 2
    assert body["page_size"] == 10

    # 総ページ数を超える page は 200 + 空 items
    res_over = client.get("/api/customers", params={"page": 99, "page_size": 10})
    assert res_over.status_code == 200
    assert res_over.json()["items"] == []
    assert res_over.json()["total"] == 25
    assert res_over.json()["page"] == 99


def test_list_page_and_page_size_validation(client: TestClient, base_users):
    for params in (
        {"page": 0},
        {"page": "abc"},
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": "abc"},
    ):
        res = client.get("/api/customers", params=params)
        _assert_public_422(res)


def test_search_is_case_insensitive(client: TestClient, customer_factory):
    customer_factory(name="Sky Net Works 株式会社")
    customer_factory(name="アオバ製作所")

    for term in ("sky", "SKY", "Sky"):
        res = client.get("/api/customers", params={"search": term})
        assert res.status_code == 200
        assert res.json()["total"] == 1
        assert res.json()["items"][0]["name"] == "Sky Net Works 株式会社"


def test_search_metacharacters_are_literal(client: TestClient, customer_factory):
    # % / _ / \ を literal として検索できること（autoescape。仕様）
    customer_factory(name="100%サポート株式会社")
    customer_factory(name="A_Bテクノロジーズ")
    customer_factory(name="C\\Dシステムズ")
    customer_factory(name="普通の商事")

    res_percent = client.get("/api/customers", params={"search": "%"})
    assert res_percent.json()["total"] == 1
    assert res_percent.json()["items"][0]["name"] == "100%サポート株式会社"

    res_underscore = client.get("/api/customers", params={"search": "_"})
    assert res_underscore.json()["total"] == 1
    assert res_underscore.json()["items"][0]["name"] == "A_Bテクノロジーズ"

    res_backslash = client.get("/api/customers", params={"search": "\\"})
    assert res_backslash.json()["total"] == 1
    assert res_backslash.json()["items"][0]["name"] == "C\\Dシステムズ"


def test_search_length_boundary(client: TestClient, customer_factory):
    customer_factory(name="アオバ製作所")
    ok = client.get("/api/customers", params={"search": "あ" * 80})
    assert ok.status_code == 200
    ng = client.get("/api/customers", params={"search": "あ" * 81})
    _assert_public_422(ng)


def test_search_blank_means_no_filter(client: TestClient, customer_factory):
    customer_factory(name="顧客A")
    customer_factory(name="顧客B")
    res = client.get("/api/customers", params={"search": "   "})
    assert res.json()["total"] == 2


def test_list_filters_by_area_status_owner(client: TestClient, customer_factory):
    customer_factory(name="東京見込み", area=CustomerArea.tokyo, status=CustomerStatus.prospect, owner_id=2)
    customer_factory(name="東京受注", area=CustomerArea.tokyo, status=CustomerStatus.won, owner_id=2)
    customer_factory(name="千葉見込み", area=CustomerArea.chiba, status=CustomerStatus.prospect, owner_id=3)

    res_area = client.get("/api/customers", params={"area": "tokyo"})
    assert res_area.json()["total"] == 2

    res_combo = client.get(
        "/api/customers", params={"area": "tokyo", "status": "prospect"}
    )
    assert res_combo.json()["total"] == 1
    assert res_combo.json()["items"][0]["name"] == "東京見込み"

    res_owner = client.get("/api/customers", params={"owner_id": 3})
    assert res_owner.json()["total"] == 1


def test_list_sort_whitelist(client: TestClient, customer_factory):
    customer_factory(name="ん社")
    customer_factory(name="あ社")

    res_asc = client.get("/api/customers", params={"sort": "name"})
    assert [c["name"] for c in res_asc.json()["items"]] == ["あ社", "ん社"]

    res_desc = client.get("/api/customers", params={"sort": "-name"})
    assert [c["name"] for c in res_desc.json()["items"]] == ["ん社", "あ社"]

    res_invalid = client.get("/api/customers", params={"sort": "address"})
    _assert_public_422(res_invalid)


def test_list_includes_last_visited_at(
    client: TestClient, db_session: Session, customer_factory
):
    with_visits = customer_factory(name="訪問あり")
    customer_factory(name="訪問なし")
    db_session.add_all(
        [
            Visit(
                customer_id=with_visits.id,
                user_id=1,
                activity_type=ActivityType.visit,
                status=VisitStatus.done,
                visited_at=datetime(2026, 5, 1, 10, 0, 0),
            ),
            Visit(
                customer_id=with_visits.id,
                user_id=1,
                activity_type=ActivityType.call,
                status=VisitStatus.done,
                visited_at=datetime(2026, 6, 1, 9, 30, 0),
            ),
        ]
    )
    db_session.commit()

    res = client.get("/api/customers", params={"sort": "name"})
    items = {item["name"]: item for item in res.json()["items"]}
    # 最新の visited_at が入る
    assert items["訪問あり"]["last_visited_at"] == "2026-06-01T09:30:00Z"
    assert items["訪問なし"]["last_visited_at"] is None


# --- GET 詳細 / PATCH / DELETE ---


def test_get_customer_404(client: TestClient, base_users):
    res = client.get("/api/customers/999")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found"}


def test_patch_customer_updates_fields_and_updated_at(
    client: TestClient, customer_factory
):
    customer = customer_factory(name="旧名", status=CustomerStatus.prospect)
    before = client.get(f"/api/customers/{customer.id}").json()

    res = client.patch(
        f"/api/customers/{customer.id}", json={"status": "negotiating"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "negotiating"
    assert body["updated_at"] > before["updated_at"]
    assert body["created_at"] == before["created_at"]


def test_patch_noop_returns_200_without_updating(
    client: TestClient, customer_factory
):
    # 空ボディ・不変値のみの PATCH は updated_at を進めない
    customer = customer_factory(name="変更なし")
    before = client.get(f"/api/customers/{customer.id}").json()

    res_empty = client.patch(f"/api/customers/{customer.id}", json={})
    assert res_empty.status_code == 200
    assert res_empty.json()["updated_at"] == before["updated_at"]

    res_same = client.patch(
        f"/api/customers/{customer.id}", json={"name": "変更なし"}
    )
    assert res_same.status_code == 200
    assert res_same.json()["updated_at"] == before["updated_at"]


def test_patch_null_for_required_field_is_422(client: TestClient, customer_factory):
    customer = customer_factory()
    for field in ("name", "area", "status", "owner_id"):
        res = client.patch(f"/api/customers/{customer.id}", json={field: None})
        _assert_public_422(res)


def test_patch_address_can_be_cleared(client: TestClient, customer_factory):
    customer = customer_factory(address="旧住所")
    res = client.patch(f"/api/customers/{customer.id}", json={"address": None})
    assert res.status_code == 200
    assert res.json()["address"] is None


def test_patch_unknown_owner_is_422(client: TestClient, customer_factory):
    customer = customer_factory()
    res = client.patch(f"/api/customers/{customer.id}", json={"owner_id": 999})
    _assert_public_422(res)


def test_patch_customer_404(client: TestClient, base_users):
    res = client.patch("/api/customers/999", json={"name": "x"})
    assert res.status_code == 404


def test_delete_customer_cascades_visits(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="削除対象")
    db_session.add(
        Visit(
            customer_id=customer.id,
            user_id=1,
            activity_type=ActivityType.visit,
            status=VisitStatus.done,
            visited_at=datetime(2026, 5, 10, 9, 0, 0),
        )
    )
    db_session.commit()

    res = client.delete(f"/api/customers/{customer.id}")
    assert res.status_code == 204

    assert client.get(f"/api/customers/{customer.id}").status_code == 404
    # 関連 visits も DB レベルで消えている（ON DELETE CASCADE。仕様）
    remaining = db_session.scalar(select(func.count()).select_from(Visit))
    assert remaining == 0


def test_sales_customer_delete_is_404_and_keeps_other_user_visits(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    customer = customer_factory(name="営業削除対象", owner_id=2)
    db_session.add(
        Visit(
            customer_id=customer.id,
            user_id=3,
            activity_type=ActivityType.visit,
            status=VisitStatus.done,
            visited_at=datetime(2026, 5, 10, 9, 0, 0),
        )
    )
    db_session.commit()
    sales = db_session.get(User, 2)
    assert sales is not None
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        res = client.delete(f"/api/customers/{customer.id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 404
    assert db_session.get(Customer, customer.id) is not None
    remaining = db_session.scalar(select(func.count()).select_from(Visit))
    assert remaining == 1


def test_delete_customer_404(client: TestClient, base_users):
    res = client.delete("/api/customers/999")
    assert res.status_code == 404
