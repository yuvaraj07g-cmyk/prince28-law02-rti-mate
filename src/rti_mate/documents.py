"""Document listing and retrieval endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from rti_mate.api.deps import get_repository
from rti_mate.db.repository import DocumentRepository

router = APIRouter()

RESERVED = {"q", "limit"}


@router.get("/v1/documents")
async def list_documents(
    request: Request,
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    filters = {key: value for key, value in request.query_params.items() if key not in RESERVED}
    if any("-" in name or "." in name for name in filters):
        name = sorted(filters)[0]
        raise HTTPException(status_code=400, detail=f"Unknown filter: {name}")

    records = await repository.list(q=q, filters=filters, limit=limit)
    return {"total": len(records), "items": records, "filters": filters}


@router.get("/v1/documents/{document_id}")
async def get_document(
    document_id: str,
    repository: Annotated[DocumentRepository, Depends(get_repository)],
):
    record = await repository.get(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No document with id '{document_id}'.")
    return record
