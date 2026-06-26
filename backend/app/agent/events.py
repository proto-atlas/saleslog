import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.agent.faults import maybe_raise_agent_fault
from app.models import AgentEvent, AgentEventCursor, utcnow_naive

SAFE_MESSAGE_PARAMS: dict[str, set[str]] = {
    "run_created": set(),
    "customer_loaded": set(),
    "activities_loaded": {"result_count_bucket"},
    "knowledge_search_completed": {"result_count_bucket"},
    "drafting_completed": set(),
    "citation_verified": set(),
    "approval_required": {"approval_count"},
    "waiting_for_approval": set(),
    "completed": set(),
    "failed": {"error_code"},
    "cancelled": set(),
}


def _validate_safe_params(key: str, params: dict[str, object]) -> None:
    allowed = SAFE_MESSAGE_PARAMS.get(key)
    if allowed is None:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    if set(params) - allowed:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    for value in params.values():
        if not isinstance(value, str | int | bool):
            raise HTTPException(status_code=500, detail="Internal Server Error")


def count_bucket(count: int) -> str:
    if count == 0:
        return "zero"
    if count <= 3:
        return "one_to_three"
    return "four_or_more"


def create_agent_event(
    db: Session,
    *,
    run_id: int,
    event_type: str,
    status: str,
    safe_message_key: str,
    safe_message_params_json: dict[str, object] | None = None,
    step_no: int | None = None,
    artifact_id: int | None = None,
    approval_id: int | None = None,
) -> AgentEvent:
    params = safe_message_params_json or {}
    _validate_safe_params(safe_message_key, params)
    event_seq = _reserve_event_seq(db, run_id)
    maybe_raise_agent_fault("sse_event_write_failed_hook")
    event = AgentEvent(
        run_id=run_id,
        event_seq=event_seq,
        step_no=step_no,
        event_type=event_type,
        status=status,
        safe_message_key=safe_message_key,
        safe_message_params_json=params,
        artifact_id=artifact_id,
        approval_id=approval_id,
        created_at=utcnow_naive(),
    )
    db.add(event)
    db.flush()
    return event


def _reserve_event_seq(db: Session, run_id: int) -> int:
    now = utcnow_naive()
    result = db.execute(
        update(AgentEventCursor)
        .where(AgentEventCursor.run_id == run_id)
        .values(
            last_event_seq=AgentEventCursor.last_event_seq + 1,
            updated_at=now,
        )
        .returning(AgentEventCursor.last_event_seq)
        .execution_options(synchronize_session=False)
    )
    event_seq = result.scalar_one_or_none()
    if event_seq is not None:
        return int(event_seq)
    cursor = AgentEventCursor(run_id=run_id, last_event_seq=1, updated_at=now)
    db.add(cursor)
    db.flush()
    return 1


def serialize_sse_event(event: AgentEvent) -> str:
    payload = {
        "run_id": str(event.run_id),
        "event_seq": event.event_seq,
        "step_no": event.step_no,
        "status": event.status,
        "safe_message_key": event.safe_message_key,
        "safe_message_params_json": event.safe_message_params_json,
        "artifact_id": event.artifact_id,
        "approval_id": event.approval_id,
        "created_at": _to_utc_z(event.created_at),
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.event_seq}\nevent: {event.event_type}\ndata: {data}\n\n"


def _to_utc_z(value: datetime) -> str:
    return value.isoformat() + "Z"
