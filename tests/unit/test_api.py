import pytest
from pydantic import ValidationError

from rti_mate.config import Settings


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_checks_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True


def test_ready_is_503_when_database_is_down(client):
    class DeadEngine:
        def connect(self):
            class DeadConnection:
                async def __aenter__(self):
                    raise ConnectionError("database unavailable")

                async def __aexit__(self, exc_type, exc, traceback):
                    return False

            return DeadConnection()

    client.app.state.engine = DeadEngine()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 2

    next_page = client.get("/v1/documents", params={"limit": 1, "offset": 1})
    assert [record["id"] for record in next_page.json()["items"]] == ["002"]


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})
    assert [record["id"] for record in response.json()["items"]] == ["002"]


def test_metadata_filter(client):
    response = client.get("/v1/documents", params={"year": 2024})
    assert [record["id"] for record in response.json()["items"]] == ["002"]
    assert response.json()["filters"] == {"year": "2024"}


def test_get_document_found(client):
    response = client.get("/v1/documents/001")
    assert response.status_code == 200
    assert response.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    response = client.get("/v1/documents/999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["status"] == 404
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_bad_filter_is_problem(client):
    response = client.get("/v1/documents", params={"Bad-Name": "1"})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_bad_limit_is_422_problem(client):
    response = client.get("/v1/documents", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "query.limit"


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_url_is_converted_to_asyncpg():
    settings = Settings(
        app_env="ci",
        database_url="postgresql://host/db?sslmode=require&channel_binding=require",
    )
    assert "postgresql+asyncpg://" in settings.database_url
    assert "ssl=require" in settings.database_url
