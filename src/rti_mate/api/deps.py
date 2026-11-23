"""Application dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.config import Settings
from rti_mate.db.repository import DocumentRepository


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def check_database(request: Request) -> bool:
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True


DbCheckDep = Annotated[bool, Depends(check_database)]


async def get_session(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRepository:
    return DocumentRepository(session)
