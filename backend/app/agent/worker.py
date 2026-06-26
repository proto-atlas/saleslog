from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.agent.citations import (
    create_run_source,
    enrich_citations_on_server,
    redact_artifact_content_citation_quotes,
    redact_citation_candidate_quotes,
    validate_claim_citations,
)
from app.agent.events import count_bucket, create_agent_event
from app.agent.llm import LLMProvider, LLMProviderError, select_llm_provider
from app.agent.output_schema import AgentLLMOutput
from app.agent.search import default_source_types_for_role, search_knowledge_base
from app.authz import get_customer_authorized, is_manager
from app.db import SessionLocal
from app.enums import (
    AgentActionType,
    AgentApprovalStatus,
    AgentRunStatus,
    AgentStepStatus,
)
from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    AgentStep,
    Customer,
    User,
    Visit,
    utcnow_naive,
)
from app.sqlalchemy_result import result_rowcount

APPROVAL_EXPIRATION_DAYS = 7  # 承認期限の初期値。短期の商談フォローを想定する。


def process_agent_run(run_id: int) -> None:
    with SessionLocal() as db:
        process_agent_run_in_session(db, run_id)


def process_agent_run_in_session(
    db: Session, run_id: int, *, worker_id: str = "local_worker"
) -> None:
    run = db.get(AgentRun, run_id)
    if run is None or run.status not in (AgentRunStatus.pending, AgentRunStatus.running):
        return
    user = db.get(User, run.user_id)
    if user is None:
        _fail_run_if_active(db, run_id, "agent_user_not_found")
        return

    start = utcnow_naive()
    try:
        provider = select_llm_provider()
        customer = get_customer_authorized(db, user, run.customer_id)
        _mark_run_running_if_not_cancelled(
            db,
            run=run,
            provider=provider,
            worker_id=worker_id,
            started_at=start,
        )
        _complete_step(db, run=run, step_no=1, step_type="authorize")
        create_agent_event(
            db,
            run_id=run.id,
            event_type="run_created",
            status=run.status.value,
            safe_message_key="run_created",
            step_no=1,
        )
        db.flush()

        _raise_if_cancelled(db, run)
        customer = get_customer_authorized(db, user, run.customer_id)
        customer_source = create_run_source(
            db,
            run_id=run.id,
            source_type="customer",
            source_id=str(customer.id),
            source_version=f"updated_at:{customer.updated_at.isoformat()}",
            label=f"顧客: {customer.name}",
            body=f"顧客名: {customer.name}\nステータス: {customer.status.value}",
        )
        _complete_step(
            db,
            run=run,
            step_no=2,
            step_type="fetch_customer_profile",
            source_ids=[customer_source.id],
        )
        create_agent_event(
            db,
            run_id=run.id,
            event_type="step_completed",
            status=run.status.value,
            safe_message_key="customer_loaded",
            step_no=2,
        )

        _raise_if_cancelled(db, run)
        get_customer_authorized(db, user, run.customer_id)
        visits = _load_authorized_visits(db, user, customer.id)
        activity_source_ids: list[int] = []
        for visit in visits:
            body = visit.memo or f"{visit.activity_type.value} / {visit.status.value}"
            source = create_run_source(
                db,
                run_id=run.id,
                source_type="activity",
                source_id=str(visit.id),
                source_version=f"updated_at:{visit.updated_at.isoformat()}",
                label=f"活動ログ: {visit.visited_at.date().isoformat()}",
                body=body,
            )
            activity_source_ids.append(source.id)
        _complete_step(
            db,
            run=run,
            step_no=3,
            step_type="fetch_customer_activities",
            source_ids=activity_source_ids,
        )
        create_agent_event(
            db,
            run_id=run.id,
            event_type="step_completed",
            status=run.status.value,
            safe_message_key="activities_loaded",
            safe_message_params_json={"result_count_bucket": count_bucket(len(visits))},
            step_no=3,
        )

        _raise_if_cancelled(db, run)
        get_customer_authorized(db, user, run.customer_id)
        knowledge_results = search_knowledge_base(
            db,
            query=run.objective,
            current_user=user,
            customer_id=customer.id,
            source_types=default_source_types_for_role(user.role),
            limit=5,
            max_bm25_rank=None,
        )
        knowledge_source_ids: list[int] = []
        for result in knowledge_results:
            source = create_run_source(
                db,
                run_id=run.id,
                source_type=str(result["source_type"]),
                source_id=str(result["doc_id"]),
                source_version=str(result["doc_version"]),
                label=str(result["title"]),
                body=str(result["text"]),
                chunk_id=str(result["chunk_id"]),
            )
            knowledge_source_ids.append(source.id)
        _complete_step(
            db,
            run=run,
            step_no=4,
            step_type="search_knowledge_base",
            source_ids=knowledge_source_ids,
        )
        create_agent_event(
            db,
            run_id=run.id,
            event_type="step_completed",
            status=run.status.value,
            safe_message_key="knowledge_search_completed",
            safe_message_params_json={
                "result_count_bucket": count_bucket(len(knowledge_results))
            },
            step_no=4,
        )

        db.commit()
        _raise_if_cancelled(db, run)
        db.commit()
        get_customer_authorized(db, user, run.customer_id)
        db.commit()
        llm_output = _generate_with_retry(provider, customer, visits, knowledge_results)
        output_dump = llm_output.model_dump()
        content = redact_artifact_content_citation_quotes(
            _content_from_output(output_dump)
        )
        claims = list(output_dump["claims"])
        candidates = list(output_dump["citation_candidates"])
        stored_candidates = redact_citation_candidate_quotes(candidates)
        _complete_step(db, run=run, step_no=5, step_type="generate_content_sections")
        _complete_step(
            db,
            run=run,
            step_no=6,
            step_type="generate_claims_and_citation_candidates",
        )

        _raise_if_cancelled(db, run)
        get_customer_authorized(db, user, run.customer_id)
        citations = enrich_citations_on_server(
            db,
            run_id=run.id,
            current_user=user,
            customer_id=customer.id,
            citation_candidates=candidates,
        )
        _complete_step(db, run=run, step_no=7, step_type="enrich_citations_on_server")
        valid_claims, uncertainties = validate_claim_citations(
            claims=claims, citations=citations
        )
        uncertainties.extend(list(output_dump["uncertainties"]))
        artifact = AgentArtifact(
            run_id=run.id,
            artifact_type="agent_output",
            content_json=content,
            claims_json=valid_claims,
            citation_candidates_json=stored_candidates,
            citations_json=citations,
            uncertainties_json=uncertainties,
            schema_version=run.schema_version,
        )
        db.add(artifact)
        db.flush()
        _complete_step(
            db,
            run=run,
            step_no=8,
            step_type="verify_schema",
            artifact_ids=[artifact.id],
        )
        create_agent_event(
            db,
            run_id=run.id,
            event_type="artifact_created",
            status=run.status.value,
            safe_message_key="drafting_completed",
            artifact_id=artifact.id,
            step_no=8,
        )
        _complete_step(
            db,
            run=run,
            step_no=9,
            step_type="verify_citations",
            artifact_ids=[artifact.id],
        )
        create_agent_event(
            db,
            run_id=run.id,
            event_type="step_completed",
            status=run.status.value,
            safe_message_key="citation_verified",
            artifact_id=artifact.id,
            step_no=9,
        )

        _raise_if_cancelled(db, run)
        get_customer_authorized(db, user, run.customer_id)
        approvals = _create_action_approvals(db, run, customer, content)
        _complete_step(db, run=run, step_no=10, step_type="create_action_proposals")
        latency_ms = int((utcnow_naive() - start).total_seconds() * 1000)
        if approvals:
            _complete_step(
                db,
                run=run,
                step_no=11,
                step_type="wait_for_human_approval",
            )
            _finish_run_if_active(
                db,
                run=run,
                status=AgentRunStatus.waiting_for_approval,
                latency_ms=latency_ms,
                completed_at=None,
            )
            create_agent_event(
                db,
                run_id=run.id,
                event_type="approval_required",
                status=run.status.value,
                safe_message_key="approval_required",
                safe_message_params_json={"approval_count": len(approvals)},
                approval_id=approvals[0].id,
                step_no=11,
            )
            create_agent_event(
                db,
                run_id=run.id,
                event_type="waiting_for_approval",
                status=run.status.value,
                safe_message_key="waiting_for_approval",
                approval_id=approvals[0].id,
                step_no=11,
            )
        else:
            _complete_step(db, run=run, step_no=11, step_type="completed")
            completed_at = utcnow_naive()
            _finish_run_if_active(
                db,
                run=run,
                status=AgentRunStatus.completed,
                latency_ms=latency_ms,
                completed_at=completed_at,
            )
            create_agent_event(
                db,
                run_id=run.id,
                event_type="completed",
                status=run.status.value,
                safe_message_key="completed",
                step_no=11,
            )
        db.commit()
    except LLMProviderError as error:
        db.rollback()
        _fail_run_if_active(db, run_id, str(error))
    except AgentRunCancelled:
        db.rollback()
    except AgentRunNoLongerActive:
        db.rollback()
    except Exception:
        db.rollback()
        _fail_run_if_active(db, run_id, "agent_worker_failed")


def _load_authorized_visits(db: Session, user: User, customer_id: int) -> list[Visit]:
    stmt = (
        select(Visit)
        .where(Visit.customer_id == customer_id)
        .order_by(Visit.visited_at.desc(), Visit.id.desc())
        .limit(5)
    )
    if not is_manager(user):
        stmt = stmt.where(Visit.user_id == user.id)
    return list(db.scalars(stmt).all())


def _generate_with_retry(
    provider: LLMProvider,
    customer: Customer,
    visits: list[Visit],
    knowledge_results: list[dict[str, object]],
) -> AgentLLMOutput:
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return provider.generate(
                customer=customer,
                visits=visits,
                knowledge_results=knowledge_results,
            )
        except (ValidationError, ValueError) as error:
            last_error = error
    raise LLMProviderError("llm_output_schema_invalid") from last_error


def _create_action_approvals(
    db: Session,
    run: AgentRun,
    customer: Customer,
    content: dict[str, object],
) -> list[AgentApproval]:
    approvals: list[AgentApproval] = []
    next_actions = content.get("suggested_next_actions")
    if isinstance(next_actions, list):
        for item in next_actions:
            if isinstance(item, dict) and item.get("requires_approval") is True:
                approvals.append(_create_approval_from_action(db, run, customer, item))
    email_draft = content.get("follow_up_email_draft")
    if isinstance(email_draft, dict):
        approvals.append(_create_email_draft_approval(db, run, customer, email_draft))
    return approvals


def _create_approval_from_action(
    db: Session,
    run: AgentRun,
    customer: Customer,
    action: dict[str, object],
) -> AgentApproval:
    action_type = AgentActionType(str(action["action_type"]))
    title = str(action.get("title", ""))
    description = str(action.get("description", ""))
    claim_ids = _string_list(action.get("claim_ids"))
    payload: dict[str, object]
    if action_type == AgentActionType.memo:
        payload = {"title": title, "body": description, "claim_ids": claim_ids}
        schema_version = "memo_v1"
    elif action_type == AgentActionType.email_draft:
        payload = {"subject": title, "body": description, "claim_ids": claim_ids}
        schema_version = "email_draft_v1"
    elif action_type == AgentActionType.activity_log:
        payload = {"description": description or title, "claim_ids": claim_ids}
        schema_version = "activity_log_v1"
    else:
        payload = {"title": title, "description": description, "claim_ids": claim_ids}
        schema_version = "task_v1"
    return _create_approval(
        db,
        run,
        customer,
        action_type=action_type,
        payload=payload,
        payload_schema_version=schema_version,
    )


def _create_email_draft_approval(
    db: Session,
    run: AgentRun,
    customer: Customer,
    email_draft: dict[str, object],
) -> AgentApproval:
    return _create_approval(
        db,
        run,
        customer,
        action_type=AgentActionType.email_draft,
        payload={
            "subject": str(email_draft["subject"]),
            "body": str(email_draft["body"]),
            "claim_ids": _string_list(email_draft.get("claim_ids")),
        },
        payload_schema_version="email_draft_v1",
    )


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _create_approval(
    db: Session,
    run: AgentRun,
    customer: Customer,
    *,
    action_type: AgentActionType,
    payload: dict[str, object],
    payload_schema_version: str,
) -> AgentApproval:
    now = utcnow_naive()
    approval = AgentApproval(
        run_id=run.id,
        customer_id=customer.id,
        version=1,
        action_type=action_type,
        target_entity_type="customer",
        target_entity_id=customer.id,
        original_payload_json=payload,
        payload_schema_version=payload_schema_version,
        status=AgentApprovalStatus.pending,
        expires_at=now + timedelta(days=APPROVAL_EXPIRATION_DAYS),
        created_at=now,
        updated_at=now,
    )
    db.add(approval)
    db.flush()
    return approval


class AgentRunCancelled(RuntimeError):
    pass


class AgentRunNoLongerActive(RuntimeError):
    pass


def _mark_run_running_if_not_cancelled(
    db: Session,
    *,
    run: AgentRun,
    provider: LLMProvider,
    worker_id: str,
    started_at: datetime,
) -> None:
    result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run.id,
            or_(
                and_(
                    AgentRun.status == AgentRunStatus.pending,
                    or_(AgentRun.locked_by.is_(None), AgentRun.locked_by == worker_id),
                ),
                and_(
                    AgentRun.status == AgentRunStatus.running,
                    AgentRun.locked_by == worker_id,
                ),
            ),
        )
        .values(
            status=AgentRunStatus.running,
            started_at=started_at,
            heartbeat_at=started_at,
            locked_by=worker_id,
            locked_until=started_at + timedelta(seconds=run.run_timeout_seconds),
            provider=provider.provider,
            model=provider.model,
            prompt_version=provider.prompt_version,
            schema_version=provider.schema_version,
            model_params_json=provider.model_params,
            updated_at=started_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        _raise_if_cancelled(db, run)
        raise AgentRunNoLongerActive
    db.refresh(run)


def _finish_run_if_active(
    db: Session,
    *,
    run: AgentRun,
    status: AgentRunStatus,
    latency_ms: int,
    completed_at: datetime | None,
) -> None:
    now = utcnow_naive()
    result = db.execute(
        update(AgentRun)
        .where(AgentRun.id == run.id, AgentRun.status == AgentRunStatus.running)
        .values(
            status=status,
            latency_ms=latency_ms,
            completed_at=completed_at,
            locked_by=None,
            locked_until=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        _raise_if_cancelled(db, run)
        raise AgentRunNoLongerActive
    db.refresh(run)


def _raise_if_cancelled(db: Session, run: AgentRun) -> None:
    if run.status == AgentRunStatus.cancelled:
        raise AgentRunCancelled
    with db.no_autoflush:
        current_status = db.scalar(
            select(AgentRun.status).where(AgentRun.id == run.id)
        )
    if current_status == AgentRunStatus.cancelled:
        raise AgentRunCancelled
    if current_status not in (AgentRunStatus.pending, AgentRunStatus.running):
        raise AgentRunNoLongerActive


def _content_from_output(output_dump: dict[str, object]) -> dict[str, object]:
    return {
        "customer_summary": output_dump["customer_summary"],
        "meeting_brief": output_dump["meeting_brief"],
        "risks": output_dump["risks"],
        "opportunities": output_dump["opportunities"],
        "suggested_questions": output_dump["suggested_questions"],
        "suggested_next_actions": output_dump["suggested_next_actions"],
        "follow_up_email_draft": output_dump["follow_up_email_draft"],
        "claims": output_dump["claims"],
        "citation_candidates": output_dump["citation_candidates"],
        "uncertainties": output_dump["uncertainties"],
    }


def _complete_step(
    db: Session,
    *,
    run: AgentRun,
    step_no: int,
    step_type: str,
    source_ids: list[int] | None = None,
    artifact_ids: list[int] | None = None,
) -> AgentStep:
    now = utcnow_naive()
    run.heartbeat_at = now
    run.locked_until = now + timedelta(seconds=run.run_timeout_seconds)
    run.updated_at = now
    step = AgentStep(
        run_id=run.id,
        step_no=step_no,
        step_type=step_type,
        status=AgentStepStatus.completed,
        duration_ms=0,
        source_ids_json=source_ids or [],
        artifact_ids_json=artifact_ids or [],
    )
    db.add(step)
    db.flush()
    return step


def _fail_run_if_active(db: Session, run_id: int, error_code: str) -> bool:
    now = utcnow_naive()
    result = db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status.in_((AgentRunStatus.pending, AgentRunStatus.running)),
        )
        .values(
            status=AgentRunStatus.failed,
            last_error_code=error_code,
            last_error_message_safe="Agent実行に失敗しました",
            completed_at=now,
            locked_by=None,
            locked_until=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result_rowcount(result) != 1:
        db.rollback()
        return False
    create_agent_event(
        db,
        run_id=run_id,
        event_type="failed",
        status=AgentRunStatus.failed.value,
        safe_message_key="failed",
        safe_message_params_json={"error_code": error_code},
    )
    db.commit()
    return True
