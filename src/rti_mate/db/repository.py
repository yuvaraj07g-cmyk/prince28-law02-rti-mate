"""Database queries for documents."""

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from rti_mate.db.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def allowed_filter_fields() -> set[str]:
        return {
            "id",
            "title",
            "source_url",
            "licence",
            "doc_type",
            "published_on",
            "decision_no",
            "date",
            "public_authority",
            "section_invoked",
            "outcome",
            "topic",
        }

    def to_record(self, document: Document) -> dict:
        record = dict(document.metadata_)
        record.update(
            {
                "id": document.external_id,
                "title": document.title,
                "source_url": document.source_url,
                "licence": document.licence,
                "doc_type": document.doc_type,
                "published_on": (
                    document.published_on.isoformat() if document.published_on else None
                ),
            }
        )
        return record

    async def get(self, external_id: str) -> dict | None:
        result = await self.session.execute(
            select(Document).where(Document.external_id == external_id)
        )
        document = result.scalar_one_or_none()
        return self.to_record(document) if document else None

    async def list(
        self,
        q: str | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[dict]]:
        conditions = []
        filters = filters or {}

        for field, value in filters.items():
            if field in {"id", "title", "source_url", "licence", "doc_type", "published_on"}:
                column = getattr(Document, "external_id" if field == "id" else field)
                conditions.append(column == value)
            else:
                metadata_value = Document.metadata_[field]
                conditions.append(
                    or_(
                        metadata_value.as_string() == value,
                        metadata_value.contains([value]),
                    )
                )

        if q:
            like = f"%{q}%"
            conditions.append(
                or_(
                    Document.title.ilike(like),
                    cast(Document.metadata_, Text).ilike(like),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Document).where(*conditions)
        )
        result = await self.session.execute(
            select(Document)
            .where(*conditions)
            .order_by(Document.external_id)
            .offset(offset)
            .limit(limit)
        )
        records = [self.to_record(document) for document in result.scalars().all()]
        return total, records

    async def database_ok(self) -> bool:
        await self.session.execute(select(1))
        return True
