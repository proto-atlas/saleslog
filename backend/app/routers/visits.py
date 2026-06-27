from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.authz import get_visit_authorized, is_manager
from app.deps import get_current_user, get_db
from app.enums import VisitStatus
from app.models import Customer, User, Visit, utcnow_naive
from app.schemas import ListResponse, VisitCreate, VisitListItem, VisitOut, VisitPatch

router = APIRouter(prefix="/api/visits", tags=["visits"])


def _query_datetime_to_naive_utc(value: datetime, param: str) -> datetime:
    # クエリの日時も ISO 8601 UTC 必須。タイムゾーンなしは 422
    if value.tzinfo is None:
        raise _validation_422(
            ["query", param], "タイムゾーン付きの ISO 8601 形式で指定してください"
        )
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _validation_422(loc: list[str], msg: str) -> HTTPException:
    return HTTPException(
        status_code=422, detail=[{"loc": loc, "msg": msg, "type": "value_error"}]
    )


@router.get("", response_model=ListResponse[VisitListItem])
def list_visits(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    customer_id: int | None = None,
    user_id: int | None = None,
    status: VisitStatus | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    unrecorded: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListResponse[VisitListItem]:
    conditions = []
    if customer_id is not None:
        conditions.append(Visit.customer_id == customer_id)
    if not is_manager(current_user):
        # sales は現在担当顧客に紐づく自分の記録のみ（サーバ強制。仕様）
        conditions.append(Customer.owner_id == current_user.id)
        conditions.append(Visit.user_id == current_user.id)
    elif user_id is not None:
        conditions.append(Visit.user_id == user_id)

    if unrecorded is True:
        # 入力漏れ指定時は status / from / to を無視して固定フィルタ
        conditions.append(Visit.status == VisitStatus.planned)
        conditions.append(Visit.visited_at < utcnow_naive())
    else:
        if status is not None:
            conditions.append(Visit.status == status)
        from_utc = (
            _query_datetime_to_naive_utc(from_, "from") if from_ is not None else None
        )
        to_utc = _query_datetime_to_naive_utc(to, "to") if to is not None else None
        if from_utc is not None and to_utc is not None and from_utc > to_utc:
            raise _validation_422(["query", "from"], "from は to 以前にしてください")
        if from_utc is not None:
            conditions.append(Visit.visited_at >= from_utc)
        if to_utc is not None:
            conditions.append(Visit.visited_at <= to_utc)

    total = (
        db.scalar(
            select(func.count())
            .select_from(Visit)
            .join(Customer, Visit.customer_id == Customer.id)
            .where(*conditions)
        )
        or 0
    )
    rows = db.execute(
        select(Visit, Customer.name, Customer.owner_id, User.name)
        .join(Customer, Visit.customer_id == Customer.id)
        .join(User, Visit.user_id == User.id)
        .where(*conditions)
        # visited_at 降順固定（sort パラメータなし。仕様）
        .order_by(Visit.visited_at.desc(), Visit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        VisitListItem(
            id=visit.id,
            customer_id=visit.customer_id,
            customer_name=customer_name,
            owner_id=owner_id,
            user_id=visit.user_id,
            user_name=user_name,
            activity_type=visit.activity_type,
            status=visit.status,
            visited_at=visit.visited_at,
            created_at=visit.created_at,
            updated_at=visit.updated_at,
        )
        for visit, customer_name, owner_id, user_name in rows
    ]
    return ListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=VisitOut, status_code=201)
def create_visit(
    payload: VisitCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Visit:
    # 存在しない FK は 422 に統一
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise _validation_422(["body", "customer_id"], "存在しない顧客です")
    # sales は自分担当の顧客にのみ作成可（他担当は 404。顧客詳細の 404 方針と整合。仕様）
    if not is_manager(current_user) and customer.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not Found")
    now = utcnow_naive()
    visit = Visit(
        customer_id=payload.customer_id,
        # user_id はボディで受けず、常に現在ユーザー
        user_id=current_user.id,
        activity_type=payload.activity_type,
        status=payload.status,
        visited_at=payload.visited_at,
        memo=payload.memo,
        created_at=now,
        updated_at=now,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Visit:
    return get_visit_authorized(db, current_user, visit_id)


@router.patch("/{visit_id}", response_model=VisitOut)
def update_visit(
    visit_id: int,
    payload: VisitPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Visit:
    visit = get_visit_authorized(db, current_user, visit_id)
    data = payload.model_dump(exclude_unset=True)

    # NOT NULL 列への明示 null は 422（memo のみ null 可）
    for field in ("activity_type", "status", "visited_at"):
        if field in data and data[field] is None:
            raise _validation_422(["body", field], "null は指定できません")

    # 実質変更があるときだけ updated_at を進める（no-op は UPDATE しない。仕様）
    changed = False
    for field, new_value in data.items():
        if getattr(visit, field) != new_value:
            setattr(visit, field, new_value)
            changed = True
    if changed:
        visit.updated_at = utcnow_naive()
        db.commit()
        db.refresh(visit)
    return visit


@router.delete("/{visit_id}", status_code=204)
def delete_visit(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    visit = get_visit_authorized(db, current_user, visit_id)
    db.delete(visit)
    db.commit()
