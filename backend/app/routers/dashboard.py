from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.authz import is_manager
from app.deps import get_current_user, get_db
from app.enums import VisitStatus
from app.models import Customer, User, Visit
from app.schemas import (
    AreaCount,
    DashboardSummary,
    OwnerCount,
    TodayVisit,
    TrendPoint,
)
from app.timeutil import (
    jst_last_six_months,
    jst_month_key,
    jst_six_months_window,
    jst_this_month_bounds,
    jst_today_bounds,
    utcnow_naive,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardSummary:
    now = utcnow_naive()

    # sales は現在担当顧客に紐づく自分の活動記録だけを集計する
    manager = is_manager(current_user)
    customer_scope = [] if manager else [Customer.owner_id == current_user.id]
    visit_scope = (
        []
        if manager
        else [
            Visit.user_id == current_user.id,
            Visit.customer.has(Customer.owner_id == current_user.id),
        ]
    )

    total_customers = (
        db.scalar(select(func.count()).select_from(Customer).where(*customer_scope))
        or 0
    )

    month_start, month_end = jst_this_month_bounds(now)
    visits_this_month = (
        db.scalar(
            select(func.count())
            .select_from(Visit)
            .where(
                *visit_scope,
                Visit.visited_at >= month_start,
                Visit.visited_at < month_end,
            )
        )
        or 0
    )

    # 月次推移: SQLite はタイムゾーンを扱えないため、対象期間を取得して Python 側で
    # JST の月バケットに集計し、0 件の月も 6 要素に埋める
    window_start, window_end = jst_six_months_window(now)
    visited_in_window = db.scalars(
        select(Visit.visited_at).where(
            *visit_scope,
            Visit.visited_at >= window_start,
            Visit.visited_at < window_end,
        )
    ).all()
    bucket_counts = Counter(jst_month_key(visited_at) for visited_at in visited_in_window)
    visits_trend = [
        TrendPoint(month=month, count=bucket_counts.get(month, 0))
        for month in jst_last_six_months(now)
    ]

    by_area = [
        AreaCount(area=area, count=count)
        for area, count in db.execute(
            select(Customer.area, func.count())
            .where(*customer_scope)
            .group_by(Customer.area)
            .order_by(Customer.area)
        ).all()
    ]

    # sales の担当者別は自分のみの 1 要素に縮退する
    by_owner = [
        OwnerCount(owner_id=owner_id, owner_name=owner_name, count=count)
        for owner_id, owner_name, count in db.execute(
            select(Customer.owner_id, User.name, func.count())
            .join(User, Customer.owner_id == User.id)
            .where(*customer_scope)
            .group_by(Customer.owner_id, User.name)
            .order_by(Customer.owner_id)
        ).all()
    ]

    # 入力漏れ: planned のまま予定日時を過ぎた visit
    unrecorded_count = (
        db.scalar(
            select(func.count())
            .select_from(Visit)
            .where(
                *visit_scope,
                Visit.status == VisitStatus.planned,
                Visit.visited_at < now,
            )
        )
        or 0
    )

    # 今日の予定: JST 当日の planned 全件（入力漏れと相互排他にしない。仕様）
    today_start, today_end = jst_today_bounds(now)
    today_rows = db.execute(
        select(Visit, Customer.name, Customer.owner_id)
        .join(Customer, Visit.customer_id == Customer.id)
        .where(
            *visit_scope,
            Visit.status == VisitStatus.planned,
            Visit.visited_at >= today_start,
            Visit.visited_at < today_end,
        )
        .order_by(Visit.visited_at.asc(), Visit.id.asc())
    ).all()
    today_visits = [
        TodayVisit(
            visit_id=visit.id,
            customer_id=visit.customer_id,
            customer_name=customer_name,
            owner_id=owner_id,
            visited_at=visit.visited_at,
            status=visit.status,
        )
        for visit, customer_name, owner_id in today_rows
    ]

    return DashboardSummary(
        total_customers=total_customers,
        visits_this_month=visits_this_month,
        visits_trend=visits_trend,
        by_area=by_area,
        by_owner=by_owner,
        unrecorded_count=unrecorded_count,
        today_visits=today_visits,
    )
