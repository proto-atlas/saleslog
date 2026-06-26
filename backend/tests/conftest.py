import os
import tempfile

# app.db が import 時に DATABASE_URL を読むため、app より先に設定する
_TEST_DB_DIR = tempfile.mkdtemp(prefix="fieldops-test-")
_TEST_DB_PATH = os.path.join(_TEST_DB_DIR, "test.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
# テストはローカル用の固定ユーザーモードを明示して実行する。
os.environ.setdefault("AUTH_MODE", "fixed")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.enums import CustomerArea, CustomerStatus, UserRole
from app.main import app
from app.models import Customer, User


@pytest.fixture()
def db_session():
    # テストごとにテーブルを作り直して分離する
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def base_users(db_session: Session) -> list[User]:
    # id=1 は get_current_user の固定ユーザー
    users = [
        User(id=1, name="管理者ユーザー", role=UserRole.manager),
        User(id=2, name="営業ユーザーA", role=UserRole.sales),
        User(id=3, name="営業ユーザーB", role=UserRole.sales),
    ]
    db_session.add_all(users)
    db_session.commit()
    return users


@pytest.fixture()
def customer_factory(db_session: Session, base_users: list[User]):
    def _create(**overrides: object) -> Customer:
        values: dict[str, object] = {
            "name": "テスト顧客",
            "address": None,
            "area": CustomerArea.tokyo,
            "status": CustomerStatus.prospect,
            "owner_id": 1,
        }
        values.update(overrides)
        customer = Customer(**values)
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        return customer

    return _create
