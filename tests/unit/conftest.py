import pytest
from fastapi.testclient import TestClient

from rti_mate.api.deps import get_gateway, get_repository, get_usage_repo
from rti_mate.api.main import create_app
from rti_mate.config import Settings
from rti_mate.llm.gateway import FakeLLM, LLMGateway

SAMPLE = [
    {"id": "001", "title": "Alpha guideline", "year": 2023},
    {"id": "002", "title": "Beta circular", "year": 2024},
    {"id": "003", "title": "Gamma notice", "year": 2025},
]


class FakeRepository:
    def __init__(self, records=SAMPLE):
        self.records = records

    async def list(self, q=None, filters=None, limit=20, offset=0):
        records = list(self.records)
        if q:
            records = [record for record in records if q.lower() in str(record).lower()]
        for field, value in (filters or {}).items():
            records = [record for record in records if str(record.get(field)) == str(value)]
        return len(records), records[offset : offset + limit]

    async def get(self, external_id):
        return next((record for record in self.records if record["id"] == external_id), None)


class FakeConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement):
        return None


class FakeEngine:
    def connect(self):
        return FakeConnection()

    async def dispose(self):
        return None


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(llm):
    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/unused",
        _env_file=None,
    )
def client():
    settings = Settings(app_env="ci", _env_file=None)
    app = create_app(settings)
    repository = FakeRepository()

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

    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_gateway] = lambda: LLMGateway([llm])
    app.dependency_overrides[get_usage_repo] = lambda: FakeUsage()

    with TestClient(app) as test_client:
        test_client.app.state.engine = FakeEngine()
        yield test_client
