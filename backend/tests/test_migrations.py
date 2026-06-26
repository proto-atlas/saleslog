import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "d2f4a7c9b8e1_agent_run_active_unique_index.py"
)


def _load_active_run_migration():
    spec = importlib.util.spec_from_file_location("active_run_migration", MIGRATION_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _create_agent_runs_table(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            CREATE TABLE agent_runs (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                workflow_type VARCHAR NOT NULL,
                objective_hash VARCHAR NOT NULL,
                status VARCHAR NOT NULL
            )
            """
        )
    )


def _insert_agent_run(
    connection: sa.Connection,
    *,
    run_id: int,
    user_id: int,
    objective_hash: str,
    status: str = "waiting_for_approval",
) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO agent_runs (
                id, user_id, customer_id, workflow_type, objective_hash, status
            )
            VALUES (:id, :user_id, 1, 'meeting_prep', :objective_hash, :status)
            """
        ),
        {
            "id": run_id,
            "user_id": user_id,
            "objective_hash": objective_hash,
            "status": status,
        },
    )


def test_active_run_migration_rejects_duplicate_objectives(monkeypatch):
    migration = _load_active_run_migration()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_agent_runs_table(connection)
        _insert_agent_run(connection, run_id=1, user_id=1, objective_hash="same")
        _insert_agent_run(connection, run_id=2, user_id=1, objective_hash="same")
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        with pytest.raises(RuntimeError, match="agent_runs_active_objective_duplicates"):
            migration.upgrade()


def test_active_run_migration_assigns_slots_and_enforces_indexes(monkeypatch):
    migration = _load_active_run_migration()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_agent_runs_table(connection)
        _insert_agent_run(connection, run_id=1, user_id=1, objective_hash="objective-a")
        _insert_agent_run(connection, run_id=2, user_id=1, objective_hash="objective-b")
        _insert_agent_run(
            connection,
            run_id=3,
            user_id=1,
            objective_hash="objective-a",
            status="completed",
        )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        monkeypatch.setattr(
            migration.op,
            "add_column",
            lambda table_name, column: connection.execute(
                sa.text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} INTEGER")
            ),
        )

        def create_index(
            name: str,
            table_name: str,
            columns: list[str],
            *,
            unique: bool,
            sqlite_where: object,
            postgresql_where: object,
        ) -> None:
            unique_sql = "UNIQUE " if unique else ""
            where_sql = f" WHERE {sqlite_where}" if sqlite_where is not None else ""
            column_sql = ", ".join(columns)
            connection.execute(
                sa.text(
                    f"CREATE {unique_sql}INDEX {name} ON {table_name} "
                    f"({column_sql}){where_sql}"
                )
            )

        monkeypatch.setattr(migration.op, "create_index", create_index)

        migration.upgrade()

        rows = connection.execute(
            sa.text(
                "SELECT id, active_slot FROM agent_runs ORDER BY id"
            )
        ).all()
        assert rows == [(1, 1), (2, 2), (3, None)]
        indexes = connection.execute(sa.text("PRAGMA index_list('agent_runs')")).all()
        index_names = {str(row[1]) for row in indexes}
        assert "unique_agent_runs_active_objective" in index_names
        assert "unique_agent_runs_active_slot" in index_names

        objective_tx = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO agent_runs (
                        id, user_id, customer_id, workflow_type, objective_hash,
                        status, active_slot
                    )
                    VALUES (4, 1, 1, 'meeting_prep', 'objective-a',
                        'running', 3)
                    """
                )
            )
        objective_tx.rollback()

        slot_tx = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO agent_runs (
                        id, user_id, customer_id, workflow_type, objective_hash,
                        status, active_slot
                    )
                    VALUES (5, 1, 1, 'meeting_prep', 'objective-c',
                        'running', 1)
                    """
                )
            )
        slot_tx.rollback()


def test_active_run_migration_rejects_user_active_limit(monkeypatch):
    migration = _load_active_run_migration()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_agent_runs_table(connection)
        for index in range(6):
            _insert_agent_run(
                connection,
                run_id=index + 1,
                user_id=1,
                objective_hash=f"objective-{index}",
            )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        with pytest.raises(RuntimeError, match="agent_runs_active_limit_exceeded"):
            migration.upgrade()
