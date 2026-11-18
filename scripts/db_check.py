"""Check that DATABASE_URL in .env works.

Run:  uv run python scripts/db_check.py
"""

import asyncio

from sqlalchemy import text

from rti_mate.config import get_settings
from rti_mate.db.session import make_engine


async def main() -> None:
    engine = make_engine(get_settings())
    async with engine.connect() as conn:
        version = await conn.scalar(text("SELECT version()"))
        database = await conn.scalar(text("SELECT current_database()"))
    await engine.dispose()
    print(f"Connected to database '{database}'")
    print(version)


if __name__ == "__main__":
    asyncio.run(main())
