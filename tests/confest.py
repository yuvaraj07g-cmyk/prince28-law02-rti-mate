import pytest
from fastapi.testclient import TestClient

from rti_mate.api.deps import (
    check_db,
    get_gateway,
    get_ingest_repo,
    get_manifest,
    get_queue,
    get_repo,
    get_usage_repo,
)
from rti_mate.api.main import create_app
from rti_mate.config import Settings
from rti_mate.llm.gateway import FakeLLM, LLMGateway

# Tiny fake records: unit tests never touch a real database or your data file.
SAMPLE = [
    {"id": "001", "title": "Alpha guideline", "year": 2023, "kind": "guideline"},
    {"id": "002", "title": "Beta circular", "year": 2024, "kind": "circular"},
    {"id": "003", "title": "Gamma notice", "year": 2025, "kind": "circular"},
]


class FakeRepo:
    """Behaves like DocumentRepository, but keeps rows in a Python list."""

    def __init__(self, rows):
        self.rows = rows

    async def list(self, *, q, filters, limit, offset):
        rows = [
            r
            for r in self.rows
            if (not q or q.lower() in str(r).lower())
            and all(str(r.get(k)) == v for k, v in filters.items())
        ]
        return len(rows), rows[offset : offset + limit]

    async def get(self, external_id):
        return next((r for r in self.rows if r["id"] == external_id), None)


@pytest.fixture
def settings():
    # _env_file=None: ignore your local .env so tests behave the same everywhere
    return Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/unused",
        admin_token="test-token",  # pragma: allowlist secret
        _env_file=None,
    )


@pytest.fixture
def db_state():
    return {"up": True}


class FakeUsage:
    async def by_day(self, days=7):
        return [
            {
                "day": "2026-11-25",
                "calls": 3,
                "errors": 1,
                "fallbacks": 1,
                "tokens_in": 300,
                "tokens_out": 120,
                "cost_inr": 0.0642,
            }
        ]


@pytest.fixture
def llm():
    """The fake model behind /v1/chat in unit tests. Put strings or errors in llm.script."""
    return FakeLLM()


class FakeQueue:
    """Remembers which items were queued. No Redis anywhere near a unit test."""

    def __init__(self):
        self.items: list[int] = []

    async def put(self, item_ids):
        self.items += item_ids
        return len(item_ids)


class FakeIngestRepo:
    """Behaves like IngestRepository, with Python lists instead of tables."""

    def __init__(self):
        self.known = {"f-" + "a" * 20}  # one document is already in the database
        self.jobs: dict[str, list[dict]] = {}
        self.failed = [
            {
                "item": 7,
                "job_id": "old",
                "url": "https://x.test/bad.pdf",
                "path": "data/raw/x/bad.pdf",
                "attempts": 3,
                "error": "parse: corrupt",
            }
        ]

    async def known_ids(self):
        return self.known

    async def create(self, records):
        job_id = f"job{len(self.jobs) + 1}"
        self.jobs[job_id] = records
        return job_id, list(range(1, len(records) + 1))

    async def progress(self, job_id):
        if job_id not in self.jobs:
            return None
        counts = {"queued": len(self.jobs[job_id]), "running": 0, "done": 0, "skipped": 0}
        return {"job_id": job_id, "status": "working", "counts": counts | {"failed": 0}}

    async def dead_letter(self, *, job_id=None, limit=50):
        return self.failed[:limit]

    async def failed_records(self):
        return [{"url": item["url"], "path": item["path"]} for item in self.failed]


def manifest_line(n: int, **changes) -> dict:
    record = {
        "url": f"https://x.test/{n}.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "path": f"data/raw/x/{n}.pdf",
        "sha256": str(n) * 64,
        "status": "downloaded",
    }
    return record | changes


MANIFEST = [
    manifest_line(1),
    manifest_line(2),
    manifest_line(3, sha256="a" * 64),  # already in the database
    manifest_line(4, status="failed"),  # never downloaded
]


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
def ingest_repo():
    return FakeIngestRepo()


@pytest.fixture
def client(settings, db_state, llm, queue, ingest_repo):
    app = create_app(settings)
    app.dependency_overrides[get_repo] = lambda: FakeRepo(SAMPLE)
    app.dependency_overrides[check_db] = lambda: db_state["up"]
    app.dependency_overrides[get_gateway] = lambda: LLMGateway([llm])
    app.dependency_overrides[get_usage_repo] = lambda: FakeUsage()
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_manifest] = lambda: MANIFEST
    with TestClient(app) as c:
        yield c
