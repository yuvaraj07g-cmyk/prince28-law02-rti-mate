"""Document listing and retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from rti_mate.api.deps import get_store
from rti_mate.store import RecordStore

router = APIRouter()


@router.get("/v1/documents")
def list_documents(
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    store: RecordStore = Depends(get_store),
):
    records = store.list_records()

    if q:
        records = [record for record in records if q.lower() in str(record).lower()]

    return {
        "total": len(records),
        "items": records[:limit],
    }


@router.get("/v1/documents/{document_id}")
def get_document(
    document_id: str,
    store: RecordStore = Depends(get_store),
):
    record = store.get_record(document_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{document_id}'.",
        )

    return record
