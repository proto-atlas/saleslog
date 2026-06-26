import os
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.approval import (
    approve_agent_approval,
    cancel_agent_run,
    edit_agent_approval,
    reject_agent_approval,
)
from app.agent.citations import (
    redact_artifact_content_citation_quotes,
    redact_citation_candidate_quotes,
    redact_expired_run_sources,
    run_sources_all_authorized,
    source_still_authorized,
)
from app.agent.events import serialize_sse_event
from app.agent.text import stable_json_hash
from app.agent.worker_queue import run_pending_agent_work_once
from app.authz import (
    get_agent_approval_authorized,
    get_agent_run_authorized,
    get_customer_authorized,
)
from app.deps import get_current_user, get_db
from app.enums import AgentRunStatus, AgentWorkflowType, UserRole
from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentEvent,
    AgentEventCursor,
    AgentRun,
    AgentRunSource,
    User,
    utcnow_naive,
)
from app.schemas import (
    AgentApprovalDecision,
    AgentApprovalDecisionErrorResponse,
    AgentApprovalDecisionResponse,
    AgentApprovalOut,
    AgentApprovalPatch,
    AgentArtifactOut,
    AgentRunCreate,
    AgentRunCreateResponse,
    AgentRunOut,
    AgentRunSourceOut,
    ErrorDetailResponse,
)

router = APIRouter(prefix="/api", tags=["agent"])

ACTIVE_AGENT_RUN_STATUSES = (
    AgentRunStatus.pending,
    AgentRunStatus.running,
    AgentRunStatus.waiting_for_approval,
)
# 画面は1顧客につき1つのAgent操作パネルを想定している。短時間の連続投入で外部LLM処理が
# 積み上がらないよう、active runはユーザー単位で小さく制限する。
MAX_ACTIVE_AGENT_RUNS_PER_USER = 5
AGENT_RUN_HISTORY_LIMIT_MAX = 20

AGENT_APPROVAL_DECISION_RESPONSES: dict[int | str, dict[str, Any]] = {
    202: {"model": AgentApprovalDecisionErrorResponse},
    409: {"model": AgentApprovalDecisionErrorResponse},
    422: {
        "description": "Unprocessable Entity",
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {"$ref": "#/components/schemas/HTTPValidationError"},
                        {
                            "$ref": "#/components/schemas/AgentApprovalDecisionErrorResponse"
                        },
                    ]
                }
            }
        },
    },
}


@router.post(
    "/customers/{customer_id}/agent-runs",
    response_model=AgentRunCreateResponse,
    status_code=202,
)
def create_agent_run(
    customer_id: int,
    payload: AgentRunCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentRunCreateResponse:
    get_customer_authorized(db, current_user, customer_id)
    now = utcnow_naive()
    objective_hash = stable_json_hash(
        {
            "customer_id": customer_id,
            "workflow_type": payload.workflow_type.value,
            "objective": payload.objective,
        }
    )
    existing_run = _find_active_agent_run(
        db,
        user_id=current_user.id,
        customer_id=customer_id,
        workflow_type=payload.workflow_type,
        objective_hash=objective_hash,
    )
    if existing_run is not None:
        return AgentRunCreateResponse(
            run_id=existing_run.id,
            status=existing_run.status,
            reused=True,
        )
    active_run_count = (
        db.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                AgentRun.user_id == current_user.id,
                AgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES),
            )
        )
        or 0
    )
    if active_run_count >= MAX_ACTIVE_AGENT_RUNS_PER_USER:
        raise HTTPException(status_code=429, detail="agent_run_limit_exceeded")
    for _ in range(MAX_ACTIVE_AGENT_RUNS_PER_USER):
        active_slot = _find_available_active_slot(db, user_id=current_user.id)
        if active_slot is None:
            raise HTTPException(status_code=429, detail="agent_run_limit_exceeded")
        run = AgentRun(
            user_id=current_user.id,
            customer_id=customer_id,
            workflow_type=payload.workflow_type,
            objective=payload.objective,
            objective_hash=objective_hash,
            active_slot=active_slot,
            status=AgentRunStatus.pending,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing_run = _find_active_agent_run(
                db,
                user_id=current_user.id,
                customer_id=customer_id,
                workflow_type=payload.workflow_type,
                objective_hash=objective_hash,
            )
            if existing_run is not None:
                return AgentRunCreateResponse(
                    run_id=existing_run.id,
                    status=existing_run.status,
                    reused=True,
                )
            continue
        run_id = run.id
        status = run.status
        db.add(AgentEventCursor(run_id=run.id, last_event_seq=0, updated_at=now))
        db.commit()
        background_tasks.add_task(run_pending_agent_work_once)
        return AgentRunCreateResponse(run_id=run_id, status=status, reused=False)
    raise HTTPException(status_code=409, detail="agent_run_conflict")


def _find_available_active_slot(db: Session, *, user_id: int) -> int | None:
    used_slots = set(
        db.scalars(
            select(AgentRun.active_slot).where(
                AgentRun.user_id == user_id,
                AgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES),
                AgentRun.active_slot.is_not(None),
            )
        )
    )
    for slot in range(1, MAX_ACTIVE_AGENT_RUNS_PER_USER + 1):
        if slot not in used_slots:
            return slot
    return None


def _find_active_agent_run(
    db: Session,
    *,
    user_id: int,
    customer_id: int,
    workflow_type: AgentWorkflowType,
    objective_hash: str,
) -> AgentRun | None:
    return db.scalar(
        select(AgentRun)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.customer_id == customer_id,
            AgentRun.workflow_type == workflow_type,
            AgentRun.objective_hash == objective_hash,
            AgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES),
        )
        .order_by(AgentRun.id.desc())
        .limit(1)
    )


@router.get("/customers/{customer_id}/agent-runs", response_model=list[AgentRunOut])
def list_customer_agent_runs(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=AGENT_RUN_HISTORY_LIMIT_MAX)] = 10,
) -> list[AgentRun]:
    get_customer_authorized(db, current_user, customer_id)
    query = (
        select(AgentRun)
        .where(AgentRun.customer_id == customer_id)
        .order_by(AgentRun.id.desc())
        .limit(limit)
    )
    if current_user.role != UserRole.manager:
        query = query.where(AgentRun.user_id == current_user.id)
    return list(db.scalars(query).all())


@router.get("/agent-runs/{run_id}", response_model=AgentRunOut)
def get_agent_run(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentRun:
    return get_agent_run_authorized(db, current_user, run_id)


@router.get("/agent-runs/{run_id}/artifacts", response_model=list[AgentArtifactOut])
def list_agent_artifacts(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AgentArtifactOut]:
    run = get_agent_run_authorized(db, current_user, run_id)
    _redact_expired_run_sources_if_writable(db)
    if not _all_run_sources_authorized(db, run=run, current_user=current_user):
        return []
    artifacts = list(
        db.scalars(
            select(AgentArtifact)
            .where(AgentArtifact.run_id == run_id)
            .order_by(AgentArtifact.id)
        ).all()
    )
    return [_artifact_out(artifact) for artifact in artifacts]


def _artifact_out(artifact: AgentArtifact) -> AgentArtifactOut:
    return AgentArtifactOut.model_validate(artifact).model_copy(
        update={
            "content_json": redact_artifact_content_citation_quotes(
                artifact.content_json
            ),
            "citation_candidates_json": redact_citation_candidate_quotes(
                artifact.citation_candidates_json
            ),
        }
    )


def _all_run_sources_authorized(
    db: Session, *, run: AgentRun, current_user: User
) -> bool:
    return run_sources_all_authorized(db, run=run, current_user=current_user)


def _authorized_run_sources(
    db: Session, *, run: AgentRun, current_user: User
) -> list[AgentRunSource]:
    sources = db.scalars(
        select(AgentRunSource)
        .where(AgentRunSource.run_id == run.id)
        .order_by(AgentRunSource.id)
    ).all()
    return list(
        source
        for source in sources
        if source_still_authorized(
            db,
            source=source,
            current_user=current_user,
            customer_id=run.customer_id,
        )
    )


@router.get("/agent-runs/{run_id}/sources", response_model=list[AgentRunSourceOut])
def list_agent_sources(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AgentRunSource]:
    run = get_agent_run_authorized(db, current_user, run_id)
    _redact_expired_run_sources_if_writable(db)
    return _authorized_run_sources(db, run=run, current_user=current_user)


@router.get("/agent-runs/{run_id}/approvals", response_model=list[AgentApprovalOut])
def list_agent_approvals(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AgentApproval]:
    run = get_agent_run_authorized(db, current_user, run_id)
    _redact_expired_run_sources_if_writable(db)
    if not run_sources_all_authorized(db, run=run, current_user=current_user):
        return []
    return list(
        db.scalars(
            select(AgentApproval)
            .where(AgentApproval.run_id == run_id)
            .order_by(AgentApproval.id)
        ).all()
    )


@router.get("/agent-runs/{run_id}/events")
def stream_agent_events(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    get_agent_run_authorized(db, current_user, run_id)
    last_seq = _parse_last_event_id(last_event_id)
    max_seq = (
        db.scalar(
            select(func.max(AgentEvent.event_seq)).where(AgentEvent.run_id == run_id)
        )
        or 0
    )
    if last_seq > max_seq:
        raise HTTPException(status_code=409, detail="cursor_out_of_range")
    events = list(
        db.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id, AgentEvent.event_seq > last_seq)
            .order_by(AgentEvent.event_seq)
        ).all()
    )
    return StreamingResponse(
        _iter_sse_events(events),
        media_type="text/event-stream",
    )


@router.patch(
    "/agent-runs/{run_id}/approvals/{approval_id}",
    response_model=AgentApprovalOut,
    responses={409: {"model": ErrorDetailResponse}},
)
def patch_agent_approval(
    run_id: int,
    approval_id: int,
    payload: AgentApprovalPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentApproval:
    return edit_agent_approval(
        db,
        current_user=current_user,
        run_id=run_id,
        approval_id=approval_id,
        version=payload.version,
        edited_payload_json=payload.edited_payload_json,
    )


@router.post(
    "/agent-runs/{run_id}/approvals/{approval_id}/approve",
    response_model=AgentApprovalDecisionResponse,
    responses=AGENT_APPROVAL_DECISION_RESPONSES,
)
def approve_agent_action(
    run_id: int,
    approval_id: int,
    payload: AgentApprovalDecision,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    status_code, body = approve_agent_approval(
        db,
        current_user=current_user,
        run_id=run_id,
        approval_id=approval_id,
        idempotency_key=payload.idempotency_key,
        version=payload.version,
    )
    headers = {"Retry-After": "2"} if status_code == 202 else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


@router.post(
    "/agent-runs/{run_id}/approvals/{approval_id}/reject",
    response_model=AgentApprovalOut,
)
def reject_agent_action(
    run_id: int,
    approval_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentApproval:
    get_agent_approval_authorized(db, current_user, run_id, approval_id)
    return reject_agent_approval(
        db,
        current_user=current_user,
        run_id=run_id,
        approval_id=approval_id,
    )


@router.post(
    "/agent-runs/{run_id}/cancel",
    response_model=AgentRunOut,
    responses={409: {"model": ErrorDetailResponse}},
)
def cancel_agent_action_run(
    run_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentRun:
    return cancel_agent_run(db, current_user=current_user, run_id=run_id)


def _parse_last_event_id(last_event_id: str | None) -> int:
    if last_event_id is None:
        return 0
    try:
        value = int(last_event_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="invalid_last_event_id") from error
    if value < 0:
        raise HTTPException(status_code=400, detail="invalid_last_event_id")
    return value


def _redact_expired_run_sources_if_writable(db: Session) -> None:
    if os.environ.get("DEMO_READ_ONLY") == "true":
        return
    redact_expired_run_sources(db)
    db.commit()


def _iter_sse_events(events: list[AgentEvent]) -> Iterator[str]:
    for event in events:
        yield serialize_sse_event(event)
