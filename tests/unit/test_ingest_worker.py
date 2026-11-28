"""The pure parts of the worker: planning, pacing, and getting a file. No Redis, no database."""

import httpx
import pytest

from rti_mate.workers.ingest import Pace, Permanent, get_file, plan, raw_url


def record(n: int, **changes) -> dict:
    base = {
        "url": f"https://x.test/{n}.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "via": "http",
        "path": f"data/raw/x/{n}.pdf",
        "sha256": str(n) * 64,
        "status": "downloaded",
    }
    return base | changes


async def no_sleep(seconds: float) -> None:
    pass


def test_plan_takes_what_is_downloaded_new_and_wanted():
    records = [
        record(1),
        record(2, sha256="1" * 64),  # the same bytes under a second URL
        record(3),  # already in the database
        record(4, status="failed"),
        record(5, source="other"),
        record(6),
    ]
    known = {"f-" + "3" * 20}
    assert [r["url"][-5:] for r in plan(records, known)] == ["1.pdf", "5.pdf", "6.pdf"]
    assert [r["url"][-5:] for r in plan(records, known, source="x")] == ["1.pdf", "6.pdf"]
    assert len(plan(records, known, limit=2)) == 2
    assert known == {"f-" + "3" * 20}  # the caller's set is not changed


def test_raw_url_points_a_git_record_at_the_exact_commit():
    git = record(
        1,
        via="git",
        commit="05e6df7",
        url="https://github.com/fastapi/fastapi/blob/HEAD/docs/en/docs/index.md",
    )
    wanted = "https://raw.githubusercontent.com/fastapi/fastapi/05e6df7/docs/en/docs/index.md"
    assert raw_url(git) == wanted
    assert raw_url(record(2)) == "https://x.test/2.pdf"


async def test_pace_spreads_calls_evenly():
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    pace = Pace(per_minute=60, clock=lambda: 100.0, sleep=sleep)  # one pass a second
    for _ in range(3):
        await pace.wait()  # three jobs arrive in the same instant
    assert slept == [1.0, 2.0]  # the first goes at once, the others queue up behind it


async def test_a_file_on_disk_is_used_and_a_hand_downloaded_one_is_never_fetched(tmp_path):
    here = tmp_path / "rules.md"
    here.write_text("# Rules", encoding="utf-8")
    assert await get_file(record(1, path=str(here)), tmp_path, client=None) == here
    by_hand = record(2, via="manual", path=str(tmp_path / "not-here.pdf"))
    with pytest.raises(Permanent, match="by hand"):
        await get_file(by_hand, tmp_path, client=None)


async def test_a_missing_file_is_downloaded_and_errors_are_sorted_into_two_kinds(tmp_path):
    def site(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/")
        status = {"/1.pdf": 200, "/2.pdf": 404, "/3.pdf": 503}.get(request.url.path, 200)
        return httpx.Response(status, content=b"%PDF-1.4 hello")

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        got = await get_file(record(1), tmp_path, client, no_sleep)
        assert got.read_bytes() == b"%PDF-1.4 hello" and tmp_path in got.parents
        with pytest.raises(Permanent, match="404"):  # will never be there: no retry
            await get_file(record(2), tmp_path, client, no_sleep)
        with pytest.raises(RuntimeError, match="503"):  # may heal: the job is retried
            await get_file(record(3), tmp_path, client, no_sleep)
        blocked = record(4, url="https://x.test/private/4.pdf")
        with pytest.raises(Permanent, match="robots"):
            await get_file(blocked, tmp_path, client, no_sleep)
