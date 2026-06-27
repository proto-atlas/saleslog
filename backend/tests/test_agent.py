import json
import shutil
import subprocess
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.approval import (
    IDEMPOTENCY_LOCK_TTL_SECONDS,
    _cancel_active_run,
    approve_agent_approval,
    cancel_agent_run,
    edit_agent_approval,
    reap_stale_idempotency_records,
)
from app.agent.events import create_agent_event
from app.agent.llm import (
    ANTHROPIC_OUTPUT_TOOL_NAME,
    POWERSHELL_POST_JSON_SCRIPT,
    AnthropicProvider,
    LLMProviderError,
    MockLLMProvider,
    OpenAIProvider,
    _anthropic_request_body,
    _extract_anthropic_tool_input,
    _openai_request_body,
    _post_json_with_powershell,
    _post_json,
    _system_prompt,
    select_llm_provider,
)
from app.agent.output_schema import (
    MAX_AGENT_OUTPUT_CLAIM_IDS,
    MAX_AGENT_OUTPUT_LIST_ITEMS,
    AgentLLMOutput,
)
from app.agent.search import build_fts5_phrase_query, search_knowledge_base
from app.agent.text import sha256_text, stable_json_hash
from app.settings import (
    DEFAULT_ANTHROPIC_MODEL,
    AgentLLMConfigError,
    AgentLLMSettings,
    get_agent_llm_settings,
)
from app.agent.worker import (
    AgentRunCancelled,
    AgentRunNoLongerActive,
    _finish_run_if_active,
    _mark_run_running_if_not_cancelled,
    _raise_if_cancelled,
    process_agent_run_in_session,
)
from app.agent.worker_queue import claim_next_pending_run, reap_stale_agent_runs
from app.db import SessionLocal
from app.deps import get_current_user
from app.enums import (
    AgentActionType,
    AgentApprovalStatus,
    AgentIdempotencyStatus,
    AgentRunStatus,
    AgentWorkflowType,
    KnowledgeVisibility,
)
from app.main import app
from app.models import (
    AgentApproval,
    AgentApprovalIdempotencyRecord,
    AgentArtifact,
    AgentEvent,
    AgentEventCursor,
    AgentRun,
    AgentRunSource,
    AgentTask,
    KnowledgeChunk,
    KnowledgeDoc,
    User,
    utcnow_naive,
)
from app.schemas import (
    AGENT_APPROVAL_PATCH_MAX_ARRAY_ITEMS,
    AGENT_APPROVAL_PATCH_MAX_BYTES,
    AGENT_APPROVAL_PATCH_MAX_OBJECT_KEYS,
    AGENT_APPROVAL_PATCH_MAX_STRING_LENGTH,
    AgentApprovalPatch,
)


def _create_agent_run(client: TestClient, customer_id: int) -> int:
    res = client.post(
        f"/api/customers/{customer_id}/agent-runs",
        json={"objective": "契約条件の確認", "workflow_type": "meeting_prep"},
    )
    assert res.status_code == 202
    return int(res.json()["run_id"])


def _objective_hash(customer_id: int, objective: str) -> str:
    return stable_json_hash(
        {
            "customer_id": customer_id,
            "workflow_type": AgentWorkflowType.meeting_prep.value,
            "objective": objective,
        }
    )


def _ensure_processed(db_session: Session, run_id: int) -> AgentApproval:
    process_agent_run_in_session(db_session, run_id)
    approval = db_session.scalar(
        select(AgentApproval)
        .where(AgentApproval.run_id == run_id)
        .order_by(AgentApproval.id)
    )
    assert approval is not None
    return approval


def test_worker_cancel_check_reads_database_status(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="キャンセル競合顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="cancel race",
        objective_hash=_objective_hash(customer.id, "cancel race"),
        status=AgentRunStatus.pending,
    )
    db_session.add(run)
    db_session.commit()

    worker_session = SessionLocal()
    cancel_session = SessionLocal()
    try:
        stale_run = worker_session.get(AgentRun, run.id)
        cancelled_run = cancel_session.get(AgentRun, run.id)
        assert stale_run is not None
        assert cancelled_run is not None
        cancelled_run.status = AgentRunStatus.cancelled
        cancel_session.commit()

        with pytest.raises(AgentRunCancelled):
            _raise_if_cancelled(worker_session, stale_run)
        with pytest.raises(AgentRunCancelled):
            _mark_run_running_if_not_cancelled(
                worker_session,
                run=stale_run,
                provider=MockLLMProvider(),
                worker_id="test-worker",
                started_at=utcnow_naive(),
            )
    finally:
        worker_session.close()
        cancel_session.close()


def test_worker_stops_when_database_status_is_failed(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="timeout競合顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="timeout race",
        objective_hash=_objective_hash(customer.id, "timeout race"),
        status=AgentRunStatus.running,
    )
    db_session.add(run)
    db_session.commit()

    worker_session = SessionLocal()
    reap_session = SessionLocal()
    try:
        stale_run = worker_session.get(AgentRun, run.id)
        failed_run = reap_session.get(AgentRun, run.id)
        assert stale_run is not None
        assert failed_run is not None
        failed_run.status = AgentRunStatus.failed
        failed_run.last_error_code = "agent_worker_heartbeat_timeout"
        reap_session.commit()

        with pytest.raises(AgentRunNoLongerActive):
            _raise_if_cancelled(worker_session, stale_run)
        with pytest.raises(AgentRunNoLongerActive):
            _mark_run_running_if_not_cancelled(
                worker_session,
                run=stale_run,
                provider=MockLLMProvider(),
                worker_id="test-worker",
                started_at=utcnow_naive(),
            )
    finally:
        worker_session.close()
        reap_session.close()

    db_session.refresh(run)
    assert run.status == AgentRunStatus.failed
    assert run.last_error_code == "agent_worker_heartbeat_timeout"


def test_worker_does_not_take_running_run_locked_by_other_worker(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="worker所有者競合顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="locked by another worker",
        objective_hash=_objective_hash(customer.id, "locked by another worker"),
        status=AgentRunStatus.running,
        locked_by="worker-a",
        locked_until=utcnow_naive() + timedelta(seconds=60),
    )
    db_session.add(run)
    db_session.commit()

    with pytest.raises(AgentRunNoLongerActive):
        _mark_run_running_if_not_cancelled(
            db_session,
            run=run,
            provider=MockLLMProvider(),
            worker_id="worker-b",
            started_at=utcnow_naive(),
        )

    db_session.refresh(run)
    assert run.status == AgentRunStatus.running
    assert run.locked_by == "worker-a"


def test_worker_does_not_hold_transaction_during_llm_call(
    monkeypatch, db_session: Session, customer_factory
):
    customer = customer_factory(name="LLM中キャンセル顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="cancel during llm",
        objective_hash=_objective_hash(customer.id, "cancel during llm"),
        status=AgentRunStatus.pending,
    )
    db_session.add(run)
    db_session.commit()

    class CancelDuringGenerateProvider(MockLLMProvider):
        def generate(self, **kwargs: object):
            with SessionLocal() as cancel_session:
                cancelling_run = cancel_session.get(AgentRun, run.id)
                assert cancelling_run is not None
                cancelling_run.status = AgentRunStatus.cancelled
                cancelling_run.completed_at = utcnow_naive()
                cancelling_run.locked_by = None
                cancelling_run.locked_until = None
                cancel_session.commit()
            return super().generate(**kwargs)

    monkeypatch.setattr(
        "app.agent.worker.select_llm_provider",
        lambda: CancelDuringGenerateProvider(),
    )

    process_agent_run_in_session(db_session, run.id)

    db_session.refresh(run)
    assert run.status == AgentRunStatus.cancelled
    assert run.last_error_code is None
    assert db_session.scalar(
        select(func.count()).select_from(AgentArtifact).where(AgentArtifact.run_id == run.id)
    ) == 0


def test_worker_provider_error_does_not_overwrite_cancelled_run(
    monkeypatch, db_session: Session, customer_factory
):
    customer = customer_factory(name="失敗中キャンセル顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="cancel before provider error",
        objective_hash=_objective_hash(customer.id, "cancel before provider error"),
        status=AgentRunStatus.pending,
    )
    db_session.add(run)
    db_session.commit()

    class CancelThenFailProvider(MockLLMProvider):
        def generate(self, **_kwargs: object):
            with SessionLocal() as cancel_session:
                cancelling_run = cancel_session.get(AgentRun, run.id)
                assert cancelling_run is not None
                cancelling_run.status = AgentRunStatus.cancelled
                cancelling_run.completed_at = utcnow_naive()
                cancelling_run.locked_by = None
                cancelling_run.locked_until = None
                cancel_session.commit()
            raise LLMProviderError("llm_auth_failed")

    monkeypatch.setattr(
        "app.agent.worker.select_llm_provider",
        lambda: CancelThenFailProvider(),
    )

    process_agent_run_in_session(db_session, run.id)

    db_session.refresh(run)
    assert run.status == AgentRunStatus.cancelled
    assert run.last_error_code is None


def test_worker_finish_does_not_overwrite_cancelled_run(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="完了直前キャンセル顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="finish cancelled",
        objective_hash=_objective_hash(customer.id, "finish cancelled"),
        status=AgentRunStatus.running,
    )
    db_session.add(run)
    db_session.commit()

    worker_session = SessionLocal()
    cancel_session = SessionLocal()
    try:
        stale_run = worker_session.get(AgentRun, run.id)
        cancelling_run = cancel_session.get(AgentRun, run.id)
        assert stale_run is not None
        assert cancelling_run is not None
        cancelling_run.status = AgentRunStatus.cancelled
        cancelling_run.completed_at = utcnow_naive()
        cancel_session.commit()

        with pytest.raises(AgentRunCancelled):
            _finish_run_if_active(
                worker_session,
                run=stale_run,
                status=AgentRunStatus.completed,
                latency_ms=1,
                completed_at=utcnow_naive(),
            )
    finally:
        worker_session.close()
        cancel_session.close()

    db_session.refresh(run)
    assert run.status == AgentRunStatus.cancelled


def test_cancel_agent_run_does_not_update_terminal_run(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="キャンセル済み防止顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="already completed",
        objective_hash=_objective_hash(customer.id, "already completed"),
        status=AgentRunStatus.completed,
        completed_at=utcnow_naive(),
    )
    db_session.add(run)
    db_session.commit()
    current_user = db_session.get(User, 1)
    assert current_user is not None

    with pytest.raises(HTTPException) as error:
        cancel_agent_run(db_session, current_user=current_user, run_id=run.id)

    assert error.value.status_code == 409
    assert not _cancel_active_run(db_session, run_id=run.id, now=utcnow_naive())
    db_session.refresh(run)
    assert run.status == AgentRunStatus.completed


def test_cancel_agent_run_does_not_hide_persist_failed_approval(
    db_session: Session, client: TestClient, customer_factory
):
    customer = customer_factory(name="照合中キャンセル顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    approval.status = AgentApprovalStatus.persist_failed
    approval.persist_error = "idempotency_state_unknown"
    db_session.commit()
    current_user = db_session.get(User, 1)
    assert current_user is not None

    with pytest.raises(HTTPException) as error:
        cancel_agent_run(db_session, current_user=current_user, run_id=run_id)

    db_session.refresh(approval)
    run = db_session.get(AgentRun, run_id)
    assert error.value.status_code == 409
    assert error.value.detail == "approval_reconciliation_required"
    assert approval.status == AgentApprovalStatus.persist_failed
    assert run is not None
    assert run.status == AgentRunStatus.waiting_for_approval


def test_agent_event_seq_uses_database_reserved_sequence(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="イベント採番顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="event seq",
        objective_hash=_objective_hash(customer.id, "event seq"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add(run)
    db_session.commit()
    create_agent_event(
        db_session,
        run_id=run.id,
        event_type="completed",
        status=run.status.value,
        safe_message_key="completed",
    )
    db_session.commit()

    session_a = SessionLocal()
    session_b = SessionLocal()
    try:
        assert session_a.get(AgentEventCursor, run.id) is not None
        assert session_b.get(AgentEventCursor, run.id) is not None
        create_agent_event(
            session_a,
            run_id=run.id,
            event_type="completed",
            status=run.status.value,
            safe_message_key="completed",
        )
        session_a.commit()
        create_agent_event(
            session_b,
            run_id=run.id,
            event_type="completed",
            status=run.status.value,
            safe_message_key="completed",
        )
        session_b.commit()
    finally:
        session_a.close()
        session_b.close()

    event_seqs = list(
        db_session.scalars(
            select(AgentEvent.event_seq)
            .where(AgentEvent.run_id == run.id)
            .order_by(AgentEvent.event_seq)
        ).all()
    )
    assert event_seqs == [1, 2, 3]


def test_agent_llm_output_limits_top_level_lists(customer_factory):
    customer = customer_factory(name="LLM件数上限顧客")
    output = MockLLMProvider().generate(
        customer=customer,
        visits=[],
        knowledge_results=[],
    ).model_dump()
    output["risks"] = output["risks"] * (MAX_AGENT_OUTPUT_LIST_ITEMS + 1)

    with pytest.raises(ValidationError):
        AgentLLMOutput.model_validate(output)


def test_agent_llm_output_limits_claim_ids(customer_factory):
    customer = customer_factory(name="claim件数上限顧客")
    output = MockLLMProvider().generate(
        customer=customer,
        visits=[],
        knowledge_results=[],
    ).model_dump()
    output["customer_summary"]["claim_ids"] = [
        "claim_001"
    ] * (MAX_AGENT_OUTPUT_CLAIM_IDS + 1)

    with pytest.raises(ValidationError):
        AgentLLMOutput.model_validate(output)


def _create_acl_changed_approval_run(
    db_session: Session,
    customer_factory,
) -> tuple[AgentRun, AgentApproval, User]:
    customer = customer_factory(name="ACL変更approval顧客", owner_id=2)
    sales = db_session.get(User, 2)
    assert sales is not None
    doc = KnowledgeDoc(
        title="限定承認メモ",
        source_type="sales_playbook",
        body="private approval detail",
        checksum=sha256_text("private approval detail"),
        doc_version="v1",
        visibility=KnowledgeVisibility.private,
        owner_user_id=2,
        source_acl_hash="sha256:test",
        created_by=1,
    )
    run = AgentRun(
        user_id=2,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="private approval",
        objective_hash=_objective_hash(customer.id, "private approval"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add_all([doc, run])
    db_session.flush()
    approval = AgentApproval(
        run_id=run.id,
        customer_id=customer.id,
        action_type=AgentActionType.email_draft,
        target_entity_type="customer",
        target_entity_id=customer.id,
        original_payload_json={
            "subject": "限定承認情報",
            "body": "private approval detail",
            "claim_ids": ["claim_001"],
        },
        payload_schema_version="email_draft_v1",
        status=AgentApprovalStatus.pending,
    )
    db_session.add_all(
        [
            AgentRunSource(
                run_id=run.id,
                source_type=doc.source_type,
                source_id=str(doc.id),
                source_version=doc.doc_version,
                source_checksum=doc.checksum,
                label=doc.title,
                char_start=0,
                char_end=23,
                source_excerpt="private approval detail",
                source_excerpt_hash=sha256_text("private approval detail"),
            ),
            approval,
        ]
    )
    doc.owner_user_id = 3
    db_session.commit()
    return run, approval, sales


def test_agent_run_creates_artifact_approval_and_safe_events(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="Agent顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)

    run = db_session.get(AgentRun, run_id)
    assert run is not None
    assert run.status == AgentRunStatus.waiting_for_approval
    assert approval.status == AgentApprovalStatus.pending
    assert approval.original_payload_json["claim_ids"] == ["claim_001"]

    artifact_count = db_session.scalar(
        select(func.count()).select_from(AgentArtifact).where(AgentArtifact.run_id == run_id)
    )
    approval_count = db_session.scalar(
        select(func.count()).select_from(AgentApproval).where(AgentApproval.run_id == run_id)
    )
    event_keys = [
        event.safe_message_key
        for event in db_session.scalars(
            select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.event_seq)
        )
    ]
    assert artifact_count == 1
    assert approval_count == 3
    assert event_keys == [
        "run_created",
        "customer_loaded",
        "activities_loaded",
        "knowledge_search_completed",
        "drafting_completed",
        "citation_verified",
        "approval_required",
        "waiting_for_approval",
    ]


def test_stale_pending_worker_lock_is_released_for_retry(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="queue復旧顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="契約条件の確認",
        objective_hash=_objective_hash(customer.id, "契約条件の確認"),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    assert claim_next_pending_run(db_session, owner="worker-a") == run.id
    db_session.refresh(run)
    assert run.status == AgentRunStatus.pending
    assert run.locked_by == "worker-a"

    run.locked_until = utcnow_naive() - timedelta(seconds=1)
    db_session.commit()

    assert reap_stale_agent_runs(db_session, owner="worker-b") == 1
    db_session.refresh(run)
    assert run.status == AgentRunStatus.pending
    assert run.locked_by is None
    assert run.locked_until is None
    assert claim_next_pending_run(db_session, owner="worker-b") == run.id


def test_stale_running_worker_timeout_creates_failed_event(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="timeoutイベント顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="timeout event",
        objective_hash=_objective_hash(customer.id, "timeout event"),
        status=AgentRunStatus.running,
        locked_by="worker-a",
        locked_until=utcnow_naive() - timedelta(seconds=1),
    )
    db_session.add(run)
    db_session.commit()

    assert reap_stale_agent_runs(db_session, owner="worker-b") == 1
    db_session.refresh(run)
    event = db_session.scalar(
        select(AgentEvent)
        .where(AgentEvent.run_id == run.id)
        .order_by(AgentEvent.event_seq.desc())
        .limit(1)
    )

    assert run.status == AgentRunStatus.failed
    assert run.last_error_code == "agent_worker_heartbeat_timeout"
    assert event is not None
    assert event.event_seq == 1
    assert event.event_type == "failed"
    assert event.safe_message_params_json == {
        "error_code": "agent_worker_heartbeat_timeout"
    }


def test_claim_next_pending_run_skips_locked_pending_runs(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="queue順序顧客")
    locked_run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="先頭のロック中run",
        objective_hash=_objective_hash(customer.id, "先頭のロック中run"),
        locked_by="worker-a",
        locked_until=utcnow_naive() + timedelta(seconds=60),
    )
    retry_run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="後続の未ロックrun",
        objective_hash=_objective_hash(customer.id, "後続の未ロックrun"),
    )
    db_session.add_all([locked_run, retry_run])
    db_session.commit()
    db_session.refresh(retry_run)

    assert claim_next_pending_run(db_session, owner="worker-b") == retry_run.id


def test_sales_other_user_agent_run_is_404(
    client: TestClient, db_session: Session, base_users: list[User], customer_factory
):
    customer = customer_factory(name="他担当", owner_id=3)
    run_id = _create_agent_run(client, customer.id)
    sales = db_session.get(User, 2)
    assert sales is not None
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        res = client.get(f"/api/agent-runs/{run_id}")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_duplicate_active_agent_run_returns_existing_run(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="重複run顧客")
    objective = "契約条件の確認"
    existing = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective=objective,
        objective_hash=_objective_hash(customer.id, objective),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    response = client.post(
        f"/api/customers/{customer.id}/agent-runs",
        json={"objective": objective, "workflow_type": "meeting_prep"},
    )

    run_count = db_session.scalar(select(func.count()).select_from(AgentRun))
    assert response.status_code == 202
    assert response.json() == {
        "run_id": existing.id,
        "status": "waiting_for_approval",
        "reused": True,
    }
    assert run_count == 1


def test_list_customer_agent_runs_returns_recent_runs(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="履歴run顧客")
    other_customer = customer_factory(name="別顧客")
    first = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="初回",
        objective_hash=_objective_hash(customer.id, "初回"),
        status=AgentRunStatus.completed,
    )
    second = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.follow_up,
        objective="二回目",
        objective_hash=_objective_hash(customer.id, "二回目"),
        status=AgentRunStatus.waiting_for_approval,
    )
    other = AgentRun(
        user_id=1,
        customer_id=other_customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="別顧客",
        objective_hash=_objective_hash(other_customer.id, "別顧客"),
        status=AgentRunStatus.completed,
    )
    db_session.add_all([first, second, other])
    db_session.commit()

    response = client.get(f"/api/customers/{customer.id}/agent-runs")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [second.id, first.id]
    assert all(item["customer_id"] == customer.id for item in body)


def test_list_customer_agent_runs_sales_sees_own_runs(
    client: TestClient, db_session: Session, customer_factory, base_users: list[User]
):
    sales = base_users[1]
    customer = customer_factory(name="sales履歴run顧客", owner_id=sales.id)
    own_run = AgentRun(
        user_id=sales.id,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="自分のrun",
        objective_hash=_objective_hash(customer.id, "自分のrun"),
        status=AgentRunStatus.completed,
    )
    manager_run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="manager run",
        objective_hash=_objective_hash(customer.id, "manager run"),
        status=AgentRunStatus.completed,
    )
    db_session.add_all([own_run, manager_run])
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.get(f"/api/customers/{customer.id}/agent-runs")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [own_run.id]


def test_agent_run_active_limit_returns_429(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="上限run顧客")
    for index in range(5):
        objective = f"上限確認 {index}"
        db_session.add(
            AgentRun(
                user_id=1,
                customer_id=customer.id,
                workflow_type=AgentWorkflowType.meeting_prep,
                objective=objective,
                objective_hash=_objective_hash(customer.id, objective),
                status=AgentRunStatus.waiting_for_approval,
            )
        )
    db_session.commit()

    response = client.post(
        f"/api/customers/{customer.id}/agent-runs",
        json={"objective": "新しい目的", "workflow_type": "meeting_prep"},
    )

    run_count = db_session.scalar(select(func.count()).select_from(AgentRun))
    assert response.status_code == 429
    assert response.json() == {"detail": "agent_run_limit_exceeded"}
    assert run_count == 5


def test_agent_run_assigns_active_slots(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="slot割り当て顧客")

    first = client.post(
        f"/api/customers/{customer.id}/agent-runs",
        json={"objective": "slot 1", "workflow_type": "meeting_prep"},
    )
    second = client.post(
        f"/api/customers/{customer.id}/agent-runs",
        json={"objective": "slot 2", "workflow_type": "meeting_prep"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    slots = list(
        db_session.scalars(
            select(AgentRun.active_slot)
            .where(AgentRun.user_id == 1)
            .order_by(AgentRun.active_slot)
        )
    )
    assert slots == [1, 2]


def test_active_agent_run_同一目的はDB制約で重複作成できない(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="active重複顧客")
    objective = "同じ目的"
    objective_hash = _objective_hash(customer.id, objective)
    db_session.add(
        AgentRun(
            user_id=1,
            customer_id=customer.id,
            workflow_type=AgentWorkflowType.meeting_prep,
            objective=objective,
            objective_hash=objective_hash,
            status=AgentRunStatus.pending,
        )
    )
    db_session.commit()

    db_session.add(
        AgentRun(
            user_id=1,
            customer_id=customer.id,
            workflow_type=AgentWorkflowType.meeting_prep,
            objective=objective,
            objective_hash=objective_hash,
            status=AgentRunStatus.running,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_active_agent_run_同一slotはDB制約で重複作成できない(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="slot重複顧客")
    db_session.add_all(
        [
            AgentRun(
                user_id=1,
                customer_id=customer.id,
                workflow_type=AgentWorkflowType.meeting_prep,
                objective="slot A",
                objective_hash="slot-a",
                active_slot=1,
                status=AgentRunStatus.pending,
            ),
            AgentRun(
                user_id=1,
                customer_id=customer.id,
                workflow_type=AgentWorkflowType.meeting_prep,
                objective="slot B",
                objective_hash="slot-b",
                active_slot=1,
                status=AgentRunStatus.running,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_completed_agent_run_同一目的はDB制約で再作成できる(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="completed再作成顧客")
    objective = "同じ目的"
    objective_hash = _objective_hash(customer.id, objective)
    db_session.add_all(
        [
            AgentRun(
                user_id=1,
                customer_id=customer.id,
                workflow_type=AgentWorkflowType.meeting_prep,
                objective=objective,
                objective_hash=objective_hash,
                status=AgentRunStatus.completed,
            ),
            AgentRun(
                user_id=1,
                customer_id=customer.id,
                workflow_type=AgentWorkflowType.meeting_prep,
                objective=objective,
                objective_hash=objective_hash,
                status=AgentRunStatus.pending,
            ),
        ]
    )
    db_session.commit()

    run_count = db_session.scalar(select(func.count()).select_from(AgentRun))
    assert run_count == 2


def test_agent_sources_redact_expired_excerpt_on_read(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="期限切れsource顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="根拠確認",
        objective_hash=_objective_hash(customer.id, "根拠確認"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add(run)
    db_session.flush()
    source = AgentRunSource(
        run_id=run.id,
        source_type="customer",
        source_id=str(customer.id),
        source_version="v1",
        source_checksum=sha256_text("期限切れ本文"),
        label="顧客",
        char_start=0,
        char_end=5,
        source_excerpt="期限切れ本文",
        source_excerpt_hash=sha256_text("期限切れ本文"),
        expires_at=utcnow_naive() - timedelta(seconds=1),
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    response = client.get(f"/api/agent-runs/{run.id}/sources")

    db_session.refresh(source)
    assert response.status_code == 200
    assert response.json()[0]["source_excerpt"] is None
    assert source.source_excerpt is None
    assert source.source_excerpt_redacted_at is not None


def test_agent_sources_hide_private_knowledge_after_acl_change(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    customer = customer_factory(name="ACL変更source顧客", owner_id=2)
    sales = db_session.get(User, 2)
    assert sales is not None
    doc = KnowledgeDoc(
        title="限定メモ",
        source_type="sales_playbook",
        body="private renewal detail",
        checksum=sha256_text("private renewal detail"),
        doc_version="v1",
        visibility=KnowledgeVisibility.private,
        owner_user_id=2,
        source_acl_hash="sha256:test",
        created_by=1,
    )
    run = AgentRun(
        user_id=2,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="private renewal",
        objective_hash=_objective_hash(customer.id, "private renewal"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add_all([doc, run])
    db_session.flush()
    db_session.add(
        AgentRunSource(
            run_id=run.id,
            source_type=doc.source_type,
            source_id=str(doc.id),
            source_version=doc.doc_version,
            source_checksum=doc.checksum,
            label=doc.title,
            char_start=0,
            char_end=22,
            source_excerpt="private renewal detail",
            source_excerpt_hash=sha256_text("private renewal detail"),
        )
    )
    doc.owner_user_id = 3
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.get(f"/api/agent-runs/{run.id}/sources")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == []


def test_agent_artifacts_hide_when_source_acl_changed(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    customer = customer_factory(name="ACL変更artifact顧客", owner_id=2)
    sales = db_session.get(User, 2)
    assert sales is not None
    doc = KnowledgeDoc(
        title="限定メモ",
        source_type="sales_playbook",
        body="private artifact detail",
        checksum=sha256_text("private artifact detail"),
        doc_version="v1",
        visibility=KnowledgeVisibility.private,
        owner_user_id=2,
        source_acl_hash="sha256:test",
        created_by=1,
    )
    run = AgentRun(
        user_id=2,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="private artifact",
        objective_hash=_objective_hash(customer.id, "private artifact"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add_all([doc, run])
    db_session.flush()
    db_session.add_all(
        [
            AgentRunSource(
                run_id=run.id,
                source_type=doc.source_type,
                source_id=str(doc.id),
                source_version=doc.doc_version,
                source_checksum=doc.checksum,
                label=doc.title,
                char_start=0,
                char_end=23,
                source_excerpt="private artifact detail",
                source_excerpt_hash=sha256_text("private artifact detail"),
            ),
            AgentArtifact(
                run_id=run.id,
                artifact_type="agent_output",
                content_json={"customer_summary": {"text": "private artifact detail"}},
                claims_json=[],
                citation_candidates_json=[],
                citations_json=[],
                uncertainties_json=[],
            ),
        ]
    )
    doc.owner_user_id = 3
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.get(f"/api/agent-runs/{run.id}/artifacts")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == []


def test_agent_approvals_hide_when_source_acl_changed(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    run, _, sales = _create_acl_changed_approval_run(db_session, customer_factory)

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.get(f"/api/agent-runs/{run.id}/approvals")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == []
    assert "private approval detail" not in response.text


def test_agent_approval_edit_is_404_when_source_acl_changed(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    run, approval, sales = _create_acl_changed_approval_run(db_session, customer_factory)

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.patch(
            f"/api/agent-runs/{run.id}/approvals/{approval.id}",
            json={
                "version": approval.version,
                "edited_payload_json": {
                    "subject": "編集後",
                    "body": "編集後本文",
                    "claim_ids": ["claim_001"],
                }
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    db_session.refresh(approval)
    assert response.status_code == 404
    assert approval.edited_payload_json is None
    assert approval.version == 1


def test_agent_approval_approve_is_404_when_source_acl_changed(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    run, approval, sales = _create_acl_changed_approval_run(db_session, customer_factory)

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.post(
            f"/api/agent-runs/{run.id}/approvals/{approval.id}/approve",
            json={"idempotency_key": "idem-acl-denied-001", "version": approval.version},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    db_session.refresh(approval)
    record_count = db_session.scalar(
        select(func.count()).select_from(AgentApprovalIdempotencyRecord)
    )
    assert response.status_code == 404
    assert approval.status == AgentApprovalStatus.pending
    assert record_count == 0


def test_agent_approval_reject_is_404_when_source_acl_changed(
    client: TestClient,
    db_session: Session,
    base_users: list[User],
    customer_factory,
):
    run, approval, sales = _create_acl_changed_approval_run(db_session, customer_factory)

    app.dependency_overrides[get_current_user] = lambda: sales
    try:
        response = client.post(f"/api/agent-runs/{run.id}/approvals/{approval.id}/reject")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    db_session.refresh(approval)
    assert response.status_code == 404
    assert approval.status == AgentApprovalStatus.pending


def test_agent_artifacts_redact_citation_candidate_quotes(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="quote除去artifact顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="quote redaction",
        objective_hash=_objective_hash(customer.id, "quote redaction"),
        status=AgentRunStatus.waiting_for_approval,
    )
    db_session.add(run)
    db_session.flush()
    candidate = {
        "candidate_id": "cand_001",
        "source_type": "customer",
        "source_id": str(customer.id),
        "quoted_text": "返してはいけない本文",
    }
    db_session.add_all(
        [
            AgentRunSource(
                run_id=run.id,
                source_type="customer",
                source_id=str(customer.id),
                source_version="v1",
                source_checksum=sha256_text("顧客本文"),
                label="顧客",
                char_start=0,
                char_end=4,
                source_excerpt="顧客本文",
                source_excerpt_hash=sha256_text("顧客本文"),
            ),
            AgentArtifact(
                run_id=run.id,
                artifact_type="agent_output",
                content_json={"citation_candidates": [candidate]},
                claims_json=[],
                citation_candidates_json=[candidate],
                citations_json=[],
                uncertainties_json=[],
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/agent-runs/{run.id}/artifacts")

    body = response.json()
    assert response.status_code == 200
    assert "quoted_text" not in body[0]["citation_candidates_json"][0]
    assert "quoted_text" not in body[0]["content_json"]["citation_candidates"][0]


def test_approve_same_idempotency_key_returns_same_response_without_duplicate_task(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="承認顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    body = {"idempotency_key": "idem-approve-001", "version": approval.version}

    first = client.post(f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve", json=body)
    second = client.post(f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve", json=body)

    task_count = db_session.scalar(select(func.count()).select_from(AgentTask))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert task_count == 1


def test_approve_agent_approval_requires_version(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="承認version必須顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)

    response = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": "idem-missing-version-001"},
    )

    db_session.refresh(approval)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert "error" not in response.json()
    assert approval.status == AgentApprovalStatus.pending


def test_idempotency_same_key_different_request_hash_is_409(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="hash顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    first = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": "idem-hash-001", "version": approval.version},
    )
    second = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": "idem-hash-001", "version": approval.version + 1},
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_stale_idempotency_pending_returns_failure_and_same_key_reuses_it(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="stale顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    idempotency_key = "idem-stale-001"
    now = utcnow_naive()
    payload = approval.original_payload_json
    request_hash = stable_json_hash(
        {
            "method": "POST",
            "path": f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
            "run_id": run_id,
            "approval_id": approval.id,
            "version": approval.version,
            "payload_hash": stable_json_hash(payload),
            "body": {"idempotency_key": idempotency_key, "version": approval.version},
        }
    )
    record = AgentApprovalIdempotencyRecord(
        approval_id=approval.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status=AgentIdempotencyStatus.in_progress,
        locked_until=now - timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS),
        processing_started_at=now - timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS + 1),
        processing_owner="test-owner",
        lease_token="test-lease",
        created_at=now,
        updated_at=now,
    )
    db_session.add(record)
    db_session.commit()

    first = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": idempotency_key, "version": approval.version},
    )
    second = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": idempotency_key, "version": approval.version},
    )

    assert first.status_code == 409
    assert first.json()["error"]["retry_with_new_idempotency_key"] is True
    assert second.status_code == 409
    assert second.json() == first.json()


def test_stale_idempotency_record_does_not_overwrite_rejected_approval(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="stale却下顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    idempotency_key = "idem-stale-rejected-001"
    now = utcnow_naive()
    payload = approval.original_payload_json
    request_hash = stable_json_hash(
        {
            "method": "POST",
            "path": f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
            "run_id": run_id,
            "approval_id": approval.id,
            "version": approval.version,
            "payload_hash": stable_json_hash(payload),
            "body": {"idempotency_key": idempotency_key, "version": approval.version},
        }
    )
    record = AgentApprovalIdempotencyRecord(
        approval_id=approval.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status=AgentIdempotencyStatus.in_progress,
        locked_until=now - timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS),
        processing_started_at=now - timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS + 1),
        processing_owner="test-owner",
        lease_token="test-lease",
        created_at=now,
        updated_at=now,
    )
    db_session.add(record)
    db_session.commit()

    rejected = client.post(f"/api/agent-runs/{run_id}/approvals/{approval.id}/reject")
    assert rejected.status_code == 200

    assert reap_stale_idempotency_records(db_session) == 1
    db_session.refresh(approval)
    db_session.refresh(record)
    assert approval.status == AgentApprovalStatus.rejected
    assert record.status == AgentIdempotencyStatus.failed
    assert record.error_code == "approval_not_pending"


def test_reject_keeps_business_tables_empty_and_finalizes_run(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="却下顧客")
    run_id = _create_agent_run(client, customer.id)
    _ensure_processed(db_session, run_id)
    approvals = list(
        db_session.scalars(
            select(AgentApproval)
            .where(AgentApproval.run_id == run_id)
            .order_by(AgentApproval.id)
        ).all()
    )

    responses = [
        client.post(f"/api/agent-runs/{run_id}/approvals/{approval.id}/reject")
        for approval in approvals
    ]
    run = db_session.get(AgentRun, run_id)
    task_count = db_session.scalar(select(func.count()).select_from(AgentTask))

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert run is not None
    assert run.status == AgentRunStatus.completed
    assert task_count == 0


def test_approval_payload_validation_failure_keeps_pending(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="validation顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    approval.original_payload_json = {"title": "", "description": "本文"}
    db_session.commit()

    response = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": "idem-invalid-001", "version": approval.version},
    )
    db_session.refresh(approval)
    record = db_session.scalar(
        select(AgentApprovalIdempotencyRecord).where(
            AgentApprovalIdempotencyRecord.approval_id == approval.id,
            AgentApprovalIdempotencyRecord.idempotency_key == "idem-invalid-001",
        )
    )

    assert response.status_code == 422
    assert approval.status == AgentApprovalStatus.pending
    assert record is not None
    assert record.status == AgentIdempotencyStatus.failed


def test_stale_pending_approval_cannot_persist_after_reject(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="承認競合顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)

    approval_session = SessionLocal()
    reject_session = SessionLocal()
    try:
        stale_approval = approval_session.get(AgentApproval, approval.id)
        rejected_approval = reject_session.get(AgentApproval, approval.id)
        assert stale_approval is not None
        assert rejected_approval is not None
        assert stale_approval.status == AgentApprovalStatus.pending

        rejected_approval.status = AgentApprovalStatus.rejected
        rejected_approval.decided_by = 1
        rejected_approval.decided_at = utcnow_naive()
        reject_session.commit()

        current_user = approval_session.get(User, 1)
        assert current_user is not None
        status_code, body = approve_agent_approval(
            approval_session,
            current_user=current_user,
            run_id=run_id,
            approval_id=approval.id,
            idempotency_key="idem-stale-rejected-001",
            version=approval.version,
        )
    finally:
        approval_session.close()
        reject_session.close()

    db_session.refresh(approval)
    assert status_code == 409
    assert body["error"]["code"] == "approval_not_pending"
    assert approval.status == AgentApprovalStatus.rejected


def test_stale_edit_approval_cannot_update_after_reject(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="編集競合顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
    }

    edit_session = SessionLocal()
    reject_session = SessionLocal()
    try:
        stale_approval = edit_session.get(AgentApproval, approval.id)
        rejected_approval = reject_session.get(AgentApproval, approval.id)
        assert stale_approval is not None
        assert rejected_approval is not None
        assert stale_approval.status == AgentApprovalStatus.pending

        rejected_approval.status = AgentApprovalStatus.rejected
        rejected_approval.decided_by = 1
        rejected_approval.decided_at = utcnow_naive()
        reject_session.commit()

        current_user = edit_session.get(User, 1)
        assert current_user is not None
        with pytest.raises(HTTPException) as error:
            edit_agent_approval(
                edit_session,
                current_user=current_user,
                run_id=run_id,
                approval_id=approval.id,
                version=stale_approval.version,
                edited_payload_json=edited_payload,
            )
    finally:
        edit_session.close()
        reject_session.close()

    db_session.refresh(approval)
    assert error.value.status_code == 409
    assert approval.status == AgentApprovalStatus.rejected
    assert approval.edited_payload_json is None


def test_edit_agent_approval_accepts_allowed_payload(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="編集承認顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    assert approval.action_type == AgentActionType.task
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version, "edited_payload_json": edited_payload},
    )

    assert response.status_code == 200
    assert response.json()["edited_payload_json"] == edited_payload


def test_edit_agent_approval_requires_version(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="version必須顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"edited_payload_json": edited_payload},
    )

    db_session.refresh(approval)
    assert response.status_code == 422
    assert approval.edited_payload_json is None


def test_edit_agent_approval_rejects_stale_version(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="古いversion顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version + 1, "edited_payload_json": edited_payload},
    )

    db_session.refresh(approval)
    assert response.status_code == 409
    assert approval.edited_payload_json is None


def test_edit_agent_approval_rejects_extra_payload_keys(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="余分payload顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
        "unexpected": {"nested": "value"},
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version, "edited_payload_json": edited_payload},
    )

    db_session.refresh(approval)
    assert response.status_code == 422
    assert approval.edited_payload_json is None


def test_edit_agent_approval_rejects_deep_payload(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="深いpayload顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": ["claim_001"],
        "unexpected": {"a": {"b": {"c": {"d": "too deep"}}}},
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version, "edited_payload_json": edited_payload},
    )

    db_session.refresh(approval)
    assert response.status_code == 422
    assert approval.edited_payload_json is None


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (
            {
                f"key_{index}": "value"
                for index in range(AGENT_APPROVAL_PATCH_MAX_OBJECT_KEYS + 1)
            },
            "edited_payload_json_too_many_keys",
        ),
        (
            {"items": ["claim"] * (AGENT_APPROVAL_PATCH_MAX_ARRAY_ITEMS + 1)},
            "edited_payload_json_array_too_long",
        ),
        (
            {"body": "x" * (AGENT_APPROVAL_PATCH_MAX_STRING_LENGTH + 1)},
            "edited_payload_json_string_too_long",
        ),
    ],
)
def test_agent_approval_patch_rejects_payload_limits(
    payload: dict[str, object], error_code: str
):
    with pytest.raises(ValidationError) as error:
        AgentApprovalPatch(version=1, edited_payload_json=payload)

    assert error_code in str(error.value)


def test_agent_approval_patch_accepts_payload_under_byte_limit():
    payload = {"items": ["x" * 4_000 for _ in range(5)]}

    result = AgentApprovalPatch(version=1, edited_payload_json=payload)

    assert result.edited_payload_json == payload


def test_agent_approval_patch_rejects_payload_over_byte_limit_boundary():
    payload = {"items": ["x" * 4_000 for _ in range(7)]}

    with pytest.raises(ValidationError):
        AgentApprovalPatch(version=1, edited_payload_json=payload)


@pytest.mark.parametrize(
    "claim_ids",
    [
        [f"claim_{index:03d}" for index in range(21)],
        [""],
        ["x" * 81],
    ],
)
def test_edit_agent_approval_rejects_invalid_claim_ids(
    client: TestClient,
    db_session: Session,
    customer_factory,
    claim_ids: list[str],
):
    customer = customer_factory(name="claim上限顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    edited_payload = {
        "title": "次回フォロー",
        "description": "確認事項を整理する",
        "claim_ids": claim_ids,
    }

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version, "edited_payload_json": edited_payload},
    )

    db_session.refresh(approval)
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_claim_ids"
    assert approval.edited_payload_json is None


def test_edit_agent_approval_validation_response_does_not_echo_payload(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="非反射顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    raw_value = "do-not-echo-" + ("x" * AGENT_APPROVAL_PATCH_MAX_BYTES)

    response = client.patch(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}",
        json={"version": approval.version, "edited_payload_json": {"body": raw_value}},
    )

    assert response.status_code == 422
    assert raw_value not in response.text


def test_idempotency_in_progress_returns_202_with_retry_after(
    client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="processing顧客")
    run_id = _create_agent_run(client, customer.id)
    approval = _ensure_processed(db_session, run_id)
    idempotency_key = "idem-processing-001"
    payload = approval.original_payload_json
    request_hash = stable_json_hash(
        {
            "method": "POST",
            "path": f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
            "run_id": run_id,
            "approval_id": approval.id,
            "version": approval.version,
            "payload_hash": stable_json_hash(payload),
            "body": {"idempotency_key": idempotency_key, "version": approval.version},
        }
    )
    now = utcnow_naive()
    db_session.add(
        AgentApprovalIdempotencyRecord(
            approval_id=approval.id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status=AgentIdempotencyStatus.in_progress,
            locked_until=now + timedelta(seconds=IDEMPOTENCY_LOCK_TTL_SECONDS),
            processing_started_at=now,
            processing_owner="test-owner",
            lease_token="test-lease",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/agent-runs/{run_id}/approvals/{approval.id}/approve",
        json={"idempotency_key": idempotency_key, "version": approval.version},
    )

    assert response.status_code == 202
    assert response.headers["Retry-After"] == "2"


def test_provider_model_params_do_not_send_unsupported_anthropic_temperature():
    settings = AgentLLMSettings(
        provider="anthropic",
        openai_api_key=None,
        openai_model="",
        anthropic_api_key="test-key",
        anthropic_model="claude-opus-4-8",
        max_tokens=1200,
        temperature=0.2,
    )
    provider = AnthropicProvider(settings=settings)

    assert provider.model_params == {"max_tokens": 1200}


def test_openai_provider_uses_responses_token_param_name():
    settings = AgentLLMSettings(
        provider="openai",
        openai_api_key="test-key",
        openai_model="openai-explicit-test-model",
        anthropic_api_key=None,
        anthropic_model=DEFAULT_ANTHROPIC_MODEL,
        max_tokens=1200,
        temperature=0.2,
    )
    provider = OpenAIProvider(settings=settings)

    assert provider.model_params == {"max_output_tokens": 1200, "temperature": 0.2}


def test_llm_post_json_returns_decoded_object(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_HTTP_TRANSPORT", "httpx")

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        assert url == "https://example.test/messages"
        assert json == {"input": "ok"}
        assert headers == {"x-api-key": "test-key"}
        assert timeout == 60
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"content": []}, request=request)

    monkeypatch.setattr("app.agent.llm.httpx.post", fake_post)

    assert _post_json(
        "https://example.test/messages",
        {"input": "ok"},
        {"x-api-key": "test-key"},
    ) == {"content": []}


def test_llm_post_json_wraps_http_errors(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_HTTP_TRANSPORT", "httpx")

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        request = httpx.Request("POST", url)
        return httpx.Response(401, text="invalid api key", request=request)

    monkeypatch.setattr("app.agent.llm.httpx.post", fake_post)

    with pytest.raises(LLMProviderError, match="llm_auth_failed"):
        _post_json("https://example.test/messages", {}, {})


def test_llm_post_json_maps_model_not_found(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_HTTP_TRANSPORT", "httpx")

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: int,
    ) -> httpx.Response:
        request = httpx.Request("POST", url)
        return httpx.Response(404, text="model not found", request=request)

    monkeypatch.setattr("app.agent.llm.httpx.post", fake_post)

    with pytest.raises(LLMProviderError, match="llm_model_not_found"):
        _post_json("https://example.test/messages", {}, {})


def test_llm_powershell_transport_sends_request_on_stdin(monkeypatch):
    def fake_run(
        command: list[str],
        *,
        input: bytes,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        payload = json.loads(input.decode("utf-8"))
        assert command[0] == "powershell.exe"
        assert payload["url"] == "https://example.test/messages"
        assert payload["body"] == {"input": "ok"}
        assert payload["headers"] == {"x-api-key": "test-key"}
        assert capture_output is True
        assert timeout == 70
        assert check is False
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=b'{"content":[]}',
            stderr=b"",
        )

    monkeypatch.setattr("app.agent.llm.subprocess.run", fake_run)

    assert _post_json_with_powershell(
        "https://example.test/messages",
        {"input": "ok"},
        {"x-api-key": "test-key", "Content-Type": "application/json"},
    ) == {"content": []}


def test_llm_powershell_transport_decodes_utf8_response(monkeypatch):
    def fake_run(
        command: list[str],
        *,
        input: bytes,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        del input, capture_output, timeout, check
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {"content": [{"text": "株式会社サンプル"}]},
                ensure_ascii=False,
            ).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr("app.agent.llm.subprocess.run", fake_run)

    assert _post_json_with_powershell(
        "https://example.test/messages",
        {"input": "ok"},
        {"x-api-key": "test-key"},
    ) == {"content": [{"text": "株式会社サンプル"}]}


def test_powershell_transport_script_writes_raw_response_bytes():
    assert "$response.Content" not in POWERSHELL_POST_JSON_SCRIPT
    assert "-OutFile $responseBodyPath" in POWERSHELL_POST_JSON_SCRIPT
    assert "[Console]::OpenStandardOutput().Write" in POWERSHELL_POST_JSON_SCRIPT
    assert "application/json; charset=utf-8" in POWERSHELL_POST_JSON_SCRIPT
    assert ".GetBytes($body)" in POWERSHELL_POST_JSON_SCRIPT
    assert "-Body $bodyBytes" in POWERSHELL_POST_JSON_SCRIPT


def test_powershell_transport_posts_utf8_request_body():
    if shutil.which("powershell.exe") is None:
        pytest.skip("powershell.exe がない環境ではPowerShell transport実送信を確認しない")

    captured_body: bytes | None = None
    captured_content_type: str | None = None

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            nonlocal captured_body, captured_content_type
            length = int(self.headers.get("content-length", "0"))
            captured_content_type = self.headers.get("content-type")
            captured_body = self.rfile.read(length)
            response = json.dumps(
                {"content": [{"text": "受信しました"}]},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _post_json_with_powershell(
            f"http://127.0.0.1:{server.server_port}/messages",
            {"customer": {"name": "株式会社サンプル"}},
            {"x-api-key": "test-key"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result == {"content": [{"text": "受信しました"}]}
    assert captured_content_type == "application/json; charset=utf-8"
    assert captured_body is not None
    assert json.loads(captured_body.decode("utf-8"))["customer"]["name"] == "株式会社サンプル"


def test_llm_powershell_transport_wraps_errors(monkeypatch):
    def fake_run(
        command: list[str],
        *,
        input: bytes,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            22,
            stdout=b"",
            stderr=b"llm_http_error:401:invalid api key",
        )

    monkeypatch.setattr("app.agent.llm.subprocess.run", fake_run)

    with pytest.raises(LLMProviderError, match="llm_auth_failed"):
        _post_json_with_powershell("https://example.test/messages", {}, {})


def test_agent_llm_settings_defaults_to_anthropic_model_and_requires_openai_model(
    monkeypatch,
):
    for name in ("OPENAI_MODEL", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(name, raising=False)

    settings = get_agent_llm_settings()

    assert settings.openai_model == ""
    assert settings.anthropic_model == DEFAULT_ANTHROPIC_MODEL


def test_agent_llm_settings_blank_anthropic_model_uses_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "   ")

    settings = get_agent_llm_settings()

    assert settings.anthropic_model == DEFAULT_ANTHROPIC_MODEL


def test_openai_provider_requires_explicit_model():
    settings = AgentLLMSettings(
        provider="openai",
        openai_api_key="test-key",
        openai_model="",
        anthropic_api_key=None,
        anthropic_model=DEFAULT_ANTHROPIC_MODEL,
        max_tokens=1200,
        temperature=None,
    )

    with pytest.raises(LLMProviderError, match="openai_model_missing"):
        OpenAIProvider(settings=settings)


def test_mock_provider_ignores_external_model_numeric_env(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "mock")
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "not-a-number")
    monkeypatch.setenv("AGENT_LLM_TEMPERATURE", "not-a-number")

    provider = select_llm_provider()

    assert isinstance(provider, MockLLMProvider)


def test_agent_llm_settings_reject_invalid_numeric_env(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "not-a-number")
    monkeypatch.setenv("AGENT_LLM_TEMPERATURE", "not-a-number")

    with pytest.raises(AgentLLMConfigError, match="agent_llm_numeric_env_invalid"):
        get_agent_llm_settings()


def test_real_provider_translates_invalid_numeric_env(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "not-a-number")

    with pytest.raises(LLMProviderError, match="agent_llm_numeric_env_invalid"):
        select_llm_provider()


def test_worker_records_invalid_numeric_env_error(
    monkeypatch, client: TestClient, db_session: Session, customer_factory
):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "not-a-number")
    customer = customer_factory(name="数値設定エラー顧客")
    run_id = _create_agent_run(client, customer.id)

    process_agent_run_in_session(db_session, run_id)

    run = db_session.get(AgentRun, run_id)
    assert run is not None
    assert run.status == AgentRunStatus.failed
    assert run.last_error_code == "agent_llm_numeric_env_invalid"


def test_worker_keeps_provider_error_code(
    monkeypatch, client: TestClient, db_session: Session, customer_factory
):
    class FailingProvider(MockLLMProvider):
        def generate(self, **_kwargs: object):
            raise LLMProviderError("llm_auth_failed")

    monkeypatch.setattr("app.agent.worker.select_llm_provider", lambda: FailingProvider())
    customer = customer_factory(name="Providerエラー顧客")
    run_id = _create_agent_run(client, customer.id)

    process_agent_run_in_session(db_session, run_id)

    run = db_session.get(AgentRun, run_id)
    assert run is not None
    assert run.status == AgentRunStatus.failed
    assert run.last_error_code == "llm_auth_failed"


def test_openai_request_body_uses_responses_json_schema(customer_factory):
    customer = customer_factory(name="OpenAI接続顧客")

    body = _openai_request_body(
        "openai-explicit-test-model",
        {"max_output_tokens": 1200},
        customer=customer,
        visits=[],
        knowledge_results=[],
    )

    assert body["model"] == "openai-explicit-test-model"
    assert body["max_output_tokens"] == 1200
    assert isinstance(body["instructions"], str)
    assert isinstance(body["input"], str)
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True


def test_anthropic_request_body_omits_strict_for_large_schema(customer_factory):
    customer = customer_factory(name="Anthropic接続顧客")

    body = _anthropic_request_body(
        DEFAULT_ANTHROPIC_MODEL,
        {"max_tokens": 1200, "temperature": 0.2},
        customer=customer,
        visits=[],
        knowledge_results=[],
    )
    tools = body["tools"]
    tool = tools[0]

    assert body["model"] == DEFAULT_ANTHROPIC_MODEL
    assert body["max_tokens"] == 1200
    assert body["temperature"] == 0.2
    assert "output_config" not in body
    assert body["tool_choice"] == {
        "type": "tool",
        "name": ANTHROPIC_OUTPUT_TOOL_NAME,
        "disable_parallel_tool_use": True,
    }
    assert tool["name"] == ANTHROPIC_OUTPUT_TOOL_NAME
    # strict はこのスキーマで "grammar too large" 400 になるため送らない
    assert "strict" not in tool
    assert tool["input_schema"]["type"] == "object"


def test_anthropic_request_body_日本語出力を指示する(customer_factory):
    customer = customer_factory(name="日本語出力顧客")

    body = _anthropic_request_body(
        DEFAULT_ANTHROPIC_MODEL,
        {"max_tokens": 1200},
        customer=customer,
        visits=[],
        knowledge_results=[],
    )
    user_context = json.loads(str(body["messages"][0]["content"]))

    assert "自然文はすべて日本語" in str(body["system"])
    assert user_context["output_language"] == "ja-JP"


def test_system_prompt_日本語自然文と識別子保持を明示する():
    prompt = _system_prompt()

    assert "自然文はすべて日本語" in prompt
    assert "固有名詞、source_type、ID、enum値は入力値のまま保持" in prompt


def test_anthropic_tool_input_extraction_validates_provider_payload(customer_factory):
    customer = customer_factory(name="tool use顧客")
    output = MockLLMProvider().generate(
        customer=customer,
        visits=[],
        knowledge_results=[],
    ).model_dump()

    extracted = _extract_anthropic_tool_input(
        {
            "content": [
                {"type": "text", "text": "入力を整形します。"},
                {
                    "type": "tool_use",
                    "name": ANTHROPIC_OUTPUT_TOOL_NAME,
                    "input": output,
                },
            ]
        }
    )

    assert extracted == output


def test_sse_last_event_id_validation(client: TestClient, db_session: Session, customer_factory):
    customer = customer_factory(name="SSE顧客")
    run_id = _create_agent_run(client, customer.id)
    _ensure_processed(db_session, run_id)

    invalid = client.get(f"/api/agent-runs/{run_id}/events", headers={"Last-Event-ID": "-1"})
    out_of_range = client.get(
        f"/api/agent-runs/{run_id}/events", headers={"Last-Event-ID": "999"}
    )
    replay = client.get(f"/api/agent-runs/{run_id}/events", headers={"Last-Event-ID": "0"})

    assert invalid.status_code == 400
    assert out_of_range.status_code == 409
    assert replay.status_code == 200
    assert "event: run_created" in replay.text


def test_fts5_query_builder_treats_operators_as_literals():
    assert build_fts5_phrase_query('更新提案 NEAR "契約"') == '"更新提案" "NEAR" """契約"""'
    assert build_fts5_phrase_query("   ") is None


def test_knowledge_search_uses_doc_acl_join(
    db_session: Session, base_users: list[User], customer_factory
):
    customer = customer_factory(name="検索顧客", owner_id=2)
    checksum = sha256_text("renewal proposal note")
    visible_doc = KnowledgeDoc(
        title="営業メモ",
        source_type="sales_playbook",
        body="renewal proposal note",
        checksum=checksum,
        doc_version="v1",
        visibility=KnowledgeVisibility.all_sales,
        source_acl_hash="sha256:test",
        created_by=1,
    )
    hidden_doc = KnowledgeDoc(
        title="限定メモ",
        source_type="sales_playbook",
        body="renewal proposal secret",
        checksum=sha256_text("renewal proposal secret"),
        doc_version="v1",
        visibility=KnowledgeVisibility.private,
        owner_user_id=3,
        source_acl_hash="sha256:test",
        created_by=1,
    )
    db_session.add_all([visible_doc, hidden_doc])
    db_session.flush()
    db_session.add_all(
        [
            KnowledgeChunk(
                doc_id=visible_doc.id,
                chunk_index=0,
                text="renewal proposal note",
                doc_version="v1",
                doc_checksum=visible_doc.checksum,
            ),
            KnowledgeChunk(
                doc_id=hidden_doc.id,
                chunk_index=0,
                text="renewal proposal secret",
                doc_version="v1",
                doc_checksum=hidden_doc.checksum,
            ),
        ]
    )
    db_session.commit()
    sales = db_session.get(User, 2)
    assert sales is not None

    results = search_knowledge_base(
        db_session,
        query="renewal proposal",
        current_user=sales,
        customer_id=customer.id,
        source_types=["sales_playbook"],
        limit=10,
        max_bm25_rank=None,
    )

    assert [result["title"] for result in results] == ["営業メモ"]
