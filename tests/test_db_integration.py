"""Runs against a REAL Postgres. Skipped unless TEST_DATABASE_URL is set.

Use an empty database you don't mind wiping, e.g. a second Neon database "test".
"""

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from rti_mate.api.main import create_app
from rti_mate.config import Settings
from rti_mate.db.models import Base, Document
from rti_mate.db.session import make_engine, make_sessionmaker

TEST_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="set TEST_DATABASE_URL to run")


async def _reset_and_seed(settings: Settings) -> None:
    engine = make_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with make_sessionmaker(engine)() as session, session.begin():
        session.add_all(
            [
                Document(external_id="001", title="Alpha", sha256="a" * 64, metadata_={"k": "x"}),
                Document(external_id="002", title="Beta", sha256="b" * 64, metadata_={"k": "y"}),
            ]
        )
    await engine.dispose()


@pytest.fixture(scope="module")
def db_client():
    settings = Settings(app_env="ci", database_url=TEST_URL, _env_file=None)
    asyncio.run(_reset_and_seed(settings))
    with TestClient(create_app(settings)) as c:
        yield c


def test_ready_with_real_database(db_client):
    assert db_client.get("/ready").json()["checks"]["database"] is True


def test_filter_uses_jsonb_containment(db_client):
    body = db_client.get("/v1/documents", params={"k": "y"}).json()
    assert [d["id"] for d in body["items"]] == ["002"]


def test_get_from_real_database(db_client):
    assert db_client.get("/v1/documents/001").json()["title"] == "Alpha"
