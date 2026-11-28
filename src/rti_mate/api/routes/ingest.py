"""POST /v1/ingest queues the work and answers at once. GET shows how far the worker is."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from rti_mate.api.deps import IngestRepoDep, ManifestDep, QueueDep, require_admin
from rti_mate.workers.ingest import plan

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=2000)  # how many documents to queue at most
    source: str = Field(default="", max_length=100)  # only this source from the manifest
    retry_failed: bool = False  # queue the dead-letter list again instead of new documents


@router.post("", status_code=202, dependencies=[Depends(require_admin)])
async def start(
    body: IngestRequest,
    response: Response,
    repo: IngestRepoDep,
    queue: QueueDep,
    manifest: ManifestDep,
) -> dict:
    """202 Accepted: "I have written your request down", not "the work is done"."""
    if body.retry_failed:
        records = (await repo.failed_records())[: body.limit]
    else:
        known = await repo.known_ids()
        records = plan(manifest, known, source=body.source, limit=body.limit)
    if not records:
        response.status_code = 200
        return {"job_id": None, "queued": 0, "detail": "Nothing to do: all of it is ingested."}
    job_id, item_ids = await repo.create(records)
    await queue.put(item_ids)
    return {"job_id": job_id, "queued": len(item_ids), "status_url": f"/v1/ingest/{job_id}"}


@router.get("/dead-letter")
async def dead_letter(repo: IngestRepoDep, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> dict:
    """Every item that failed for good, with the reason. A person decides what happens next."""
    items = await repo.dead_letter(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/{job_id}")
async def progress(job_id: str, repo: IngestRepoDep) -> dict:
    found = await repo.progress(job_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"No ingest job with id {job_id!r}.")
    return found
