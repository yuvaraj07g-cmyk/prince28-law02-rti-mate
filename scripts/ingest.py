"""Queue an ingestion through your API and watch the worker do it.

  uv run python scripts/ingest.py --limit 20            your laptop (http://localhost:8000)
  uv run python scripts/ingest.py --limit 20 --url https://your-app.onrender.com
  uv run python scripts/ingest.py --retry-failed        queue the dead-letter list again
  uv run python scripts/ingest.py --watch JOB_ID        only watch a job that is running

On a public URL the API wants the token: put ADMIN_TOKEN=... in .env (and in Render).
"""

import argparse
import sys
import time

import httpx

from rti_mate.config import get_settings


def show(progress: dict) -> str:
    counts = progress["counts"]
    parts = " ".join(f"{name}={counts[name]}" for name in counts)
    return f"{progress['status']:<9} {parts} pages={progress['pages']} {progress['seconds']:.0f}s"


def watch(client: httpx.Client, job_id: str, every: float) -> int:
    last = ""
    while True:
        response = client.get(f"/v1/ingest/{job_id}")
        if response.status_code != 200:
            print(f"HTTP {response.status_code}: {response.text[:200]}")
            return 1
        progress = response.json()
        line = show(progress)
        if line.rsplit(" ", 1)[0] != last:  # print only when something changed
            print(line, flush=True)
            last = line.rsplit(" ", 1)[0]
        if progress["status"] == "finished":
            break
        time.sleep(every)
    for item in progress["dead_letter"]:
        tries = "1 try" if item["attempts"] == 1 else f"{item['attempts']} tries"
        print(f"FAILED   {item['path'] or item['url']}  ({tries})  {item['error']}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:8000", help="where your API runs")
    parser.add_argument("--limit", type=int, default=20, help="queue at most N documents")
    parser.add_argument("--source", default="", help="only this source from the manifest")
    parser.add_argument("--retry-failed", action="store_true", help="queue failed items again")
    parser.add_argument("--watch", metavar="JOB_ID", help="do not start anything, only watch")
    parser.add_argument("--every", type=float, default=3.0, help="seconds between checks")
    args = parser.parse_args()
    headers = {"X-Admin-Token": get_settings().admin_token}
    try:
        with httpx.Client(base_url=args.url.rstrip("/"), headers=headers, timeout=90) as client:
            if args.watch:
                return watch(client, args.watch, args.every)
            body = {"limit": args.limit, "source": args.source, "retry_failed": args.retry_failed}
            response = client.post("/v1/ingest", json=body)
            answer = response.json()
            if response.status_code not in (200, 202):
                print(f"HTTP {response.status_code}: {answer.get('detail', answer)}")
                return 1
            if not answer["job_id"]:
                print(answer["detail"])
                return 0
            print(f"HTTP {response.status_code}: job {answer['job_id']}, {answer['queued']} queued")
            return watch(client, answer["job_id"], args.every)
    except httpx.TransportError as exc:
        print(f"{type(exc).__name__}: is the API running at {args.url}?")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
