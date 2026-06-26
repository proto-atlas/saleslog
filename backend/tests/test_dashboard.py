from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import ActivityType, CustomerArea, VisitStatus
from app.models import Visit
from app.timeutil import (
    jst_last_six_months,
    jst_six_months_window,
    jst_this_month_bounds,
    jst_today_bounds,
    utcnow_naive,
)


def _visit(customer_id: int, **overrides: object) -> Visit:
    values: dict[str, object] = {
        "customer_id": customer_id,
        "user_id": 1,
        "activity_type": ActivityType.visit,
        "status": VisitStatus.done,
        "visited_at": utcnow_naive() - timedelta(days=1),
    }
    values.update(overrides)
    return Visit(**values)


def test_summary_empty_db_returns_zeros_and_six_trend_buckets(
    client: TestClient, base_users
):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["total_customers"] == 0
    assert body["visits_this_month"] == 0
    assert body["unrecorded_count"] == 0
    assert body["today_visits"] == []
    assert body["by_area"] == []
    assert body["by_owner"] == []
    # 0 件でも常に 6 要素・昇順・当月含む
    months = [point["month"] for point in body["visits_trend"]]
    assert months == jst_last_six_months(utcnow_naive())
    assert all(point["count"] == 0 for point in body["visits_trend"])


def test_summary_trend_buckets_respect_jst_month_boundary(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    now = utcnow_naive()
    month_start_utc, _ = jst_this_month_bounds(now)
    # JST 月初の 30 分後（当月扱い）と 30 分前（前月扱い）。UTC 単純集計だと前月にずれる境界
    db_session.add_all(
        [
            _visit(customer.id, visited_at=month_start_utc + timedelta(minutes=30)),
            _visit(customer.id, visited_at=month_start_utc - timedelta(minutes=30)),
        ]
    )
    db_session.commit()

    body = client.get("/api/dashboard/summary").json()
    months = jst_last_six_months(now)
    counts = {point["month"]: point["count"] for point in body["visits_trend"]}
    assert counts[months[-1]] == 1  # 当月
    assert counts[months[-2]] == 1  # 前月
    assert body["visits_this_month"] == 1


def test_summary_trend_excludes_visits_outside_window(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory()
    window_start, _ = jst_six_months_window(utcnow_naive())
    db_session.add(
        _visit(customer.id, visited_at=window_start - timedelta(minutes=1))
    )
    db_session.commit()

    body = client.get("/api/dashboard/summary").json()
    assert all(point["count"] == 0 for point in body["visits_trend"])


def test_summary_by_area_and_owner_counts(
    client: TestClient, customer_factory
):
    customer_factory(area=CustomerArea.tokyo, owner_id=2)
    customer_factory(area=CustomerArea.tokyo, owner_id=2)
    customer_factory(area=CustomerArea.chiba, owner_id=3)

    body = client.get("/api/dashboard/summary").json()
    assert body["total_customers"] == 3
    area_counts = {entry["area"]: entry["count"] for entry in body["by_area"]}
    assert area_counts == {"tokyo": 2, "chiba": 1}
    owner_counts = {entry["owner_id"]: entry for entry in body["by_owner"]}
    assert owner_counts[2]["count"] == 2
    assert owner_counts[2]["owner_name"] == "営業ユーザーA"
    assert owner_counts[3]["count"] == 1


def test_summary_today_and_unrecorded_are_not_mutually_exclusive(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="今日の顧客")
    now = utcnow_naive()
    today_start, today_end = jst_today_bounds(now)
    db_session.add_all(
        [
            # 今日のうち過ぎた予定（深夜0時直後の実行では当日にならないため境界に丸める）
            _visit(
                customer.id,
                status=VisitStatus.planned,
                visited_at=max(today_start, now - timedelta(minutes=2)),
            ),
            # 今日のこれからの予定（23時台の実行では翌日にはみ出すため境界に丸める）
            _visit(
                customer.id,
                status=VisitStatus.planned,
                visited_at=min(today_end - timedelta(minutes=1), now + timedelta(hours=1)),
            ),
            # 昨日の入力漏れ（今日には出ない）
            _visit(
                customer.id,
                status=VisitStatus.planned,
                visited_at=today_start - timedelta(hours=3),
            ),
            # 今日の done は today_visits に含めない
            _visit(
                customer.id,
                status=VisitStatus.done,
                visited_at=max(today_start, now - timedelta(minutes=2)),
            ),
        ]
    )
    db_session.commit()

    body = client.get("/api/dashboard/summary").json()
    # 今日の予定 = planned 当日 2 件（過去分も含む。相互排他にしない。仕様）
    assert len(body["today_visits"]) == 2
    first = body["today_visits"][0]
    assert first["customer_name"] == "今日の顧客"
    assert {"visit_id", "customer_id", "owner_id", "visited_at", "status"} <= set(
        first.keys()
    )
    # 入力漏れ = 過ぎた planned（昨日 1 + 今日の過去分 1）
    assert body["unrecorded_count"] == 2
