import os
import subprocess
import sys

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.enums import AgentRunStatus, AgentWorkflowType
from app.models import AgentRun, Customer
from app.seed import reset


def test_seed_reset_deletes_agent_runs_before_customers(
    db_session: Session, customer_factory
):
    customer = customer_factory(name="seedリセット対象")
    db_session.add(
        AgentRun(
            user_id=1,
            customer_id=customer.id,
            workflow_type=AgentWorkflowType.meeting_prep,
            objective="seed reset",
            objective_hash="seed-reset",
            status=AgentRunStatus.waiting_for_approval,
        )
    )
    db_session.commit()
    db_session.expunge_all()

    reset(db_session)
    db_session.commit()

    customer_count = db_session.scalar(select(func.count()).select_from(Customer))
    agent_run_count = db_session.scalar(select(func.count()).select_from(AgentRun))
    assert customer_count == 60
    assert agent_run_count == 0


def test_seed_reset_schema_recreates_empty_db_users_table(tmp_path):
    db_path = tmp_path / "seed-empty.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    old_engine = create_engine(database_url)
    with old_engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))

    result = subprocess.run(
        [sys.executable, "-m", "app.seed", "--reset-schema", "--empty"],
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    new_engine = create_engine(database_url)
    with new_engine.connect() as connection:
        user_count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        user_name = connection.execute(
            text("SELECT name FROM users WHERE id = 1")
        ).scalar_one()
    assert user_count == 3
    assert user_name == "管理者ユーザー"
