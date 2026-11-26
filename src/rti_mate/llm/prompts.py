"""Prompts are files: prompts/<task>_v<number>.md. The file name is the version id.

Changing a prompt means adding a new file, never editing an old one: the version id is
logged with every model call, so you can always tell which words produced which answer.
"""

import re
from pathlib import Path

_VERSION = re.compile(r"_v(\d+)$")


def read_prompt(directory: Path, name: str) -> str:
    return (directory / f"{name}.md").read_text(encoding="utf-8").strip()


def versions(directory: Path, task: str) -> list[str]:
    """Every version of one task, oldest first: classify_v1, classify_v2, classify_v10."""
    names = [p.stem for p in directory.glob(f"{task}_v*.md") if _VERSION.search(p.stem)]
    return sorted(names, key=lambda name: int(_VERSION.search(name).group(1)))


def latest(directory: Path, task: str) -> str:
    found = versions(directory, task)
    if not found:
        raise FileNotFoundError(f"no prompt file {directory}/{task}_v1.md")
    return found[-1]
