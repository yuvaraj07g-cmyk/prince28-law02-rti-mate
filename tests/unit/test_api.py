import json
import logging

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from rti_mate.api.middleware import logger as middleware_logger
from rti_mate.config import Settings
from rti_mate.logging_setup import JsonFormatter


def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "dev"  # no GIT_SHA outside a CI-built image


def test_health_reports_app_and_environment(client):
    response = client.get("/health")
    assert response.json()["app"] == "rti_mate"
    assert response.json()["env"] == "ci"


def test_health_does_not_check_database(client):
    class UnavailableEngine:
        def connect(self):
            raise AssertionError("liveness must not access the database")

    client.app.state.engine = UnavailableEngine()
    response = client.get("/health")
    assert response.status_code == 200


def test_git_sha_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "3f2c1ab")
    settings = Settings(app_env="ci", database_url="postgresql://localhost/db", _env_file=None)
    assert settings.git_sha == "3f2c1ab"


def test_ready_checks_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True


@pytest.mark.parametrize(
    "database_error",
    [OSError("database unavailable"), SQLAlchemyError("database unavailable")],
)
def test_ready_is_503_when_database_is_down(client, database_error: Exception):
    class DeadEngine:
        def connect(self):
            class DeadConnection:
                async def __aenter__(self):
                    raise database_error

                async def __aexit__(self, exc_type, exc, traceback):
                    return False

            return DeadConnection()

    client.app.state.engine = DeadEngine()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": False},
    }


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2

    next_page = client.get("/v1/documents", params={"limit": 1, "offset": 1})
    assert next_page.json()["total"] == 3
    assert [record["id"] for record in next_page.json()["items"]] == ["002"]

    search_page = client.get("/v1/documents", params={"q": "a", "limit": 1})
    assert search_page.json()["total"] == 3
    assert len(search_page.json()["items"]) == 1


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


def test_request_id_is_echoed_and_logged(client, monkeypatch):
    log_events: list[tuple[str, dict[str, object]]] = []

    def capture_log(message: str, *, extra: dict[str, object]) -> None:
        log_events.append((message, extra))

    monkeypatch.setattr(middleware_logger, "info", capture_log)
    response = client.get("/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"
    message, context = log_events[0]
    assert message == "request completed"
    assert context["request_id"] == "abc123"

    record = logging.LogRecord(
        "rti_mate.api.middleware", logging.INFO, __file__, 0, message, (), None
    )
    record.__dict__.update(context)
    assert json.loads(JsonFormatter().format(record))["request_id"] == "abc123"


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
