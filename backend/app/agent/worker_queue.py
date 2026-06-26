from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agent.approval import expire_pending_approvals, reap_stale_idempotency_records
from app.agent.citations import redact_expired_run_sources
from app.agent.events import create_agent_event
from app.agent.faults import maybe_raise_agent_fault
from app.agent.worker import process_agent_run_in_session
from app.db import SessionLocal
from app.enums import AgentRunStatus
from app.models import AgentRun, utcnow_naive
from app.sqlalchemy_result import result_rowcount

WORKER_LOCK_SECONDS = 180
CLAIM_CANDIDATE_LIMIT = 10


def run_pending_agent_work_once(worker_id: str | None = None) -> int:
    owner = worker_id or f"worker:{uuid4().hex}"
    processed = 0
    with SessionLocal() as db:
        redact_expired_run_sources(db)
        expire_pending_approvals(db)
        reap_stale_agent_runs(db, owner=owner)
        reap_stale_idempotency_records(db)
        db.commit()
        while True:
            run_id = claim_next_pending_run(db, owner=owner)
            if run_id is None:
                break
            maybe_raise_agent_fault("worker_heartbeat_stopped_hook")
            process_agent_run_in_session(db, run_id, worker_id=owner)
            processed += 1
    return processed


def claim_next_pending_run(db: Session, *, owner: str) -> int | None:
    run_ids = list(
        db.scalars(
            select(AgentRun.id)
            .where(
                AgentRun.status == AgentRunStatus.pending,
                AgentRun.locked_by.is_(None),
            )
            .order_by(AgentRun.id)
            .limit(CLAIM_CANDIDATE_LIMIT)
        ).all()
    )
    if not run_ids:
        return None
    now = utcnow_naive()
    for run_id in run_ids:
        result = db.execute(
            update(AgentRun)
            .where(
                AgentRun.id == run_id,
                AgentRun.status == AgentRunStatus.pending,
                AgentRun.locked_by.is_(None),
            )
            .values(
                locked_by=owner,
                locked_until=now + timedelta(seconds=WORKER_LOCK_SECONDS),
                heartbeat_at=now,
                updated_at=now,
            )
        )
        if result_rowcount(result) == 1:
            db.commit()
            return run_id
    return None


def reap_stale_agent_runs(db: Session, *, owner: str) -> int:
    now = utcnow_naive()
    pending_result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.status == AgentRunStatus.pending,
            AgentRun.locked_by.is_not(None),
            AgentRun.locked_until.is_not(None),
            AgentRun.locked_until < now,
        )
        .values(
            locked_by=None,
            locked_until=None,
            heartbeat_at=None,
            updated_at=now,
        )
    )
    failed_run_ids = list(
        db.scalars(
            update(AgentRun)
            .where(
                AgentRun.status == AgentRunStatus.running,
                AgentRun.locked_until.is_not(None),
                AgentRun.locked_until < now,
            )
            .values(
                status=AgentRunStatus.failed,
                locked_by=None,
                locked_until=None,
                completed_at=now,
                last_error_code="agent_worker_heartbeat_timeout",
                last_error_message_safe="Agent実行がタイムアウトしました",
                updated_at=now,
            )
            .returning(AgentRun.id)
            .execution_options(synchronize_session=False)
        ).all()
    )
    for run_id in failed_run_ids:
        create_agent_event(
            db,
            run_id=run_id,
            event_type="failed",
            status=AgentRunStatus.failed.value,
            safe_message_key="failed",
            safe_message_params_json={
                "error_code": "agent_worker_heartbeat_timeout"
            },
        )
    return result_rowcount(pending_result) + len(failed_run_ids)
