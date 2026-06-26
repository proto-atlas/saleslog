from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.authz import is_manager
from app.deps import get_current_user, get_db
from app.enums import UserRole
from app.models import User, utcnow_naive
from app.schemas import UserCreate, UserListItem, UserOut, UserPatch, UsersResponse
from app.sqlalchemy_result import result_rowcount

router = APIRouter(prefix="/api/users", tags=["users"])

# /api/me は users と分けた prefix で公開する
me_router = APIRouter(prefix="/api", tags=["users"])


def _to_user_out(user: User, include_linked: bool = False) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        role=user.role,
        # 紐付け状況は管理用途（manager）のみに返す。担当者 lookup には不要な情報のため
        linked=(user.external_id is not None) if include_linked else None,
    )


def _to_user_list_item(user: User, include_admin_fields: bool = False) -> UserListItem:
    return UserListItem(
        id=user.id,
        name=user.name,
        role=user.role if include_admin_fields else None,
        linked=(user.external_id is not None) if include_admin_fields else None,
    )


@me_router.get("/me", response_model=UserOut)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    # フロントの role 出し分け用
    return _to_user_out(current_user)


@router.get("", response_model=UsersResponse)
def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    role: UserRole | None = None,
    db: Session = Depends(get_db),
) -> UsersResponse:
    # id 昇順固定（決定的 seed と E2E 再現性のため。仕様）
    stmt = select(User).order_by(User.id)
    if role is not None:
        if not is_manager(current_user):
            raise HTTPException(status_code=404, detail="Not Found")
        stmt = stmt.where(User.role == role)
    users = db.scalars(stmt).all()
    include_admin_fields = is_manager(current_user)
    return UsersResponse(
        items=[
            _to_user_list_item(user, include_admin_fields=include_admin_fields)
            for user in users
        ]
    )


def _require_manager(current_user: User) -> None:
    # ユーザー管理は manager のみ（sales には存在を見せない 404。認証仕様）
    if not is_manager(current_user):
        raise HTTPException(status_code=404, detail="Not Found")


def _validation_422(loc: list[str], msg: str) -> HTTPException:
    return HTTPException(
        status_code=422, detail=[{"loc": loc, "msg": msg, "type": "value_error"}]
    )


def _ensure_external_id_unused(
    db: Session, external_id: str, exclude_user_id: int
) -> None:
    duplicated = db.scalar(
        select(User).where(
            User.external_id == external_id, User.id != exclude_user_id
        )
    )
    if duplicated is not None:
        raise _validation_422(
            ["body", "external_id"], "既に別のユーザーに紐付いています"
        )


def _demote_manager_if_allowed(db: Session, user: User) -> None:
    manager_count = (
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.manager)
        .scalar_subquery()
    )
    result = db.execute(
        update(User)
        .where(
            User.id == user.id,
            User.role == UserRole.manager,
            manager_count > 1,
        )
        .values(role=UserRole.sales)
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        raise _validation_422(["body", "role"], "最後の管理者の役割は変更できません")
    db.refresh(user)


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    _require_manager(current_user)
    user = User(name=payload.name, role=payload.role, created_at=utcnow_naive())
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_user_out(user, include_linked=True)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    _require_manager(current_user)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Not Found")

    data = payload.model_dump(exclude_unset=True)
    for field in ("name", "role"):
        if field in data and data[field] is None:
            raise _validation_422(["body", field], "null は指定できません")

    if "role" in data and data["role"] != user.role:
        # 自分自身の役割変更は拒否（誤操作での自己降格を防ぐ。認証仕様）
        if user.id == current_user.id:
            raise _validation_422(["body", "role"], "自分自身の役割は変更できません")
        # 最後の manager の降格は拒否（管理不能状態を防ぐ。認証仕様）
        if user.role == UserRole.manager and data["role"] == UserRole.sales:
            _demote_manager_if_allowed(db, user)
            data.pop("role")

    if "external_id" in data:
        # 自分自身の紐付け変更・解除は拒否（clerk モードで自分を締め出すため。
        # 自分の紐付けを変える必要がある場合は link_user CLI を使う）
        if user.id == current_user.id:
            raise _validation_422(
                ["body", "external_id"], "自分自身の紐付けは変更できません"
            )
        if data["external_id"] is not None:
            _ensure_external_id_unused(
                db, data["external_id"], exclude_user_id=user.id
            )

    for field, new_value in data.items():
        setattr(user, field, new_value)
    db.commit()
    db.refresh(user)
    return _to_user_out(user, include_linked=True)
