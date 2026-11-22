"""Smoke test a deployed app: is the new version live, alive and ready?

    uv run python scripts/smoke.py https://your-app.onrender.com --expect-version <sha>

Exit code 0 = passed, 1 = failed. Standard library only, so it runs anywhere.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def get(url: str) -> tuple[int | None, object]:
    """GET a URL and return (status, parsed JSON body). Status None = no answer."""
    request = urllib.request.Request(url, headers={"User-Agent": "smoke-test"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:  # 4xx / 5xx still have a body
        try:
            return error.code, json.loads(error.read() or b"null")
        except ValueError:
            return error.code, None
    except (OSError, ValueError) as error:  # DNS, refused, timeout, not JSON
        return None, str(error)


def wait_for(url: str, ok, deadline: float, interval: int) -> tuple[bool, int | None, object]:
    """Retry until ok(status, body) is true or the deadline passes."""
    while True:
        status, body = get(url)
        if ok(status, body):
            return True, status, body
        if time.monotonic() > deadline:
            return False, status, body
        detail = body.get("version", "")[:7] if isinstance(body, dict) else ""
        print(f"  waiting: {url} -> {status} {detail}".rstrip(), flush=True)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--expect-version", help="commit SHA that /health must report")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for the deploy")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    base = args.base_url.strip().rstrip("/")

    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print("FAIL base_url must be an HTTP(S) app URL, for example:")
        print("  http://127.0.0.1:8000")
        print("  https://your-app.onrender.com")
        return 1
    if parsed.hostname == "github.com" or base.endswith(".git"):
        print("FAIL that URL is a GitHub repository, not the running application.")
        print("Use the Render service URL or http://127.0.0.1:8000 for local testing.")
        return 1
    deadline = time.monotonic() + args.timeout

    # 1) Wait for the NEW version. A free instance may be asleep, and a deploy takes minutes.
    def is_new_version(status, body):
        version = body.get("version") if isinstance(body, dict) else None
        return status == 200 and args.expect_version in (None, version)

    ok, status, body = wait_for(f"{base}/health", is_new_version, deadline, args.interval)
    if not ok:
        print(f"FAIL /health never reported version {args.expect_version}: {status} {body}")
        return 1
    print(f"ok   /health -> 200, version {body.get('version')}")

    # 2) Ready? Give a sleeping database (Neon scales to zero) up to a minute to wake.
    soon = min(deadline, time.monotonic() + 60)
    ok, status, body = wait_for(f"{base}/ready", lambda s, b: s == 200, soon, 5)
    print(f"{'ok  ' if ok else 'FAIL'} /ready -> {status} {body}")
    if not ok:
        return 1

    # 3) One real endpoint that reads the database.
    status, body = get(f"{base}/v1/documents?limit=1")
    ok = status == 200 and isinstance(body, dict) and "items" in body
    print(f"{'ok  ' if ok else 'FAIL'} /v1/documents?limit=1 -> {status}")
    if not ok:
        print(body)
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
