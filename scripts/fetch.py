"""Collect your corpus. Four doors, one logbook (data/manifest.jsonl).

  uv run python scripts/fetch.py urls                  download every URL in data/sources.csv
  uv run python scripts/fetch.py repo OWNER/REPO ...   a Git repository: clone it, don't crawl it
  uv run python scripts/fetch.py sitemap URL ...       list a site's pages into data/sources.csv
  uv run python scripts/fetch.py manual FOLDER ...     register files you downloaded by hand

Add --help after any of them to see its options. Every door is safe to run again.
"""

import argparse
import asyncio
import csv
import gzip
import hashlib
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from rti_mate.ingest.fetch import (
    USER_AGENT,
    Manifest,
    fetch_all,
    now_iso,
    read_sources,
    slug,
)

SOURCES = Path("data/sources.csv")
RAW = Path("data/raw")
MANIFEST = Path("data/manifest.jsonl")
HEADER = ["url", "source", "licence", "title"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def local_record(path: Path, **fields: str) -> dict:
    """A manifest line for a file that is already on disk (git and manual doors)."""
    size, digest = path.stat().st_size, sha256_file(path)
    on_disk = {"path": path.as_posix(), "bytes": size, "sha256": digest}
    return fields | on_disk | {"status": "downloaded", "fetched_at": now_iso()}


# ---------- door 1: a list of URLs ----------
def cmd_urls(args: argparse.Namespace) -> int:
    sources = read_sources(args.sources)
    if args.limit:
        sources = sources[: args.limit]
    seen = 0

    def show(record: dict) -> None:
        nonlocal seen
        seen += 1
        if record["status"] == "downloaded":
            detail = f"{record['bytes'] / 1024:9.1f} kB  {record['path']}"
        else:
            detail = f"{record.get('error', '')}  {record['url']}"
        print(f"[{seen:>4}] {record['status']:<10} {detail}", flush=True)

    started = time.perf_counter()
    counts = asyncio.run(
        fetch_all(
            sources,
            max_concurrency=args.max_concurrency,
            per_host_delay=args.delay,
            on_result=show,
        )
    )
    took = time.perf_counter() - started
    summary = " ".join(f"{name}={count}" for name, count in counts.items())
    print(f"sources={len(sources)} {summary} seconds={took:.1f}")
    return 0


# ---------- door 2: a Git repository ----------
def git(*args: str, cwd: Path | None = None) -> str:
    command = ["git", "-c", "core.longpaths=true", *args]
    env = os.environ | {"GIT_TERMINAL_PROMPT": "0"}  # never stop to ask for a password
    done = subprocess.run(command, cwd=cwd, env=env, check=True, capture_output=True, text=True)
    return done.stdout


def cmd_repo(args: argparse.Namespace) -> int:
    repo = args.repo.removeprefix("https://github.com/").removesuffix(".git").strip("/")
    dest = RAW / slug(args.source)
    try:
        if not (dest / ".git").exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            # depth 1 = newest version only; blob:none + sparse = only the folders you ask for
            clone = ["clone", "--depth", "1", "--filter=blob:none", "--sparse"]
            if args.ref:
                clone += ["--branch", args.ref]
            git(*clone, f"https://github.com/{repo}.git", str(dest))
        if args.path == ["."]:
            git("sparse-checkout", "disable", cwd=dest)
        else:
            git("sparse-checkout", "set", *args.path, cwd=dest)
        commit = git("rev-parse", "HEAD", cwd=dest).strip()
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}")
        print("Check the OWNER/REPO spelling, the --path folders and your internet connection.")
        return 1
    wanted = {ext if ext.startswith(".") else "." + ext for ext in args.ext}
    manifest = Manifest(MANIFEST)
    added = unchanged = 0
    for folder in args.path:
        for path in sorted((dest / folder).rglob("*")):
            if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in wanted:
                continue
            inside = path.relative_to(dest).as_posix()
            record = local_record(
                path,
                url=f"https://github.com/{repo}/blob/HEAD/{inside}",
                source=args.source,
                licence=args.licence,
                title=inside,
                via="git",
                commit=commit,
            )
            old = manifest.records.get(record["url"], {})
            if old.get("sha256") == record["sha256"] and old.get("path") == record["path"]:
                unchanged += 1
            else:
                manifest.add(record)
                added += 1
    print(f"repo={repo} commit={commit[:10]} added={added} unchanged={unchanged}")
    return 0


# ---------- door 3: a sitemap ----------
def sitemap_urls(client: httpx.Client, url: str, depth: int = 0) -> list[str]:
    response = client.get(url)
    response.raise_for_status()
    body = response.content
    if body[:2] == b"\x1f\x8b":  # gzip file (sitemap.xml.gz)
        body = gzip.decompress(body)
    root = ET.fromstring(body)
    locs = [el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text]
    if root.tag.endswith("sitemapindex") and depth < 2:  # a sitemap of sitemaps
        return [page for child in locs[:50] for page in sitemap_urls(client, child, depth + 1)]
    return locs


def cmd_sitemap(args: argparse.Namespace) -> int:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        try:
            found = sitemap_urls(client, args.url)
        except (httpx.HTTPError, ET.ParseError) as exc:
            print(f"could not read the sitemap: {exc}")
            return 1
    keep = [u for u in found if all(word in u for word in args.include)]
    keep = [u for u in keep if not any(word in u for word in args.exclude)]
    have: set[str] = set()
    if SOURCES.exists():
        have = {line.split(",")[0].strip() for line in SOURCES.read_text("utf-8-sig").splitlines()}
    new = [u for u in dict.fromkeys(keep) if u not in have]
    if args.limit:
        new = new[: args.limit]
    SOURCES.parent.mkdir(parents=True, exist_ok=True)
    first_time = not SOURCES.exists()
    with SOURCES.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if first_time:
            writer.writerow(HEADER)
        writer.writerows([u, args.source, args.licence, ""] for u in new)
    print(f"sitemap_urls={len(found)} matched={len(keep)} added_to_sources={len(new)}")
    return 0


# ---------- door 4: files you downloaded by hand ----------
def cmd_manual(args: argparse.Namespace) -> int:
    folder = args.folder.resolve()
    if not folder.is_dir() or not folder.is_relative_to(RAW.resolve()):
        print(f"put the files in a folder under {RAW.as_posix()}/ first, e.g. data/raw/my-source")
        return 1
    manifest = Manifest(MANIFEST)
    known = {record.get("path") for record in manifest.records.values()}
    added = 0
    for file in sorted(folder.rglob("*")):
        path = file.relative_to(Path.cwd())
        if not file.is_file() or file.name.startswith(".") or path.as_posix() in known:
            continue
        record = local_record(
            path,
            url=f"{args.from_url}#{file.name}",
            source=args.source,
            licence=args.licence,
            title=file.stem,
            via="manual",
        )
        manifest.add(record)
        added += 1
    print(f"folder={args.folder.as_posix()} added={added}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # odd characters never crash a Windows console
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    doors = parser.add_subparsers(dest="door", required=True)

    urls = doors.add_parser("urls", help="download every URL in data/sources.csv")
    urls.add_argument("--sources", type=Path, default=SOURCES)
    urls.add_argument(
        "--max-concurrency", type=int, default=4, help="downloads at once (default 4)"
    )
    urls.add_argument("--delay", type=float, default=0.5, help="seconds between hits on one site")
    urls.add_argument("--limit", type=int, default=0, help="only the first N sources")
    urls.set_defaults(run=cmd_urls)

    repo = doors.add_parser("repo", help="clone the folders you need from a GitHub repository")
    repo.add_argument("repo", help="OWNER/REPO, e.g. fastapi/fastapi")
    repo.add_argument("--path", action="append", required=True, help="folder in the repo (repeat)")
    repo.add_argument("--ext", action="append", required=True, help="file type to keep, e.g. .md")
    repo.add_argument("--source", required=True, help="short name, becomes data/raw/<source>/")
    repo.add_argument("--licence", required=True)
    repo.add_argument("--ref", default="", help="branch or tag (default: the default branch)")
    repo.set_defaults(run=cmd_repo)

    sitemap = doors.add_parser("sitemap", help="add a site's pages to data/sources.csv")
    sitemap.add_argument("url", help="e.g. https://example.org/sitemap.xml")
    sitemap.add_argument("--include", action="append", default=[], help="URL must contain this")
    sitemap.add_argument("--exclude", action="append", default=[], help="URL must not contain this")
    sitemap.add_argument("--limit", type=int, default=0)
    sitemap.add_argument("--source", required=True)
    sitemap.add_argument("--licence", required=True)
    sitemap.set_defaults(run=cmd_sitemap)

    manual = doors.add_parser("manual", help="register files you downloaded by hand")
    manual.add_argument("folder", type=Path, help="a folder under data/raw/")
    manual.add_argument("--from-url", required=True, help="the page you downloaded them from")
    manual.add_argument("--source", required=True)
    manual.add_argument("--licence", required=True)
    manual.set_defaults(run=cmd_manual)

    args = parser.parse_args()
    try:
        return args.run(args)
    except KeyboardInterrupt:
        print("\nStopped. Run the same command again: finished files are skipped.")
        return 130
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
