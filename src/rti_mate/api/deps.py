"""Application dependencies."""

from fastapi import Request

from rti_mate.store import RecordStore


def get_store(request: Request) -> RecordStore:
    return request.app.state.store
