"""Week 1 self-check: the same things the nightly scan looks at, run on your laptop.

    uv run python scripts/check_week1.py                     # files, git, tests
    uv run python scripts/check_week1.py https://x.onrender.com   # + the live URL

Standard library only. It never changes anything; it only reads and reports.
"""

import json
import re
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
OK, BAD, WARN = "  ok ", "  ✗  ", "  !  "
results: list[tuple[str, bool]] = []


def check(day: str, label: str, passed: bool, hint: str = "", warn_only: bool = False) -> None:
    mark = OK if passed else (WARN if warn_only else BAD)
    print(f"{mark}{label}" + ("" if passed or not hint else f"\n       → {hint}"))
    if not warn_only:
        results.append((day, passed))


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> int:
    live = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None
    if not exists("pyproject.toml"):
        print("Run this from your project folder (where pyproject.toml is).")
        return 2
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pkg = pyproject["project"]["name"].replace("-", "_")
    readme = (ROOT / "README.md").read_text(encoding="utf-8") if exists("README.md") else ""
    notes = (ROOT / "NOTES.md").read_text(encoding="utf-8") if exists("NOTES.md") else ""
    tracked = run(["git", "ls-files"]).stdout.split()

    print("\nD01 · repo, card and quality gates  (Day 1 Build Lab)")
    for f in [
        "README.md",
        "docs/QUESTIONS.md",
        "docs/REQUIREMENTS.md",
        ".pre-commit-config.yaml",
        ".env.example",
        "uv.lock",
    ]:
        check("D01", f, exists(f), "missing: see the Day 1 Build Lab")
    q = (
        (ROOT / "docs/QUESTIONS.md").read_text(encoding="utf-8")
        if exists("docs/QUESTIONS.md")
        else ""
    )
    rows = len(re.findall(r"^\| *\d+ *\|", q, flags=re.M))
    check(
        "D01",
        f"docs/QUESTIONS.md has 10 questions ({rows} found)",
        rows >= 10,
        "add real questions until there are 10",
    )
    todo = q.count("TODO")
    check(
        "D01",
        "no TODO left in docs/QUESTIONS.md",
        todo == 0,
        f"{todo} TODOs: fill in the document and page",
        warn_only=True,
    )
    check(
        "D01",
        ".env is NOT committed",
        ".env" not in tracked,
        "git rm --cached .env, then rotate the passwords inside it",
    )
    check(
        "D01",
        "pre-commit hooks installed",
        exists(".git/hooks/pre-commit"),
        "uv run pre-commit install",
    )

    print("\nD02 · FastAPI service  (Day 1 Build Lab)")
    for f in [f"src/{pkg}/api/main.py", f"src/{pkg}/config.py", "data/sample_records.json"]:
        check("D02", f, exists(f), "missing")
    try:
        n = len(json.loads((ROOT / "data/sample_records.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        n = 0
    check(
        "D02",
        f"data/sample_records.json has 20 records ({n} found)",
        n >= 20,
        "your 20 real records are part of Day 2's homework",
    )

    print("\nD03 · PostgreSQL  (D03 Build Lab)")
    versions = (
        list((ROOT / "migrations/versions").glob("*.py")) if exists("migrations/versions") else []
    )
    check(
        "D03",
        f"2+ migrations ({len(versions)} found)",
        len(versions) >= 2,
        "uv run alembic revision --autogenerate …",
    )
    for f in [f"src/{pkg}/db/models.py", "scripts/load_db.py"]:
        check("D03", f, exists(f), "missing")
    check(
        "D03",
        "NOTES.md has the D03 section",
        "## D03" in notes,
        "migration log, loader runs, EXPLAIN",
    )

    print("\nD04 · Docker, Compose, tests  (D04 Build Lab)")
    for f in [
        "Dockerfile",
        ".dockerignore",
        "docker-compose.yml",
        "Makefile",
        "tests/unit",
        "tests/integration",
    ]:
        check("D04", f, exists(f), "missing")
    check(
        "D04",
        "README has 'Run locally in one command'",
        "Run locally in one command" in readme,
        "add the README section from D04",
    )
    tests = run(["uv", "run", "pytest", "tests/unit"])
    found = re.search(r"\d+ (passed|failed|error)[^\n]*", tests.stdout)
    last = found.group(0) if found else "no test summary"
    check(
        "D04",
        f"unit tests pass ({last})",
        tests.returncode == 0,
        "uv run poe test, and read the first failure",
    )

    print("\nD05 · CI/CD and going live  (D05 Build Lab)")
    for f in [".github/workflows/ci.yml", ".github/workflows/cd.yml", "scripts/smoke.py"]:
        check("D05", f, exists(f), "missing")
    check(
        "D05",
        "README has the CI badge",
        "actions/workflows/ci.yml/badge.svg" in readme,
        "D05 Milestone 5",
    )
    url_in_readme = re.search(r"https://[\w.-]+\.onrender\.com", readme)
    check(
        "D05",
        "README has your live URL",
        bool(url_in_readme),
        "add **Live:** https://…onrender.com",
    )
    tags = run(["git", "tag", "--list", "week-1"]).stdout.strip()
    check("D05", "tag week-1 exists", tags == "week-1", "git tag week-1 && git push origin week-1")
    check("D05", "NOTES.md has the D05 section", "## D05" in notes, "rollback drill and lead time")

    if live or url_in_readme:
        base = live or url_in_readme.group(0)
        print(f"\nLive · {base}  (the first request may take a minute if it was asleep)")
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=90) as r:
                body = json.loads(r.read())
            check("LIVE", f"/health → 200, version {str(body.get('version'))[:7]}", True)
            head = run(["git", "rev-parse", "--verify", "--quiet", "origin/main"])
            if head.returncode == 0:
                sha = head.stdout.strip()
                check(
                    "LIVE",
                    "live version = latest main",
                    body.get("version") == sha,
                    f"main is {sha[:7]}: did the last CD run go green? (git fetch first)",
                    warn_only=True,
                )
        except Exception as error:  # noqa: BLE001 - any failure means "not live"
            check("LIVE", "/health → 200", False, f"{error}: open Render → Logs")

    total, passed = len(results), sum(ok for _, ok in results)
    print(f"\n{passed} of {total} checks passed.")
    for day in ["D01", "D02", "D03", "D04", "D05", "LIVE"]:
        missing = [ok for d, ok in results if d == day and not ok]
        if missing:
            print(f"Start with {day}: it has {len(missing)} open item(s). Later days build on it.")
            break
    else:
        print("Week 1 is complete. 🚀")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
