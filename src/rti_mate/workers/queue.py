"""The queue: a thin layer over arq, so the rest of the code never imports it directly."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

JOB = "ingest_document"  # the name of the worker function that handles one item


def redis_settings(url: str) -> RedisSettings:
    settings = RedisSettings.from_dsn(url)
    settings.conn_retries, settings.conn_retry_delay = 1, 0  # Redis away? say so at once
    return settings


class Queue:
    def __init__(self, pool: ArqRedis) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, url: str) -> "Queue":
        return cls(await create_pool(redis_settings(url)))

    async def put(self, item_ids: list[int]) -> int:
        """Queue one job per item. An item that is already queued is not queued twice."""
        added = 0
        for item_id in item_ids:
            job = await self.pool.enqueue_job(JOB, item_id, _job_id=f"ingest:{item_id}")
            added += job is not None
        return added

    async def close(self) -> None:
        await self.pool.aclose()
