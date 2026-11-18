"""One engine (a pool of connections) per app; one session per request."""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from rti_mate.config import Settings


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,  # connections kept open
        max_overflow=settings.db_max_overflow,  # extra ones allowed under load
        pool_pre_ping=True,  # test a connection before using it (free DBs sleep)
        pool_recycle=300,  # replace connections older than 5 minutes
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
