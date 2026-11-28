"""POST /v1/ingest and its progress endpoints, with a fake queue and a fake job table."""

from fastapi.testclient import TestClient

from rti_mate.api.deps import get_ingest_repo, get_manifest
from rti_mate.api.main import create_app
from rti_mate.config import Settings

TOKEN = {"X-Admin-Token": "test-token"}


def test_start_answers_202_and_queues_one_job_per_new_document(client, queue, ingest_repo):
    r = client.post("/v1/ingest", json={"limit": 10}, headers=TOKEN)
    assert r.status_code == 202  # accepted: written down, not done
    body = r.json()
    assert body == {"job_id": "job1", "queued": 2, "status_url": "/v1/ingest/job1"}
    assert queue.items == [1, 2]
    urls = [record["url"] for record in ingest_repo.jobs["job1"]]
    assert urls == ["https://x.test/1.pdf", "https://x.test/2.pdf"]  # not the known or failed one


def test_start_needs_the_admin_token(client, queue):
    assert client.post("/v1/ingest", json={}).status_code == 401
    wrong = client.post("/v1/ingest", json={}, headers={"X-Admin-Token": "guess"})
    assert wrong.status_code == 401 and wrong.headers["content-type"] == "application/problem+json"
    assert queue.items == []


def test_without_a_configured_token_ingestion_is_closed_outside_your_laptop():
    settings = Settings(app_env="production", database_url="postgresql://x/y", _env_file=None)
    with TestClient(create_app(settings)) as public:
        assert public.post("/v1/ingest", json={}).status_code == 403


def test_nothing_new_is_a_plain_200(client, queue, ingest_repo):
    ingest_repo.known |= {"f-" + "1" * 20, "f-" + "2" * 20}
    r = client.post("/v1/ingest", json={}, headers=TOKEN)
    assert r.status_code == 200 and r.json()["queued"] == 0 and queue.items == []


def test_limit_and_source_are_respected_and_validated(client, queue):
    r = client.post("/v1/ingest", json={"limit": 1}, headers=TOKEN)
    assert r.json()["queued"] == 1
    r = client.post("/v1/ingest", json={"source": "somewhere-else"}, headers=TOKEN)
    assert r.status_code == 200 and r.json()["queued"] == 0
    assert client.post("/v1/ingest", json={"limit": 0}, headers=TOKEN).status_code == 422


def test_retry_failed_queues_the_dead_letter_list_again(client, queue, ingest_repo):
    r = client.post("/v1/ingest", json={"retry_failed": True}, headers=TOKEN)
    assert r.status_code == 202 and r.json()["queued"] == 1
    assert ingest_repo.jobs["job1"][0]["url"] == "https://x.test/bad.pdf"


def test_progress_is_public_and_an_unknown_job_is_a_404_problem(client):
    job_id = client.post("/v1/ingest", json={}, headers=TOKEN).json()["job_id"]
    r = client.get(f"/v1/ingest/{job_id}")
    assert r.status_code == 200 and r.json()["counts"]["queued"] == 2
    missing = client.get("/v1/ingest/no-such-job")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"


def test_dead_letter_lists_what_failed_for_good(client):
    r = client.get("/v1/ingest/dead-letter")
    assert r.status_code == 200
    assert r.json() == {
        "count": 1,
        "items": [
            {
                "item": 7,
                "job_id": "old",
                "url": "https://x.test/bad.pdf",
                "path": "data/raw/x/bad.pdf",
                "attempts": 3,
                "error": "parse: corrupt",
            }
        ],
    }


def test_when_redis_is_away_starting_is_a_503_and_the_rest_still_works(settings, ingest_repo):
    settings.redis_url = "redis://127.0.0.1:1"  # nothing listens there
    app = create_app(settings)
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_manifest] = lambda: [
        {"url": "https://x.test/9.pdf", "sha256": "9" * 64, "status": "downloaded", "source": "x"}
    ]
    with TestClient(app) as lonely:
        r = lonely.post("/v1/ingest", json={}, headers=TOKEN)
        assert r.status_code == 503 and "Redis" in r.json()["detail"]
        assert lonely.get("/health").status_code == 200
