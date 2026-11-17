import pytest
from pydantic import ValidationError

from rti_mate.config import Settings


def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_when_records_loaded(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["records_loaded"] is True


def test_ready_is_503_when_data_file_missing(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "missing.json")

    from fastapi.testclient import TestClient

    from rti_mate.api.main import create_app

    with TestClient(create_app(settings)) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 503


def test_list_documents_paginates(client):
    r = client.get("/v1/documents", params={"limit": 2})
    body = r.json()

    assert r.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_search_filters_records(client):
    r = client.get("/v1/documents", params={"q": "beta"})
    assert [d["id"] for d in r.json()["items"]] == ["002"]


def test_get_document_found(client):
    r = client.get("/v1/documents/001")
    assert r.status_code == 200
    assert r.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    r = client.get("/v1/documents/999")

    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"

    body = r.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["request_id"] == r.headers["X-Request-ID"]


def test_bad_limit_is_422_problem(client):
    r = client.get("/v1/documents", params={"limit": 0})

    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "query.limit"


def test_request_id_is_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
