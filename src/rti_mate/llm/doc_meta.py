"""The record we want for every document of RTI Mate.

This class is a contract. The extraction prompt, the database and (from Week 3) the search
filters all rely on it: add a field freely, but rename or remove one only on purpose.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Values = Annotated[list[Short], Field(default_factory=list, max_length=8)]
Kind = Literal[
    "guideline", "rule", "notice", "list", "report", "faq", "form", "tutorial", "reference", "other"
]


class DocMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unknown key is an error, not a surprise

    doc_kind: Kind
    year: int | None = Field(default=None, ge=1950, le=2027)  # null when the document has none
    language: Literal["en", "ta", "hi", "other"]
    summary: str = Field(min_length=20, max_length=300)
    topics: Annotated[list[Short], Field(min_length=1, max_length=6)]
    # Your product's fields. A document can cover many records, so each one is a list.
    decision_no: Values
    date: Values
    public_authority: Values
    section_invoked: Values
    outcome: Values
    topic: Values

    @field_validator("topics")
    @classmethod
    def _tidy(cls, value: list[str]) -> list[str]:
        """Lowercase and without repeats, so "Dengue" and "dengue" are one topic."""
        return list(dict.fromkeys(topic.lower() for topic in value))
