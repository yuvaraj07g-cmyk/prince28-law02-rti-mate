"""Show how Postgres runs a JSONB metadata filter."""

import asyncio
import json
import sys

from sqlalchemy import text

from rti_mate.config import get_settings
from rti_mate.db.session import make_engine

SQL = "EXPLAIN ANALYZE SELECT id, title FROM documents WHERE metadata @> CAST(:f AS jsonb)"


async def main(field: str, value: str) -> None:
    engine = make_engine(get_settings())
    params = {"f": json.dumps({field: value})}

    async with engine.connect() as connection:
        print("-- 1) What the planner chooses on its own:")
        for line in (await connection.execute(text(SQL), params)).scalars():
            print(line)

        await connection.execute(text("SET enable_seqscan = off"))
        print("\n-- 2) Seq scan switched off, to prove the index can be used:")
        for line in (await connection.execute(text(SQL), params)).scalars():
            print(line)

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: uv run python scripts/explain.py <field> <value>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
