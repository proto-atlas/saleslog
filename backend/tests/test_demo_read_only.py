"""DEMO_READ_ONLY=true の読み取り専用デモモード検証。

仕様 の指定どおり専用モジュールに分離し、fixture は function スコープの
monkeypatch.setenv のみを使う（session / module スコープは使わない）。
"""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import pytest

from app.agent.text import sha256_text
from app.enums import AgentRunStatus, AgentWorkflowType
from app.models import AgentRun, AgentRunSource, Customer, utcnow_naive


@pytest.fixture()
def read_only_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEMO_READ_ONLY", "true")
    return client


def _count_customers(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Customer)) or 0


def test_write_methods_return_405_and_db_is_unchanged(
    read_only_client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="既存顧客")
    before_count = _count_customers(db_session)

    res_post = read_only_client.post(
        "/api/customers", json={"name": "追加できない", "area": "tokyo", "status": "prospect"}
    )
    assert res_post.status_code == 405

    res_patch = read_only_client.patch(
        f"/api/customers/{customer.id}", json={"name": "変更できない"}
    )
    assert res_patch.status_code == 405

    res_delete = read_only_client.delete(f"/api/customers/{customer.id}")
    assert res_delete.status_code == 405

    # DB が変化していないこと
    assert _count_customers(db_session) == before_count
    db_session.expire_all()
    assert db_session.get(Customer, customer.id).name == "既存顧客"


def test_read_methods_still_work(read_only_client: TestClient, customer_factory):
    customer = customer_factory(name="閲覧可能")
    res_list = read_only_client.get("/api/customers")
    assert res_list.status_code == 200
    res_detail = read_only_client.get(f"/api/customers/{customer.id}")
    assert res_detail.status_code == 200


def test_agent_sources_get_does_not_redact_expired_excerpt_in_read_only_mode(
    read_only_client: TestClient, db_session: Session, customer_factory
):
    customer = customer_factory(name="期限切れsource顧客")
    run = AgentRun(
        user_id=1,
        customer_id=customer.id,
        workflow_type=AgentWorkflowType.meeting_prep,
        objective="根拠確認",
        objective_hash=sha256_text("根拠確認"),
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

    res = read_only_client.get(f"/api/agent-runs/{run.id}/sources")

    assert res.status_code == 200
    db_session.refresh(source)
    assert res.json()[0]["source_excerpt"] == "期限切れ本文"
    assert source.source_excerpt == "期限切れ本文"
    assert source.source_excerpt_redacted_at is None


def test_default_is_off(client: TestClient, base_users):
    # 既定（環境変数なし）では書き込みできる
    res = client.post(
        "/api/customers", json={"name": "書き込み可", "area": "tokyo", "status": "prospect"}
    )
    assert res.status_code == 201
