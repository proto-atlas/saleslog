"""role 別の認可スコープ。

方針: 権限外は 404（リソースの存在を漏らさない）。
例外は sales の owner_id 指定 POST のみ 422（users が lookup で公開されているため）。
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.enums import UserRole
from app.models import AgentApproval, AgentRun, Customer, User, Visit


def is_manager(user: User) -> bool:
    return user.role == UserRole.manager


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not Found")


def get_customer_authorized(
    db: Session, current_user: User, customer_id: int
) -> Customer:
    """顧客を取得し、sales は自分担当（owner_id = 自分）以外を 404 にする。"""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise _not_found()
    db.refresh(customer)
    if not is_manager(current_user) and customer.owner_id != current_user.id:
        raise _not_found()
    return customer


def get_visit_authorized(db: Session, current_user: User, visit_id: int) -> Visit:
    """活動記録を取得し、sales は自分の記録（user_id = 自分）以外を 404 にする。"""
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise _not_found()
    db.refresh(visit)
    if not is_manager(current_user) and visit.user_id != current_user.id:
        raise _not_found()
    return visit


def get_agent_run_authorized(
    db: Session, current_user: User, run_id: int
) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise _not_found()
    db.refresh(run)
    customer = get_customer_authorized(db, current_user, run.customer_id)
    if not is_manager(current_user) and run.user_id != current_user.id:
        raise _not_found()
    if customer.id != run.customer_id:
        raise _not_found()
    return run


def get_agent_approval_authorized(
    db: Session, current_user: User, run_id: int, approval_id: int
) -> AgentApproval:
    run = get_agent_run_authorized(db, current_user, run_id)
    approval = db.get(AgentApproval, approval_id)
    if approval is None or approval.run_id != run.id:
        raise _not_found()
    return approval
