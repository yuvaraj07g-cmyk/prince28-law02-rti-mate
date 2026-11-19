import pytest
from fastapi.testclient import TestClient

from rti_mate.api.deps import get_repository
from rti_mate.api.main import create_app
from rti_mate.config import Settings

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
def client():
    settings = Settings(app_env="ci")
    app = create_app(settings)
    repository = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: repository

    with TestClient(app) as test_client:
        test_client.app.state.engine = FakeEngine()
        yield test_client
