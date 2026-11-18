"""Application dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.db.repository import DocumentRepository


async def get_session(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRepository:
    return DocumentRepository(session)
