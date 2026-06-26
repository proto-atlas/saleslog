"""agent workflow

Revision ID: 9b1f6e2c4a10
Revises: 426f933c296d
Create Date: 2026-06-16 08:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b1f6e2c4a10"
down_revision: Union[str, None] = "426f933c296d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "workflow_type",
            sa.Enum("meeting_prep", "risk_review", "follow_up", name="agent_workflow_type"),
            nullable=False,
        ),
        sa.Column("objective", sa.String(length=500), nullable=False),
        sa.Column("objective_hash", sa.String(length=80), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "waiting_for_approval",
                "completed",
                "failed",
                "cancelled",
                name="agent_run_status",
            ),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("workflow_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("model_params_json", sa.JSON(), nullable=False),
        sa.Column("locked_by", sa.String(length=80), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("run_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message_safe", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_agent_runs_customer_id_customers")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_agent_runs_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index("idx_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("idx_agent_runs_customer_id", "agent_runs", ["customer_id"])
    op.create_index("idx_agent_runs_status", "agent_runs", ["status"])
    op.create_index("idx_agent_runs_locked_until", "agent_runs", ["locked_until"])

    op.create_table(
        "agent_event_cursors",
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("last_event_seq", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_event_cursors_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_agent_event_cursors")),
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.Enum("running", "completed", "failed", name="agent_step_status"), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message_safe", sa.String(length=200), nullable=True),
        sa.Column("source_ids_json", sa.JSON(), nullable=False),
        sa.Column("artifact_ids_json", sa.JSON(), nullable=False),
        sa.Column("token_usage_json", sa.JSON(), nullable=False),
        sa.Column("cost_estimate", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_steps_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_steps")),
        sa.UniqueConstraint("run_id", "step_no", name="unique_agent_steps_run_step_no"),
    )
    op.create_table(
        "agent_run_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("source_version", sa.String(length=40), nullable=False),
        sa.Column("source_checksum", sa.String(length=80), nullable=False),
        sa.Column("chunk_id", sa.String(length=80), nullable=True),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("offset_unit", sa.String(length=40), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("source_excerpt_hash", sa.String(length=80), nullable=False),
        sa.Column("source_excerpt_redacted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_run_sources_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_run_sources")),
    )
    op.create_index("idx_agent_run_sources_run_id", "agent_run_sources", ["run_id"])
    op.create_index("idx_agent_run_sources_source_id", "agent_run_sources", ["source_id"])
    op.create_index("idx_agent_run_sources_expires_at", "agent_run_sources", ["expires_at"])

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("claims_json", sa.JSON(), nullable=False),
        sa.Column("citation_candidates_json", sa.JSON(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("uncertainties_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_artifacts_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_artifacts")),
    )
    op.create_index("idx_agent_artifacts_run_id", "agent_artifacts", ["run_id"])
    op.create_index("idx_agent_artifacts_type", "agent_artifacts", ["artifact_type"])

    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.Enum("activity_log", "task", "memo", "email_draft", name="agent_action_type"), nullable=False),
        sa.Column("target_entity_type", sa.String(length=60), nullable=True),
        sa.Column("target_entity_id", sa.Integer(), nullable=True),
        sa.Column("business_record_type", sa.String(length=60), nullable=True),
        sa.Column("business_record_id", sa.Integer(), nullable=True),
        sa.Column("original_payload_json", sa.JSON(), nullable=False),
        sa.Column("edited_payload_json", sa.JSON(), nullable=True),
        sa.Column("approved_payload_json", sa.JSON(), nullable=True),
        sa.Column("payload_schema_version", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "edited_and_approved",
                "rejected",
                "persisted",
                "persist_failed",
                "expired",
                "cancelled",
                name="agent_approval_status",
            ),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("persisted_at", sa.DateTime(), nullable=True),
        sa.Column("persist_error", sa.String(length=200), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_agent_approvals_customer_id_customers")),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name=op.f("fk_agent_approvals_decided_by_users")),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_approvals_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_approvals")),
    )
    op.create_index("idx_agent_approvals_run_id", "agent_approvals", ["run_id"])
    op.create_index("idx_agent_approvals_customer_id", "agent_approvals", ["customer_id"])
    op.create_index("idx_agent_approvals_status", "agent_approvals", ["status"])
    op.create_index("idx_agent_approvals_decided_by", "agent_approvals", ["decided_by"])
    op.create_index("idx_agent_approvals_expires_at", "agent_approvals", ["expires_at"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("safe_message_key", sa.String(length=80), nullable=False),
        sa.Column("safe_message_params_json", sa.JSON(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=True),
        sa.Column("approval_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["agent_approvals.id"], name=op.f("fk_agent_events_approval_id_agent_approvals")),
        sa.ForeignKeyConstraint(["artifact_id"], ["agent_artifacts.id"], name=op.f("fk_agent_events_artifact_id_agent_artifacts")),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name=op.f("fk_agent_events_run_id_agent_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_events")),
        sa.UniqueConstraint("run_id", "event_seq", name="unique_agent_events_run_seq"),
    )
    op.create_index("idx_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("idx_agent_events_run_seq", "agent_events", ["run_id", "event_seq"])
    op.create_index("idx_agent_events_created_at", "agent_events", ["created_at"])

    op.create_table(
        "agent_approval_idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approval_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.Enum("in_progress", "succeeded", "failed", name="agent_idempotency_status"), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("failure_kind", sa.Enum("retryable_before_side_effect", "permanent", "unknown_after_possible_side_effect", name="agent_idempotency_failure_kind"), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(), nullable=True),
        sa.Column("processing_owner", sa.String(length=80), nullable=True),
        sa.Column("lease_token", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["agent_approvals.id"], name=op.f("fk_agent_approval_idempotency_records_approval_id_agent_approvals")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_approval_idempotency_records")),
        sa.UniqueConstraint("approval_id", "idempotency_key", name="unique_agent_approval_idem_key"),
    )
    op.create_index("idx_agent_approval_idem_approval_id", "agent_approval_idempotency_records", ["approval_id"])
    op.create_index("idx_agent_approval_idem_status", "agent_approval_idempotency_records", ["status"])
    op.create_index("idx_agent_approval_idem_locked_until", "agent_approval_idempotency_records", ["locked_until"])
    op.create_index("idx_agent_approval_idem_lease_token", "agent_approval_idempotency_records", ["lease_token"])

    _create_business_tables()
    _create_knowledge_tables()
    with op.batch_alter_table("visits") as batch_op:
        batch_op.add_column(sa.Column("source_approval_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_visits_source_approval_id_agent_approvals"),
            "agent_approvals",
            ["source_approval_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            op.f("uq_visits_source_approval_id"),
            ["source_approval_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("visits") as batch_op:
        batch_op.drop_constraint(op.f("uq_visits_source_approval_id"), type_="unique")
        batch_op.drop_constraint(op.f("fk_visits_source_approval_id_agent_approvals"), type_="foreignkey")
        batch_op.drop_column("source_approval_id")

    _drop_knowledge_tables()
    for table_name in (
        "agent_email_proposals",
        "agent_memos",
        "agent_tasks",
        "agent_persisted_actions",
        "agent_approval_idempotency_records",
        "agent_events",
        "agent_approvals",
        "agent_artifacts",
        "agent_run_sources",
        "agent_steps",
        "agent_event_cursors",
        "agent_runs",
    ):
        op.drop_table(table_name)


def _create_business_tables() -> None:
    op.create_table(
        "agent_persisted_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approval_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("business_record_type", sa.String(length=60), nullable=False),
        sa.Column("business_record_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["approval_id"], ["agent_approvals.id"], name=op.f("fk_agent_persisted_actions_approval_id_agent_approvals")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_persisted_actions")),
        sa.UniqueConstraint("approval_id", name=op.f("uq_agent_persisted_actions_approval_id")),
    )
    for table_name, columns in (
        ("agent_tasks", [sa.Column("title", sa.String(length=160), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("due_at", sa.DateTime(), nullable=True)]),
        ("agent_memos", [sa.Column("title", sa.String(length=160), nullable=False), sa.Column("body", sa.Text(), nullable=False)]),
        ("agent_email_proposals", [sa.Column("subject", sa.String(length=200), nullable=False), sa.Column("body", sa.Text(), nullable=False)]),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            *columns,
            sa.Column("source_approval_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f(f"fk_{table_name}_customer_id_customers")),
            sa.ForeignKeyConstraint(["source_approval_id"], ["agent_approvals.id"], name=op.f(f"fk_{table_name}_source_approval_id_agent_approvals")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f(f"fk_{table_name}_user_id_users")),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint("source_approval_id", name=op.f(f"uq_{table_name}_source_approval_id")),
        )


def _create_knowledge_tables() -> None:
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=80), nullable=False),
        sa.Column("doc_version", sa.String(length=40), nullable=False),
        sa.Column("visibility", sa.Enum("all_sales", "managers_only", "owner_team", "customer_scoped", "private", name="knowledge_visibility"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("allowed_roles_json", sa.JSON(), nullable=True),
        sa.Column("allowed_user_ids_json", sa.JSON(), nullable=True),
        sa.Column("source_acl_hash", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_knowledge_docs_created_by_users")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_knowledge_docs_customer_id_customers")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_knowledge_docs_owner_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_docs")),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("doc_version", sa.String(length=40), nullable=False),
        sa.Column("doc_checksum", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["knowledge_docs.id"], name=op.f("fk_knowledge_chunks_doc_id_knowledge_docs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
    )
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts "
        "USING fts5(text, chunk_id UNINDEXED, doc_id UNINDEXED, tokenize = 'unicode61')"
    )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks "
        "BEGIN INSERT INTO knowledge_chunks_fts(text, chunk_id, doc_id) "
        "VALUES (new.text, new.id, new.doc_id); END"
    )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks "
        "BEGIN DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id; END"
    )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks "
        "BEGIN DELETE FROM knowledge_chunks_fts WHERE chunk_id = old.id; "
        "INSERT INTO knowledge_chunks_fts(text, chunk_id, doc_id) "
        "VALUES (new.text, new.id, new.doc_id); END"
    )


def _drop_knowledge_tables() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_au")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ad")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ai")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks_fts")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_docs")
