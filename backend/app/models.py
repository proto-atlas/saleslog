from datetime import datetime, timezone

from sqlalchemy import (
    DDL,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import (
    ActivityType,
    AgentActionType,
    AgentApprovalStatus,
    AgentIdempotencyFailureKind,
    AgentIdempotencyStatus,
    AgentRunStatus,
    AgentStepStatus,
    AgentWorkflowType,
    CustomerArea,
    CustomerStatus,
    KnowledgeVisibility,
    UserRole,
    VisitStatus,
)


def utcnow_naive() -> datetime:
    # DB には naive UTC で格納し、API 出力時に UTC として直列化する
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    # 外部認証のユーザーIDを格納する。未連携ユーザーは null のまま扱う
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(String(200), default=None)
    area: Mapped[CustomerArea] = mapped_column(Enum(CustomerArea, name="customer_area"))
    status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus, name="customer_status"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    # 初期値は created_at と同値。実質変更時のみ明示代入で更新する（onupdate は使わない。仕様）
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # DB レベルの ON DELETE CASCADE に削除を任せる（passive_deletes。仕様）
    visits: Mapped[list["Visit"]] = relationship(
        back_populates="customer", passive_deletes=True
    )


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, name="activity_type")
    )
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus, name="visit_status"))
    visited_at: Mapped[datetime] = mapped_column(DateTime)
    memo: Mapped[str | None] = mapped_column(String(2000), default=None)
    source_approval_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_approvals.id"), unique=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    customer: Mapped[Customer] = relationship(back_populates="visits")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_user_id", "user_id"),
        Index("idx_agent_runs_customer_id", "customer_id"),
        Index("idx_agent_runs_status", "status"),
        Index("idx_agent_runs_locked_until", "locked_until"),
        Index(
            "unique_agent_runs_active_objective",
            "user_id",
            "customer_id",
            "workflow_type",
            "objective_hash",
            unique=True,
            sqlite_where=text(
                "status IN ('pending', 'running', 'waiting_for_approval')"
            ),
            postgresql_where=text(
                "status IN ('pending', 'running', 'waiting_for_approval')"
            ),
        ),
        Index(
            "unique_agent_runs_active_slot",
            "user_id",
            "active_slot",
            unique=True,
            sqlite_where=text(
                "active_slot IS NOT NULL AND status IN ('pending', 'running', 'waiting_for_approval')"
            ),
            postgresql_where=text(
                "active_slot IS NOT NULL AND status IN ('pending', 'running', 'waiting_for_approval')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    workflow_type: Mapped[AgentWorkflowType] = mapped_column(
        Enum(AgentWorkflowType, name="agent_workflow_type")
    )
    objective: Mapped[str] = mapped_column(String(500))
    objective_hash: Mapped[str] = mapped_column(String(80))
    active_slot: Mapped[int | None] = mapped_column(default=None)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name="agent_run_status"),
        default=AgentRunStatus.pending,
    )
    schema_version: Mapped[str] = mapped_column(String(32), default="agent_output_v1")
    workflow_version: Mapped[str] = mapped_column(
        String(32), default="agent_workflow_v1"
    )
    prompt_version: Mapped[str] = mapped_column(String(32), default="mock_v1")
    provider: Mapped[str] = mapped_column(String(40), default="mock")
    model: Mapped[str] = mapped_column(String(80), default="mock-llm")
    model_params_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    locked_by: Mapped[str | None] = mapped_column(String(80), default=None)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    run_timeout_seconds: Mapped[int] = mapped_column(default=180)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    latency_ms: Mapped[int | None] = mapped_column(default=None)
    last_error_code: Mapped[str | None] = mapped_column(String(80), default=None)
    last_error_message_safe: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    approvals: Mapped[list["AgentApproval"]] = relationship(back_populates="run")


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_no", name="unique_agent_steps_run_step_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"))
    step_no: Mapped[int]
    step_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[AgentStepStatus] = mapped_column(
        Enum(AgentStepStatus, name="agent_step_status")
    )
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(String(80), default=None)
    error_message_safe: Mapped[str | None] = mapped_column(String(200), default=None)
    source_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list)
    artifact_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list)
    token_usage_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    cost_estimate: Mapped[str | None] = mapped_column(String(40), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_seq", name="unique_agent_events_run_seq"),
        Index("idx_agent_events_run_id", "run_id"),
        Index("idx_agent_events_run_seq", "run_id", "event_seq"),
        Index("idx_agent_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"))
    event_seq: Mapped[int]
    step_no: Mapped[int | None] = mapped_column(default=None)
    event_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    safe_message_key: Mapped[str] = mapped_column(String(80))
    safe_message_params_json: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict
    )
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_artifacts.id"), default=None
    )
    approval_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_approvals.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentEventCursor(Base):
    __tablename__ = "agent_event_cursors"

    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), primary_key=True)
    last_event_seq: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentRunSource(Base):
    __tablename__ = "agent_run_sources"
    __table_args__ = (
        Index("idx_agent_run_sources_run_id", "run_id"),
        Index("idx_agent_run_sources_source_id", "source_id"),
        Index("idx_agent_run_sources_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"))
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(80))
    source_version: Mapped[str] = mapped_column(String(40))
    source_checksum: Mapped[str] = mapped_column(String(80))
    chunk_id: Mapped[str | None] = mapped_column(String(80), default=None)
    label: Mapped[str] = mapped_column(String(160))
    char_start: Mapped[int]
    char_end: Mapped[int]
    offset_unit: Mapped[str] = mapped_column(
        String(40), default="unicode_code_point_nfc_lf"
    )
    source_excerpt: Mapped[str | None] = mapped_column(Text, default=None)
    source_excerpt_hash: Mapped[str] = mapped_column(String(80))
    source_excerpt_redacted_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        Index("idx_agent_artifacts_run_id", "run_id"),
        Index("idx_agent_artifacts_type", "artifact_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"))
    artifact_type: Mapped[str] = mapped_column(String(60))
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    claims_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    citation_candidates_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list
    )
    citations_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    uncertainties_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list
    )
    schema_version: Mapped[str] = mapped_column(String(32), default="agent_output_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentApproval(Base):
    __tablename__ = "agent_approvals"
    __table_args__ = (
        Index("idx_agent_approvals_run_id", "run_id"),
        Index("idx_agent_approvals_customer_id", "customer_id"),
        Index("idx_agent_approvals_status", "status"),
        Index("idx_agent_approvals_decided_by", "decided_by"),
        Index("idx_agent_approvals_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    version: Mapped[int] = mapped_column(default=1)
    action_type: Mapped[AgentActionType] = mapped_column(
        Enum(AgentActionType, name="agent_action_type")
    )
    target_entity_type: Mapped[str | None] = mapped_column(String(60), default=None)
    target_entity_id: Mapped[int | None] = mapped_column(default=None)
    business_record_type: Mapped[str | None] = mapped_column(String(60), default=None)
    business_record_id: Mapped[int | None] = mapped_column(default=None)
    original_payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    edited_payload_json: Mapped[dict[str, object] | None] = mapped_column(
        JSON, default=None
    )
    approved_payload_json: Mapped[dict[str, object] | None] = mapped_column(
        JSON, default=None
    )
    payload_schema_version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[AgentApprovalStatus] = mapped_column(
        Enum(AgentApprovalStatus, name="agent_approval_status"),
        default=AgentApprovalStatus.pending,
    )
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    persisted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    persist_error: Mapped[str | None] = mapped_column(String(200), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    run: Mapped[AgentRun] = relationship(back_populates="approvals")


class AgentApprovalIdempotencyRecord(Base):
    __tablename__ = "agent_approval_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "approval_id", "idempotency_key", name="unique_agent_approval_idem_key"
        ),
        Index("idx_agent_approval_idem_approval_id", "approval_id"),
        Index("idx_agent_approval_idem_status", "status"),
        Index("idx_agent_approval_idem_locked_until", "locked_until"),
        Index("idx_agent_approval_idem_lease_token", "lease_token"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey("agent_approvals.id"))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(80))
    status: Mapped[AgentIdempotencyStatus] = mapped_column(
        Enum(AgentIdempotencyStatus, name="agent_idempotency_status")
    )
    response_json: Mapped[dict[str, object] | None] = mapped_column(JSON, default=None)
    status_code: Mapped[int | None] = mapped_column(default=None)
    error_code: Mapped[str | None] = mapped_column(String(80), default=None)
    failure_kind: Mapped[AgentIdempotencyFailureKind | None] = mapped_column(
        Enum(AgentIdempotencyFailureKind, name="agent_idempotency_failure_kind"),
        default=None,
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )
    processing_owner: Mapped[str | None] = mapped_column(String(80), default=None)
    lease_token: Mapped[str | None] = mapped_column(String(80), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentPersistedAction(Base):
    __tablename__ = "agent_persisted_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    approval_id: Mapped[int] = mapped_column(
        ForeignKey("agent_approvals.id"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80))
    business_record_type: Mapped[str] = mapped_column(String(60))
    business_record_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    source_approval_id: Mapped[int] = mapped_column(
        ForeignKey("agent_approvals.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentMemo(Base):
    __tablename__ = "agent_memos"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    source_approval_id: Mapped[int] = mapped_column(
        ForeignKey("agent_approvals.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class AgentEmailProposal(Base):
    __tablename__ = "agent_email_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    source_approval_id: Mapped[int] = mapped_column(
        ForeignKey("agent_approvals.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(80))
    doc_version: Mapped[str] = mapped_column(String(40), default="v1")
    visibility: Mapped[KnowledgeVisibility] = mapped_column(
        Enum(KnowledgeVisibility, name="knowledge_visibility")
    )
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    team_id: Mapped[str | None] = mapped_column(String(40), default=None)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), default=None)
    allowed_roles_json: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    allowed_user_ids_json: Mapped[list[int] | None] = mapped_column(JSON, default=None)
    source_acl_hash: Mapped[str] = mapped_column(String(80), default="sha256:unscoped")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("knowledge_docs.id"))
    chunk_index: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    doc_version: Mapped[str] = mapped_column(String(40))
    doc_checksum: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


event.listen(
    KnowledgeChunk.__table__,
    "after_create",
    DDL(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts "
        "USING fts5(text, chunk_id UNINDEXED, doc_id UNINDEXED, tokenize = 'unicode61')"
    ),
)
event.listen(
    KnowledgeChunk.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks "
        "BEGIN INSERT INTO knowledge_chunks_fts(text, chunk_id, doc_id) "
        "VALUES (new.text, new.id, new.doc_id); END"
    ),
)
event.listen(
    KnowledgeChunk.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks "
        "BEGIN DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id; END"
    ),
)
event.listen(
    KnowledgeChunk.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks "
        "BEGIN DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id; "
        "INSERT INTO knowledge_chunks_fts(text, chunk_id, doc_id) "
        "VALUES (new.text, new.id, new.doc_id); END"
    ),
)
event.listen(
    KnowledgeChunk.__table__,
    "before_drop",
    DDL("DROP TRIGGER IF EXISTS knowledge_chunks_au"),
)
event.listen(
    KnowledgeChunk.__table__,
    "before_drop",
    DDL("DROP TRIGGER IF EXISTS knowledge_chunks_ad"),
)
event.listen(
    KnowledgeChunk.__table__,
    "before_drop",
    DDL("DROP TRIGGER IF EXISTS knowledge_chunks_ai"),
)
event.listen(
    KnowledgeChunk.__table__,
    "before_drop",
    DDL("DROP TABLE IF EXISTS knowledge_chunks_fts"),
)
