from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.authz import get_customer_authorized, is_manager
from app.deps import get_current_user, get_db
from app.enums import CustomerArea, CustomerStatus
from app.models import Customer, User, Visit, utcnow_naive
from app.schemas import (
    CustomerCreate,
    CustomerListItem,
    CustomerOut,
    CustomerPatch,
    ListResponse,
    VisitListItem,
)

router = APIRouter(prefix="/api/customers", tags=["customers"])

SortKey = Literal["name", "-name", "created_at", "-created_at", "updated_at", "-updated_at"]


def _sort_clause(sort: SortKey):
    column = {
        "name": Customer.name,
        "created_at": Customer.created_at,
        "updated_at": Customer.updated_at,
    }[sort.removeprefix("-")]
    return column.desc() if sort.startswith("-") else column.asc()


def _validation_422(loc: list[str], msg: str) -> HTTPException:
    # FK 違反などアプリ判定のエラーも FastAPI 標準の 422 detail 形式に揃える
    return HTTPException(
        status_code=422, detail=[{"loc": loc, "msg": msg, "type": "value_error"}]
    )


def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return customer


@router.get("", response_model=ListResponse[CustomerListItem])
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: Annotated[str | None, Query(max_length=80)] = None,
    area: CustomerArea | None = None,
    status: CustomerStatus | None = None,
    owner_id: int | None = None,
    sort: SortKey | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListResponse[CustomerListItem]:
    conditions = []
    # sales は自分担当の顧客のみ（クエリの owner_id に関わらずサーバ側で強制。仕様）
    if not is_manager(current_user):
        conditions.append(Customer.owner_id == current_user.id)
    if search is not None and search.strip():
        # 検索はこの 1 経路に統一: LOWER(name) LIKE :q ESCAPE 相当（メタ文字は autoescape。仕様）
        conditions.append(
            func.lower(Customer.name).contains(search.lower(), autoescape=True)
        )
    if area is not None:
        conditions.append(Customer.area == area)
    if status is not None:
        conditions.append(Customer.status == status)
    # owner_id フィルタは manager のみ有効（sales はクライアント指定を無視して自分に強制。仕様）
    if owner_id is not None and is_manager(current_user):
        conditions.append(Customer.owner_id == owner_id)

    # total はフィルタ適用後・ページ分割前の件数
    total = db.scalar(select(func.count()).select_from(Customer).where(*conditions)) or 0

    # N+1 を避けるため最新 visited_at を集約 JOIN で取得
    last_visited_conditions = []
    if not is_manager(current_user):
        # sales は派生値（最終訪問日時）も自分の記録のみ（履歴 API と同じ強制。認証仕様）
        last_visited_conditions.append(Visit.user_id == current_user.id)
    last_visited = (
        select(Visit.customer_id, func.max(Visit.visited_at).label("last_visited_at"))
        .where(*last_visited_conditions)
        .group_by(Visit.customer_id)
        .subquery()
    )
    order_clauses = [_sort_clause(sort)] if sort is not None else []
    # 同値時もページ分割が安定するよう id を最終ソートキーにする
    order_clauses.append(Customer.id.asc())

    rows = db.execute(
        select(Customer, last_visited.c.last_visited_at)
        .outerjoin(last_visited, last_visited.c.customer_id == Customer.id)
        .where(*conditions)
        .order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        CustomerListItem(
            id=customer.id,
            name=customer.name,
            address=customer.address,
            area=customer.area,
            status=customer.status,
            owner_id=customer.owner_id,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            last_visited_at=last_visited_at,
        )
        for customer, last_visited_at in rows
    ]
    # 総ページ数を超える page は 200 + 空 items（404 にしない。仕様）
    return ListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Customer:
    # owner_id 省略時は現在ユーザー
    owner_id = payload.owner_id if payload.owner_id is not None else current_user.id
    # sales は自分以外の owner_id を指定できない（404 統一の例外として 422。仕様）
    if not is_manager(current_user) and owner_id != current_user.id:
        raise _validation_422(["body", "owner_id"], "自分以外の担当者は指定できません")
    if db.get(User, owner_id) is None:
        raise _validation_422(["body", "owner_id"], "存在しない担当者です")
    # created_at と updated_at は同値で初期化する
    now = utcnow_naive()
    customer = Customer(
        name=payload.name,
        address=payload.address,
        area=payload.area,
        status=payload.status,
        owner_id=owner_id,
        created_at=now,
        updated_at=now,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Customer:
    return get_customer_authorized(db, current_user, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Customer:
    customer = get_customer_authorized(db, current_user, customer_id)
    data = payload.model_dump(exclude_unset=True)

    # 担当者変更（owner_id を含む PATCH）は manager のみ。sales は 404 で明示拒否
    if "owner_id" in data and not is_manager(current_user):
        raise HTTPException(status_code=404, detail="Not Found")

    # NOT NULL 列への明示 null は入力値の問題として 422（address のみ null 可）
    for field in ("name", "area", "status", "owner_id"):
        if field in data and data[field] is None:
            raise _validation_422(["body", field], "null は指定できません")
    if "owner_id" in data and db.get(User, data["owner_id"]) is None:
        raise _validation_422(["body", "owner_id"], "存在しない担当者です")

    # 実質変更があるときだけ updated_at を進めて UPDATE する（no-op は発行しない。仕様）
    changed = False
    for field, new_value in data.items():
        if getattr(customer, field) != new_value:
            setattr(customer, field, new_value)
            changed = True
    if changed:
        customer.updated_at = utcnow_naive()
        db.commit()
        db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    if not is_manager(current_user):
        raise HTTPException(status_code=404, detail="Not Found")
    customer = get_customer_authorized(db, current_user, customer_id)
    # 関連 visits は DB の ON DELETE CASCADE が削除する
    db.delete(customer)
    db.commit()


@router.get("/{customer_id}/visits", response_model=ListResponse[VisitListItem])
def list_customer_visits(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListResponse[VisitListItem]:
    # まず顧客の認可を通し、通った場合のみ履歴を返す
    customer = get_customer_authorized(db, current_user, customer_id)

    conditions = [Visit.customer_id == customer_id]
    if not is_manager(current_user):
        # sales は履歴も自分の記録のみ（/api/visits と同じ強制。認証仕様）
        conditions.append(Visit.user_id == current_user.id)

    total = (
        db.scalar(select(func.count()).select_from(Visit).where(*conditions)) or 0
    )
    rows = db.execute(
        select(Visit, User.name)
        .join(User, Visit.user_id == User.id)
        .where(*conditions)
        # visited_at 降順固定。同時刻は id 降順で安定させる
        .order_by(Visit.visited_at.desc(), Visit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        VisitListItem(
            id=visit.id,
            customer_id=customer.id,
            customer_name=customer.name,
            owner_id=customer.owner_id,
            user_id=visit.user_id,
            user_name=user_name,
            activity_type=visit.activity_type,
            status=visit.status,
            visited_at=visit.visited_at,
            created_at=visit.created_at,
            updated_at=visit.updated_at,
        )
        for visit, user_name in rows
    ]
    return ListResponse(items=items, total=total, page=page, page_size=page_size)
