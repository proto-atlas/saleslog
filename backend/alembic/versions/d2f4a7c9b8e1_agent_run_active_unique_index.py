"""agent run active unique index

Revision ID: d2f4a7c9b8e1
Revises: 9b1f6e2c4a10
Create Date: 2026-06-19 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f4a7c9b8e1"
down_revision: Union[str, None] = "9b1f6e2c4a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACTIVE_AGENT_RUN_WHERE = "status IN ('pending', 'running', 'waiting_for_approval')"
MAX_ACTIVE_AGENT_RUNS_PER_USER = 5


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = op.get_bind().execute(
        sa.text(
            """
            SELECT user_id, customer_id, workflow_type, objective_hash, COUNT(*) AS count
            FROM agent_runs
            WHERE status IN ('pending', 'running', 'waiting_for_approval')
            GROUP BY user_id, customer_id, workflow_type, objective_hash
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError("agent_runs_active_objective_duplicates")
    active_rows = bind.execute(
        sa.text(
            """
            SELECT id, user_id
            FROM agent_runs
            WHERE status IN ('pending', 'running', 'waiting_for_approval')
            ORDER BY user_id, id
            """
        )
    ).mappings()
    user_slots: dict[int, int] = {}
    slot_updates: list[dict[str, int]] = []
    for row in active_rows:
        user_id = int(row["user_id"])
        next_slot = user_slots.get(user_id, 0) + 1
        if next_slot > MAX_ACTIVE_AGENT_RUNS_PER_USER:
            raise RuntimeError("agent_runs_active_limit_exceeded")
        user_slots[user_id] = next_slot
        slot_updates.append({"run_id": int(row["id"]), "active_slot": next_slot})

    op.add_column("agent_runs", sa.Column("active_slot", sa.Integer(), nullable=True))
    for update in slot_updates:
        bind.execute(
            sa.text(
                "UPDATE agent_runs SET active_slot = :active_slot WHERE id = :run_id"
            ),
            update,
        )
    op.create_index(
        "unique_agent_runs_active_objective",
        "agent_runs",
        ["user_id", "customer_id", "workflow_type", "objective_hash"],
        unique=True,
        sqlite_where=sa.text(ACTIVE_AGENT_RUN_WHERE),
        postgresql_where=sa.text(ACTIVE_AGENT_RUN_WHERE),
    )
    active_slot_where = (
        "active_slot IS NOT NULL AND "
        "status IN ('pending', 'running', 'waiting_for_approval')"
    )
    op.create_index(
        "unique_agent_runs_active_slot",
        "agent_runs",
        ["user_id", "active_slot"],
        unique=True,
        sqlite_where=sa.text(active_slot_where),
        postgresql_where=sa.text(active_slot_where),
    )


def downgrade() -> None:
    op.drop_index("unique_agent_runs_active_slot", table_name="agent_runs")
    op.drop_index("unique_agent_runs_active_objective", table_name="agent_runs")
    op.drop_column("agent_runs", "active_slot")
