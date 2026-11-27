"""Integration tests: a REAL Postgres, and a brand-new database for every test run.

Point TEST_DATABASE_URL at a server where you may create databases. With docker
compose running, `uv run poe test-integration` sets it for you (see pyproject.toml).
Without TEST_DATABASE_URL these tests are skipped.
"""

import asyncio
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from rti_mate.config import get_settings
from rti_mate.db.url import to_asyncpg_url

BASE_URL = os.getenv("TEST_DATABASE_URL")


def pytest_collection_modifyitems(config, items):
    if BASE_URL:
        return
    skip = pytest.mark.skip(reason="set TEST_DATABASE_URL to run integration tests")
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(skip)


async def _admin(sql: str) -> None:
    engine = create_async_engine(to_asyncpg_url(BASE_URL), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(sql))
    await engine.dispose()


async def _create_unmanaged_table(url: str) -> None:
    engine = create_async_engine(to_asyncpg_url(url))
    try:
        async with engine.begin() as conn:
            await conn.execute(text('CREATE TABLE "playing_with_neon" (id integer PRIMARY KEY)'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_url():
    """Create test_xxxxxxxx, run the real migrations on it, drop it at the end."""
    name = f"test_{uuid.uuid4().hex[:8]}"
    asyncio.run(_admin(f'CREATE DATABASE "{name}"'))
    url = make_url(to_asyncpg_url(BASE_URL)).set(database=name)
    url_str = url.render_as_string(hide_password=False)
    asyncio.run(_create_unmanaged_table(url_str))
    patch = pytest.MonkeyPatch()
    patch.setenv("APP_ENV", "ci")
    patch.setenv("DATABASE_URL", url_str)
    get_settings.cache_clear()  # settings are cached: forget the old ones
    command.upgrade(Config("alembic.ini"), "head")
    yield url_str
    get_settings.cache_clear()
    patch.undo()
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
