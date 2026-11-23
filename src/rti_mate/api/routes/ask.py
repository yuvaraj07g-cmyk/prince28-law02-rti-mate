"""RTI question and answer API."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["questions"])


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Enter your RTI-related question",
    )


class AskResponse(BaseModel):
    question: str
    answer: str


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    question = request.question

    # Temporary response for testing the POST endpoint.
    answer = (
        "The Right to Information Act, 2005 allows Indian citizens "
        "to request information from public authorities."
    )

    return AskResponse(
        question=question,
        answer=answer,
    )
