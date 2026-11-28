"""Dependencies: endpoints ask for these instead of building them."""

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.config import Settings
from rti_mate.db.ingest_jobs import IngestRepository
from rti_mate.db.llm_calls import UsageRepository
from rti_mate.db.repository import DocumentRepository
from rti_mate.llm.gateway import LLMGateway
from rti_mate.workers.queue import Queue


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, closed automatically afterwards."""
    async with request.app.state.sessionmaker() as session:
        yield session


async def get_repo(session: Annotated[AsyncSession, Depends(get_session)]) -> DocumentRepository:
    return DocumentRepository(session)


async def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRepository:
    """Compatibility dependency used by the document routes and existing tests."""
    return DocumentRepository(session)


async def check_db(request: Request) -> bool:
    """Can we run SELECT 1 within 2 seconds?"""
    try:
        async with request.app.state.engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2)
        return True
    except Exception:
        return False


def get_gateway(request: Request) -> LLMGateway:
    return request.app.state.gateway


async def get_usage_repo(session: Annotated[AsyncSession, Depends(get_session)]) -> UsageRepository:
    return UsageRepository(session)


async def get_ingest_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestRepository:
    return IngestRepository(session)


async def get_queue(request: Request) -> Queue:
    """Connect to Redis on first use, so the API starts (and chats) even when Redis is down."""
    state = request.app.state
    if getattr(state, "queue", None) is None:
        try:
            state.queue = await Queue.connect(state.settings.redis_url)
        except Exception as exc:
            detail = "The job queue (Redis) cannot be reached."
            raise HTTPException(status_code=503, detail=detail) from exc
    return state.queue


def get_manifest(request: Request) -> list[dict]:
    """The newest manifest line per URL: what was downloaded, from where, with which hash."""
    path = request.app.state.settings.manifest_file
    if not path.is_file():
        return []
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[record["url"]] = record
    return list(latest.values())


def require_admin(request: Request, x_admin_token: Annotated[str, Header()] = "") -> None:
    """Starting an ingestion spends time and money: it needs the token from ADMIN_TOKEN."""
    settings: Settings = request.app.state.settings
    if not settings.admin_token:
        if settings.app_env == "local":
            return  # on your own laptop, no token is fine
        raise HTTPException(status_code=403, detail="Set ADMIN_TOKEN to allow ingestion here.")
    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status_code=401, detail="Missing or wrong X-Admin-Token header.")


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
IngestRepoDep = Annotated[IngestRepository, Depends(get_ingest_repo)]
QueueDep = Annotated[Queue, Depends(get_queue)]
ManifestDep = Annotated[list[dict], Depends(get_manifest)]
GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repo)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
DbCheckDep = Annotated[bool, Depends(check_db)]
