"""Route a question before answering it.

docs       the documents can answer it
personal   it needs live information or the user's own private data: no document has that
off_topic  it is not about this product's subject

From Week 3 the product uses this to say "I don't know" instead of guessing.
"""

import re

from rti_mate.llm.gateway import LLMGateway, LLMResult

LABELS = ("docs", "personal", "off_topic")


def build_messages(prompt: str, question: str) -> list[dict[str, str]]:
    """Instructions go in the system message; the user's text goes inside tags, as data."""
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"<question>\n{question.strip()}\n</question>"},
    ]


def parse_label(reply: str, labels: tuple[str, ...] = LABELS) -> str:
    """We asked for one word. Forgive capitals and punctuation; anything else is "invalid"."""
    text = re.sub(r"off[\s-]+topic", "off_topic", reply.lower())
    found = {label for label in labels if re.search(rf"(?<![a-z_]){label}(?![a-z_])", text)}
    return found.pop() if len(found) == 1 else "invalid"


async def classify(
    gateway: LLMGateway, prompt: str, version: str, question: str
) -> tuple[str, LLMResult]:
    result = await gateway.generate(
        build_messages(prompt, question), purpose="classify", prompt_version=version, temperature=0
    )
    return parse_label(result.text), result


def accuracy(rows: list[dict]) -> float:
    """rows: [{"label": the right answer, "got": what the model said}, ...] -> 0.0 to 1.0"""
    return sum(row["got"] == row["label"] for row in rows) / len(rows) if rows else 0.0


def find_leaks(prompt: str, questions: list[str]) -> list[str]:
    """Test questions that also appear in the prompt. Such a test proves nothing."""
    text = " ".join(prompt.lower().split())
    return [q for q in questions if " ".join(q.lower().split()) in text]
