"""Dependencies: endpoints ask for these instead of building them."""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.config import Settings
from rti_mate.db.llm_calls import UsageRepository
from rti_mate.db.repository import DocumentRepository
from rti_mate.llm.gateway import LLMGateway


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def check_db(request: Request) -> bool:
    """Can we run SELECT 1 within 2 seconds?"""
    try:
        async with request.app.state.engine.connect() as connection:
            await asyncio.wait_for(connection.execute(text("SELECT 1")), timeout=2)
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    return True


async def check_database(request: Request) -> bool:
    """Compatibility alias for the original readiness dependency."""
    return await check_db(request)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, closed automatically afterwards."""
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        sessionmaker = request.app.state.session_factory
    async with sessionmaker() as session:
        yield session


async def get_repo(session: Annotated[AsyncSession, Depends(get_session)]) -> DocumentRepository:
    return DocumentRepository(session)


async def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRepository:
    """Compatibility alias used by the document routes."""
    return DocumentRepository(session)


def get_gateway(request: Request) -> LLMGateway:
    return request.app.state.gateway


async def get_usage_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UsageRepository:
    return UsageRepository(session)


GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repo)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
DbCheckDep = Annotated[bool, Depends(check_db)]
