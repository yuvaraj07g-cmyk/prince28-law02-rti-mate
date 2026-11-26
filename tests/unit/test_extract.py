"""Structured output: parsing, validating and the repair loop, tested with a fake model."""

from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field, ValidationError

from rti_mate.llm.doc_meta import DocMeta
from rti_mate.llm.extract import extract, parse_json
from rti_mate.llm.gateway import FakeLLM, LLMGateway
from rti_mate.llm.prompts import latest, read_prompt


class Notice(BaseModel):
    """A tiny contract, only for these tests."""

    kind: Literal["circular", "guideline"]
    year: int = Field(ge=1950, le=2027)


GOOD = '{"kind": "circular", "year": 2024}'


def model_saying(*replies: str) -> tuple[FakeLLM, LLMGateway]:
    llm = FakeLLM(script=list(replies))
    return llm, LLMGateway([llm])


async def ask(gateway: LLMGateway, **options):
    return await extract(
        gateway, Notice, "Fill the record.", "extract_v1", "Fee circular", "New fees.", **options
    )


def test_parse_json_takes_the_object_out_of_fences_and_chatter():
    reply = (
        'Sure! Here it is:\n```json\n{"kind": "circular", "tags": {"a": 1}}\n```\nAnything else?'
    )
    assert parse_json(reply) == {"kind": "circular", "tags": {"a": 1}}


def test_parse_json_rejects_what_is_not_a_json_object():
    for reply in ("I cannot do that.", "[1, 2, 3]", '{"kind": }'):
        with pytest.raises(ValueError):
            parse_json(reply)


async def test_a_valid_reply_is_accepted_at_once():
    llm, gateway = model_saying(GOOD)
    out = await ask(gateway)
    assert out.record == Notice(kind="circular", year=2024)
    assert out.attempts == 1 and out.errors == []
    system, user = llm.seen[0]["messages"]
    assert "Fill the record." in system["content"] and '"year"' in system["content"]  # the schema
    assert user["content"] == "Title: Fee circular\n<document>\nNew fees.\n</document>"


async def test_a_rejected_reply_goes_back_with_the_reason_and_gets_repaired():
    llm, gateway = model_saying('{"kind": "circular", "year": 3024}', GOOD)
    out = await ask(gateway)
    assert out.record.year == 2024 and out.attempts == 2
    assert "less than or equal to 2027" in out.errors[0]
    *_, rejected, repair = llm.seen[1]["messages"]
    assert rejected["role"] == "assistant" and "3024" in rejected["content"]
    assert "rejected" in repair["content"] and "2027" in repair["content"]
    assert out.tokens_in == 24  # both calls are paid for: 12 + 12


async def test_after_three_bad_replies_there_is_no_record():
    llm, gateway = model_saying("I cannot do that.", '{"kind": "poem", "year": 2024}', "{}")
    out = await ask(gateway)
    assert out.record is None and out.attempts == 3 and llm.calls == 3
    assert "no JSON object" in out.errors[0] and "kind" in out.errors[1]
    assert "Field required" in out.errors[2]


async def test_schema_mode_asks_the_provider_to_enforce_the_schema():
    llm, gateway = model_saying(GOOD, GOOD)
    await ask(gateway)
    await ask(gateway, native_schema=True)
    assert "response_format" not in llm.seen[0]
    wanted = llm.seen[1]["response_format"]
    assert wanted["type"] == "json_schema" and wanted["json_schema"]["name"] == "Notice"
    assert "year" in wanted["json_schema"]["schema"]["properties"]


def test_doc_meta_is_a_strict_contract():
    good = {
        "doc_kind": "guideline",
        "year": 2022,
        "language": "en",
        "summary": "What to do when a child has dengue fever.",
        "topics": ["Dengue ", "dengue", "Fever"],
    }
    assert DocMeta.model_validate(good).topics == ["dengue", "fever"]  # tidy, no repeats
    for change in ({"year": 3024}, {"doc_kind": "poem"}, {"surprise": 1}, {"topics": []}):
        with pytest.raises(ValidationError):
            DocMeta.model_validate({**good, **change})


def test_the_extract_prompt_names_every_field_of_the_contract():
    prompt = read_prompt(Path("prompts"), latest(Path("prompts"), "extract"))
    missing = [name for name in DocMeta.model_fields if name not in prompt]
    assert not missing, f"prompts/extract_v*.md does not mention: {missing}"
