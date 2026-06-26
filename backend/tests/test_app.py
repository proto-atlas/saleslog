from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_schema_is_served():
    # アプリが起動し OpenAPI スキーマを返すこと（step1 の検証ゴール）
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Saleslog API"
