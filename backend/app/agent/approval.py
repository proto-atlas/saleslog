from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.citations import run_sources_all_authorized
from app.agent.events import create_agent_event
from app.agent.faults import maybe_raise_agent_fault
from app.agent.text import stable_json_hash
from app.authz import get_agent_approval_authorized, get_customer_authorized
from app.enums import (
    ActivityType,
    AgentActionType,
    AgentApprovalStatus,
    AgentIdempotencyFailureKind,
    AgentIdempotencyStatus,
    AgentRunStatus,
    VisitStatus,
)
from app.models import (
    AgentApproval,
    AgentApprovalIdempotencyRecord,
    AgentEmailProposal,
    AgentMemo,
    AgentPersistedAction,
    AgentRun,
    AgentTask,
    User,
    Visit,
    utcnow_naive,
)
from app.sqlalchemy_result import result_rowcount

IDEMPOTENCY_LOCK_TTL_SECONDS = 120  # approval persistは短時間処理のため、LLM実行時間とは分離する。
# claim_ids は画面確認と根拠照合用。1つの提案に紐付く根拠数を人が読める量に抑える。
MAX_APPROVAL_CLAIM_IDS = 20
MAX_APPROVAL_CLAIM_ID_LENGTH = 80

ALLOWED_APPROVAL_PAYLOAD_KEYS: dict[AgentActionType, set[str]] = {
    AgentActionType.task: {"title", "description", "claim_ids"},
    AgentActionType.memo: {"title", "body", "claim_ids"},
    AgentActionType.email_draft: {"subject", "body", "claim_ids"},
    AgentActionType.activity_log: {"description", "claim_ids"},
}

FINAL_APPROVAL_STATUSES = (
    AgentApprovalStatus.persisted,
    AgentApprovalStatus.rejected,
    AgentApprovalStatus.expired,
    AgentApprovalStatus.cancelled,
)


def approve_agent_approval(
    db: Session,
    *,
    current_user: User,
    run_id: int,
    approval_id: int,
    idempotency_key: str,
    version: int,
) -> tuple[int, dict[str, object]]:
    approval = get_agent_approval_authorized(db, current_user, run_id, approval_id)
    run = db.get(AgentRun, approval.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not Found")
    _ensure_run_sources_allow_approval(db, current_user=current_user, run=run)

    request_hash = stable_json_hash(
        {
            "method": "POST",
            "path": f"/api/agent-runs/{run_id}/approvals/{approval_id}/approve",
            "run_id": run_id,
            "approval_id": approval_id,
            "version": version,
            "payload_hash": stable_json_hash(
                approval.edited_payload_json or approval.original_payload_json
            ),
            "body": {"idempotency_key": idempotency_key, "version": version},
        }
    )
    inserted, record = _insert_or_get_idempotency_record(
        db, approval_id=approval.id, idempotency_key=idempotency_key, request_hash=request_hash
    )
    if not inserted:
        return _handle_existing_idempotency_record(db, approval, record, request_hash)
    if run.status != AgentRunStatus.waiting_for_approval:
        body = _error_body("run_not_waiting_for_approval", retry_with_new_idempotency_key=False)
        _mark_record_failed(db, record, 409, body, AgentIdempotencyFailureKind.permanent)
        db.commit()
        return 409, body
    if _expire_if_needed(db, approval):
        try_finalize_run(db, run.id)
        body = _error_body("approval_expired", retry_with_new_idempotency_key=False)
        _mark_record_failed(db, record, 409, body, AgentIdempotencyFailureKind.permanent)
        db.commit()
        return 409, body
    return _persist_approved_action(
        db,
        current_user=current_user,
        run=run,
        approval=approval,
        record=record,
        idempotency_key=idempotency_key,
        version=version,
    )


def edit_agent_approval(
    db: Session,
    *,
    current_user: User,
    run_id: int,
    approval_id: int,
    version: int,
    edited_payload_json: dict[str, object],
) -> AgentApproval:
    approval = get_agent_approval_authorized(db, current_user, run_id, approval_id)
    run = db.get(AgentRun, approval.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not Found")
    _ensure_run_sources_allow_approval(db, current_user=current_user, run=run)
    _ensure_run_allows_approval(run)
    if approval.status != AgentApprovalStatus.pending:
        raise HTTPException(status_code=409, detail="approval_not_pending")
    _validate_payload(approval.action_type, edited_payload_json)
    if not _update_pending_approval_edit(
        db,
        approval=approval,
        edited_payload_json=edited_payload_json,
        expected_version=version,
    ):
        raise HTTPException(status_code=409, detail="approval_not_pending")
    db.commit()
    db.refresh(approval)
    return approval


def reject_agent_approval(
    db: Session,
    *,
    current_user: User,
    run_id: int,
    approval_id: int,
) -> AgentApproval:
    approval = get_agent_approval_authorized(db, current_user, run_id, approval_id)
    run = db.get(AgentRun, approval.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Not Found")
    _ensure_run_sources_allow_approval(db, current_user=current_user, run=run)
    _ensure_run_allows_approval(run)
    if _expire_if_needed(db, approval):
        try_finalize_run(db, run.id)
        db.commit()
        raise HTTPException(status_code=409, detail="approval_expired")
    if not _reject_pending_approval(db, approval=approval, current_user=current_user):
        raise HTTPException(status_code=409, detail="approval_not_pending")
    create_agent_event(
        db,
        run_id=run.id,
        event_type="approval_rejected",
        status=run.status.value,
        safe_message_key="completed",
        approval_id=approval.id,
    )
    try_finalize_run(db, run.id)
    db.commit()
    db.refresh(approval)
    return approval


def cancel_agent_run(db: Session, *, current_user: User, run_id: int) -> AgentRun:
    from app.authz import get_agent_run_authorized

    run = get_agent_run_authorized(db, current_user, run_id)
    if run.status not in (
        AgentRunStatus.pending,
        AgentRunStatus.running,
        AgentRunStatus.waiting_for_approval,
    ):
        raise HTTPException(status_code=409, detail="run_not_cancellable")
    if _run_has_persist_failed_approval(db, run_id=run.id):
        raise HTTPException(status_code=409, detail="approval_reconciliation_required")
    now = utcnow_naive()
    if not _cancel_active_run(db, run_id=run.id, now=now):
        db.rollback()
        raise HTTPException(status_code=409, detail="run_not_cancellable")
    db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.run_id == run.id,
            AgentApproval.status.in_(
                (
                    AgentApprovalStatus.pending,
                    AgentApprovalStatus.approved,
                    AgentApprovalStatus.edited_and_approved,
                )
            ),
        )
        .values(status=AgentApprovalStatus.cancelled, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    create_agent_event(
        db,
        run_id=run.id,
        event_type="cancelled",
        status=AgentRunStatus.cancelled.value,
        safe_message_key="cancelled",
    )
    db.commit()
    db.refresh(run)
    return run


def _run_has_persist_failed_approval(db: Session, *, run_id: int) -> bool:
    return (
        db.scalar(
            select(AgentApproval.id)
            .where(
                AgentApproval.run_id == run_id,
                AgentApproval.status == AgentApprovalStatus.persist_failed,
            )
            .limit(1)
        )
        is not None
    )


def try_finalize_run(db: Session, run_id: int) -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if run is None or run.status != AgentRunStatus.waiting_for_approval:
        return run
    approvals = list(
        db.scalars(
            select(AgentApproval)
            .where(AgentApproval.run_id == run.id)
            .execution_options(populate_existing=True)
        ).all()
    )
    if not approvals:
        return run
    if any(approval.status == AgentApprovalStatus.persist_failed for approval in approvals):
        return run
    if all(approval.status in FINAL_APPROVAL_STATUSES for approval in approvals):
        if _complete_waiting_run(db, run_id=run.id):
            create_agent_event(
                db,
                run_id=run.id,
                event_type="completed",
                status=AgentRunStatus.completed.value,
                safe_message_key="completed",
            )
            db.refresh(run)
    return run


def _update_pending_approval_edit(
    db: Session,
    *,
    approval: AgentApproval,
    edited_payload_json: dict[str, object],
    expected_version: int,
) -> bool:
    result = db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.id == approval.id,
            AgentApproval.status == AgentApprovalStatus.pending,
            AgentApproval.version == expected_version,
        )
        .values(
            edited_payload_json=edited_payload_json,
            version=AgentApproval.version + 1,
            updated_at=utcnow_naive(),
        )
        .execution_options(synchronize_session=False)
    )
    return result_rowcount(result) == 1


def _cancel_active_run(db: Session, *, run_id: int, now: datetime) -> bool:
    result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status.in_(
                (
                    AgentRunStatus.pending,
                    AgentRunStatus.running,
                    AgentRunStatus.waiting_for_approval,
                )
            ),
        )
        .values(
            status=AgentRunStatus.cancelled,
            completed_at=now,
            locked_by=None,
            locked_until=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    return result_rowcount(result) == 1


def _complete_waiting_run(db: Session, *, run_id: int) -> bool:
    now = utcnow_naive()
    result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status == AgentRunStatus.waiting_for_approval,
        )
        .values(
            status=AgentRunStatus.completed,
            completed_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    return result_rowcount(result) == 1


def _insert_or_get_idempotency_record(
    db: Session,
    *,
    approval_id: int,
    idempotency_key: str,
    request_hash: str,
) -> tuple[bool, AgentApprovalIdempotencyRecord]:
    now = utcnow_naive()
    record = AgentApprovalIdempotencyRecord(
        approval_id=approval_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status=AgentIdempotencyStatus.in_progress,
        locked_until=now + timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS),
        processing_started_at=now,
        processing_owner=f"request:{uuid4().hex}",
        lease_token=uuid4().hex,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        maybe_raise_agent_fault("idempotency_record_created_then_process_crashed_hook")
        return True, record
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AgentApprovalIdempotencyRecord).where(
                AgentApprovalIdempotencyRecord.approval_id == approval_id,
                AgentApprovalIdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise
        return False, existing


def _handle_existing_idempotency_record(
    db: Session,
    approval: AgentApproval,
    record: AgentApprovalIdempotencyRecord,
    request_hash: str,
) -> tuple[int, dict[str, object]]:
    now = utcnow_naive()
    if record.request_hash != request_hash:
        return _error_response(409, "idempotency_key_conflict")
    if (
        record.status == AgentIdempotencyStatus.in_progress
        and record.locked_until is not None
        and record.locked_until >= now
    ):
        maybe_raise_agent_fault("idempotency_existing_in_progress_hook")
        return _error_response(202, "idempotency_processing")
    if (
        record.status == AgentIdempotencyStatus.in_progress
        and record.locked_until is not None
        and record.locked_until < now
    ):
        return _resolve_stale_record(db, approval, record)
    if record.status in (
        AgentIdempotencyStatus.succeeded,
        AgentIdempotencyStatus.failed,
    ) and record.response_json is not None and record.status_code is not None:
        return record.status_code, record.response_json
    return _error_response(409, "idempotency_state_unknown", requires_reconciliation=True)


def _reject_pending_approval(
    db: Session, *, approval: AgentApproval, current_user: User
) -> bool:
    now = utcnow_naive()
    result = db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.id == approval.id,
            AgentApproval.status == AgentApprovalStatus.pending,
        )
        .values(
            status=AgentApprovalStatus.rejected,
            decided_by=current_user.id,
            decided_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        return False
    db.refresh(approval)
    return True


def _reserve_pending_approval_for_persist(
    db: Session,
    *,
    approval: AgentApproval,
    current_user: User,
    payload: dict[str, object],
    version: int,
) -> AgentApproval | None:
    now = utcnow_naive()
    status = (
        AgentApprovalStatus.edited_and_approved
        if approval.edited_payload_json is not None
        else AgentApprovalStatus.approved
    )
    result = db.execute(
        update(AgentApproval)
        .where(
            AgentApproval.id == approval.id,
            AgentApproval.status == AgentApprovalStatus.pending,
            AgentApproval.version == version,
        )
        .values(
            status=status,
            approved_payload_json=payload,
            decided_by=current_user.id,
            decided_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        return None
    db.refresh(approval)
    return approval


def _persist_approved_action(
    db: Session,
    *,
    current_user: User,
    run: AgentRun,
    approval: AgentApproval,
    record: AgentApprovalIdempotencyRecord,
    idempotency_key: str,
    version: int,
) -> tuple[int, dict[str, object]]:
    try:
        approval = get_agent_approval_authorized(db, current_user, run.id, approval.id)
        payload = approval.edited_payload_json or approval.original_payload_json
        maybe_raise_agent_fault("approval_payload_validation_failure_hook")
        try:
            _validate_payload(approval.action_type, payload)
        except HTTPException as error:
            code = str(error.detail)
            body = _error_body(code, retry_with_new_idempotency_key=False)
            _mark_record_failed(
                db,
                record,
                error.status_code,
                body,
                AgentIdempotencyFailureKind.permanent,
            )
            db.commit()
            return error.status_code, body
        get_customer_authorized(db, current_user, approval.customer_id)
        if not _record_lease_is_current(db, record):
            return _resolve_stale_record(db, approval, record)

        reserved_approval = _reserve_pending_approval_for_persist(
            db,
            approval=approval,
            current_user=current_user,
            payload=payload,
            version=version,
        )
        if reserved_approval is None:
            body = _error_body("approval_not_pending", retry_with_new_idempotency_key=False)
            _mark_record_failed(db, record, 409, body, AgentIdempotencyFailureKind.permanent)
            db.commit()
            return 409, body
        approval = reserved_approval

        business_type, business_id = _persist_business_record(
            db, approval=approval, current_user=current_user, payload=payload
        )
        maybe_raise_agent_fault("idempotency_lease_expired_while_original_process_alive_hook")
        maybe_raise_agent_fault("business_record_inserted_but_approval_update_failed_hook")
        approval.status = AgentApprovalStatus.persisted
        approval.business_record_type = business_type
        approval.business_record_id = business_id
        approval.persisted_at = utcnow_naive()
        approval.updated_at = utcnow_naive()
        db.add(
            AgentPersistedAction(
                approval_id=approval.id,
                idempotency_key=idempotency_key,
                business_record_type=business_type,
                business_record_id=business_id,
            )
        )
        body = _approval_response_body(approval, "approval_persisted")
        if not _mark_record_succeeded_conditionally(db, record, body):
            raise RuntimeError("idempotency_success_update_lost")
        maybe_raise_agent_fault("db_transaction_failure_hook")
        create_agent_event(
            db,
            run_id=run.id,
            event_type="approval_persisted",
            status=run.status.value,
            safe_message_key="completed",
            approval_id=approval.id,
        )
        try_finalize_run(db, run.id)
        db.commit()
        return 200, body
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        fresh_record = db.get(AgentApprovalIdempotencyRecord, record.id)
        fresh_approval = db.get(AgentApproval, approval.id)
        if fresh_record is None or fresh_approval is None:
            raise
        body = _error_body(
            "idempotency_state_unknown",
            retry_with_new_idempotency_key=False,
            requires_reconciliation=True,
        )
        _mark_record_failed(
            db,
            fresh_record,
            409,
            body,
            AgentIdempotencyFailureKind.unknown_after_possible_side_effect,
        )
        fresh_approval.status = AgentApprovalStatus.persist_failed
        fresh_approval.persist_error = "idempotency_state_unknown"
        fresh_approval.updated_at = utcnow_naive()
        db.commit()
        return 409, body


def _persist_business_record(
    db: Session,
    *,
    approval: AgentApproval,
    current_user: User,
    payload: dict[str, object],
) -> tuple[str, int]:
    existing = db.scalar(
        select(AgentPersistedAction).where(
            AgentPersistedAction.approval_id == approval.id
        )
    )
    if existing is not None:
        return existing.business_record_type, existing.business_record_id

    if approval.action_type == AgentActionType.task:
        task = AgentTask(
            customer_id=approval.customer_id,
            user_id=current_user.id,
            title=str(payload["title"]),
            description=str(payload.get("description", "")) or None,
            source_approval_id=approval.id,
        )
        db.add(task)
        db.flush()
        return "agent_task", task.id
    if approval.action_type == AgentActionType.memo:
        memo = AgentMemo(
            customer_id=approval.customer_id,
            user_id=current_user.id,
            title=str(payload["title"]),
            body=str(payload["body"]),
            source_approval_id=approval.id,
        )
        db.add(memo)
        db.flush()
        return "agent_memo", memo.id
    if approval.action_type == AgentActionType.email_draft:
        proposal = AgentEmailProposal(
            customer_id=approval.customer_id,
            user_id=current_user.id,
            subject=str(payload["subject"]),
            body=str(payload["body"]),
            source_approval_id=approval.id,
        )
        db.add(proposal)
        db.flush()
        return "agent_email_proposal", proposal.id
    visit = Visit(
        customer_id=approval.customer_id,
        user_id=current_user.id,
        activity_type=ActivityType.email,
        status=VisitStatus.done,
        visited_at=utcnow_naive(),
        memo=str(payload.get("description", payload.get("title", ""))),
        source_approval_id=approval.id,
    )
    db.add(visit)
    db.flush()
    return "visit", visit.id


def _resolve_stale_record(
    db: Session,
    approval: AgentApproval,
    record: AgentApprovalIdempotencyRecord,
) -> tuple[int, dict[str, object]]:
    existing = db.scalar(
        select(AgentPersistedAction).where(
            AgentPersistedAction.approval_id == approval.id
        )
    )
    if existing is not None:
        approval.status = AgentApprovalStatus.persisted
        approval.business_record_type = existing.business_record_type
        approval.business_record_id = existing.business_record_id
        approval.persisted_at = approval.persisted_at or utcnow_naive()
        body = _approval_response_body(approval, "approval_persisted")
        record.status = AgentIdempotencyStatus.succeeded
        record.response_json = body
        record.status_code = 200
        record.completed_at = utcnow_naive()
        record.updated_at = utcnow_naive()
        db.commit()
        return 200, body
    if approval.status == AgentApprovalStatus.pending:
        body = _error_body(
            "idempotency_processing_expired",
            retry_with_new_idempotency_key=True,
        )
        _mark_record_failed(
            db,
            record,
            409,
            body,
            AgentIdempotencyFailureKind.retryable_before_side_effect,
        )
        db.commit()
        return 409, body
    if approval.status in (
        AgentApprovalStatus.rejected,
        AgentApprovalStatus.expired,
        AgentApprovalStatus.cancelled,
    ):
        body = _error_body(
            "approval_not_pending",
            retry_with_new_idempotency_key=False,
        )
        _mark_record_failed(
            db,
            record,
            409,
            body,
            AgentIdempotencyFailureKind.permanent,
        )
        db.commit()
        return 409, body
    if approval.status == AgentApprovalStatus.persisted:
        body = _error_body(
            "idempotency_persist_mapping_missing",
            retry_with_new_idempotency_key=False,
            requires_reconciliation=True,
        )
        approval.persist_error = "idempotency_persist_mapping_missing"
        approval.updated_at = utcnow_naive()
        _mark_record_failed(
            db,
            record,
            409,
            body,
            AgentIdempotencyFailureKind.unknown_after_possible_side_effect,
        )
        db.commit()
        return 409, body
    body = _error_body(
        "idempotency_persist_interrupted",
        retry_with_new_idempotency_key=False,
        requires_reconciliation=True,
    )
    approval.status = AgentApprovalStatus.persist_failed
    approval.persist_error = "idempotency_persist_interrupted"
    approval.updated_at = utcnow_naive()
    _mark_record_failed(
        db,
        record,
        409,
        body,
        AgentIdempotencyFailureKind.unknown_after_possible_side_effect,
    )
    db.commit()
    return 409, body


def _validate_payload(action_type: AgentActionType, payload: dict[str, object]) -> None:
    _require_allowed_keys(action_type, payload)
    _validate_claim_ids(payload)
    if action_type in (AgentActionType.task, AgentActionType.memo):
        _require_text(payload, "title", 160)
    if action_type == AgentActionType.task:
        if "description" in payload and payload["description"] is not None:
            _require_text(payload, "description", 2000)
        return
    if action_type == AgentActionType.memo:
        _require_text(payload, "body", 5000)
        return
    if action_type == AgentActionType.email_draft:
        _require_text(payload, "subject", 200)
        _require_text(payload, "body", 5000)
        return
    _require_text(payload, "description", 2000)


def _require_allowed_keys(
    action_type: AgentActionType, payload: dict[str, object]
) -> None:
    allowed_keys = ALLOWED_APPROVAL_PAYLOAD_KEYS[action_type]
    if set(payload) - allowed_keys:
        raise HTTPException(status_code=422, detail="invalid_payload_keys")


def _validate_claim_ids(payload: dict[str, object]) -> None:
    value = payload.get("claim_ids")
    if value is None:
        return
    if not isinstance(value, list) or len(value) > MAX_APPROVAL_CLAIM_IDS:
        raise HTTPException(status_code=422, detail="invalid_claim_ids")
    for claim_id in value:
        if (
            not isinstance(claim_id, str)
            or claim_id.strip() == ""
            or len(claim_id) > MAX_APPROVAL_CLAIM_ID_LENGTH
        ):
            raise HTTPException(status_code=422, detail="invalid_claim_ids")


def _require_text(payload: dict[str, object], key: str, max_length: int) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or value.strip() == "" or len(value) > max_length:
        raise HTTPException(status_code=422, detail=f"invalid_{key}")


def _ensure_run_allows_approval(run: AgentRun) -> None:
    if run.status != AgentRunStatus.waiting_for_approval:
        raise HTTPException(status_code=409, detail="run_not_waiting_for_approval")


def _ensure_run_sources_allow_approval(
    db: Session, *, current_user: User, run: AgentRun
) -> None:
    if not run_sources_all_authorized(db, run=run, current_user=current_user):
        raise HTTPException(status_code=404, detail="Not Found")


def _expire_if_needed(db: Session, approval: AgentApproval) -> bool:
    if approval.expires_at is None or approval.expires_at >= utcnow_naive():
        return False
    if approval.status == AgentApprovalStatus.pending:
        approval.status = AgentApprovalStatus.expired
        approval.updated_at = utcnow_naive()
        db.flush()
    return True


def _record_lease_is_current(
    db: Session, record: AgentApprovalIdempotencyRecord
) -> bool:
    if record.lease_token is None:
        return False
    now = utcnow_naive()
    result = db.execute(
        update(AgentApprovalIdempotencyRecord)
        .where(
            AgentApprovalIdempotencyRecord.id == record.id,
            AgentApprovalIdempotencyRecord.status == AgentIdempotencyStatus.in_progress,
            AgentApprovalIdempotencyRecord.lease_token == record.lease_token,
            AgentApprovalIdempotencyRecord.locked_until.is_not(None),
            AgentApprovalIdempotencyRecord.locked_until >= now,
        )
        .values(updated_at=now)
    )
    return result_rowcount(result) == 1


def _mark_record_succeeded_conditionally(
    db: Session,
    record: AgentApprovalIdempotencyRecord,
    body: dict[str, object],
) -> bool:
    if record.lease_token is None:
        return False
    now = utcnow_naive()
    result = db.execute(
        update(AgentApprovalIdempotencyRecord)
        .where(
            AgentApprovalIdempotencyRecord.id == record.id,
            AgentApprovalIdempotencyRecord.status == AgentIdempotencyStatus.in_progress,
            AgentApprovalIdempotencyRecord.lease_token == record.lease_token,
            AgentApprovalIdempotencyRecord.locked_until.is_not(None),
            AgentApprovalIdempotencyRecord.locked_until >= now,
        )
        .values(
            status=AgentIdempotencyStatus.succeeded,
            response_json=body,
            status_code=200,
            completed_at=now,
            updated_at=now,
        )
    )
    return result_rowcount(result) == 1


def _mark_record_failed(
    db: Session,
    record: AgentApprovalIdempotencyRecord,
    status_code: int,
    body: dict[str, object],
    failure_kind: AgentIdempotencyFailureKind,
) -> None:
    record.status = AgentIdempotencyStatus.failed
    record.response_json = body
    record.status_code = status_code
    error_value = body.get("error")
    if isinstance(error_value, dict):
        code_value = error_value.get("code")
        record.error_code = code_value if isinstance(code_value, str) else None
    else:
        record.error_code = None
    record.failure_kind = failure_kind
    record.completed_at = utcnow_naive()
    record.updated_at = utcnow_naive()
    db.flush()


def expire_pending_approvals(db: Session) -> int:
    now = utcnow_naive()
    approvals = list(
        db.execute(
            select(AgentApproval.id, AgentApproval.run_id).where(
                AgentApproval.status == AgentApprovalStatus.pending,
                AgentApproval.expires_at.is_not(None),
                AgentApproval.expires_at < now,
            )
        ).all()
    )
    expired_count = 0
    for approval in approvals:
        result = db.execute(
            update(AgentApproval)
            .where(
                AgentApproval.id == approval.id,
                AgentApproval.status == AgentApprovalStatus.pending,
            )
            .values(status=AgentApprovalStatus.expired, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result_rowcount(result) == 1:
            expired_count += 1
            try_finalize_run(db, approval.run_id)
    return expired_count


def reap_stale_idempotency_records(db: Session) -> int:
    now = utcnow_naive()
    records = list(
        db.scalars(
            select(AgentApprovalIdempotencyRecord).where(
                AgentApprovalIdempotencyRecord.status
                == AgentIdempotencyStatus.in_progress,
                AgentApprovalIdempotencyRecord.locked_until.is_not(None),
                AgentApprovalIdempotencyRecord.locked_until < now,
            )
        ).all()
    )
    for record in records:
        approval = db.get(AgentApproval, record.approval_id)
        if approval is None:
            body = _error_body(
                "approval_not_found",
                retry_with_new_idempotency_key=False,
                requires_reconciliation=True,
            )
            _mark_record_failed(
                db,
                record,
                409,
                body,
                AgentIdempotencyFailureKind.unknown_after_possible_side_effect,
            )
            continue
        db.refresh(approval)
        _resolve_stale_record(db, approval, record)
    return len(records)


def _approval_response_body(approval: AgentApproval, message_key: str) -> dict[str, object]:
    return {
        "approval": {
            "id": approval.id,
            "run_id": approval.run_id,
            "customer_id": approval.customer_id,
            "version": approval.version,
            "action_type": approval.action_type.value,
            "business_record_type": approval.business_record_type,
            "business_record_id": approval.business_record_id,
            "status": approval.status.value,
        },
        "status_code": 200,
        "message_key": message_key,
        "retry_with_new_idempotency_key": False,
        "requires_reconciliation": False,
    }


def _error_response(
    status_code: int,
    code: str,
    *,
    retry_with_new_idempotency_key: bool = False,
    requires_reconciliation: bool = False,
) -> tuple[int, dict[str, object]]:
    return status_code, _error_body(
        code,
        retry_with_new_idempotency_key=retry_with_new_idempotency_key,
        requires_reconciliation=requires_reconciliation,
    )


def _error_body(
    code: str,
    *,
    retry_with_new_idempotency_key: bool,
    requires_reconciliation: bool = False,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message_key": code,
            "retry_with_new_idempotency_key": retry_with_new_idempotency_key,
            "requires_reconciliation": requires_reconciliation,
        }
    }
