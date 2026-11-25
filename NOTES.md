# Engineering Notes: RTI Mate

## D03 – PostgreSQL

### 1. Migrations

Run the following commands on the configured database:

```text
uv run alembic downgrade -1
uv run alembic current
uv run alembic upgrade head
uv run alembic history
```

Migration chain:

```text
<base> → 001 (create documents and pages) → 002 (add GIN index) → head
```

### 2. Idempotent Data Loader

```text
Run 1: uv run python scripts/load_db.py
Run 2: uv run python scripts/load_db.py
Run 3: Edit one JSON value, then run the loader again.
```

Use SHA-256 fingerprints of canonical JSON records to distinguish inserted, updated, and unchanged records.

### 3. EXPLAIN

```text
uv run python scripts/explain.py <field> <value>
```

On a small table, PostgreSQL may choose a Sequential Scan because reading all 20 rows is cheaper than an index lookup. As the table grows or a selective filter is used, the planner can switch to `ix_documents_metadata_gin`, using the JSONB GIN index with `jsonb_path_ops`.

## D04 – Docker, Compose and Tests

### 1. Docker Image

```text
$ docker images rti_mate:dev
IMAGE=rti_mate TAG=dev ID=17f5cddd3720 SIZE=300MB

$ docker run --rm rti_mate:dev id
uid=999(app) gid=999(app) groups=999(app)
```

- Image content size: 70,025,496 bytes.
- Docker Desktop disk usage: 300 MB.
- Both are under the 400 MB target.
- Initial build: 65.3 seconds.
- Cached rebuild: 15.6 seconds.
- Pinned uv, dependency-install and application-copy layers were cached.

### 2. Docker Compose Stack

```text
rti_mate_validation-api-1       Up (healthy)    8001->8000
rti_mate_validation-db-1        Up (healthy)    5433->5432
rti_mate_validation-migrate-1   Exited (0)
rti_mate_validation-redis-1     Up (healthy)    6379
```

The unrelated `demo_api` container owns host port 8000, so RTI Mate was checked on port 8001.

First migration/seed:

```text
records=20 inserted=20 updated=0 unchanged=0
```

Idempotent rerun:

```text
records=20 inserted=0 updated=0 unchanged=20
```

### 3. Health and Readiness Testing

```text
Database stopped:
  /health → HTTP 200
  /ready  → HTTP 503

Database started:
  /ready  → HTTP 200
```

A load balancer should stop routing to an instance that cannot reach its database. Readiness recovers when the database returns.

### 4. Tests and Coverage

```text
uv run poe test              → 17 passed
uv run poe test-integration  → 8 passed

Unit coverage: 85%
Combined coverage: 96% (25 passed)
```

## D05 – CI/CD and Going Live

### 1. Live Deployment

- Live URL: https://rti-mate.onrender.com
- Hosting: Render
- Database: Neon PostgreSQL
- Environment: Production
- Verified 2026-11-25: `/health` returned 200 with version `30e297c5f5a042acb5bf997fa3600cf0e7b84a2a`; `/ready` returned 200 with the database check true; `/v1/documents?limit=1` returned 200.
- The running version is older than current `main` (`3aff0c8d2e955b234fb95873a601239fd6d7adb6`); the latest CD run did not deploy.

### 2. GitHub Actions

- Repository: https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate
- Actions: https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions
- Latest CI run on `main`: [run 32](https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions/runs/45577768540), passed.
- Latest CD run: [run 9](https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions/runs/45578036785), failed during the Neon migration.
- Last successful CD run: [run 6](https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions/runs/45357047967), deployed version `30e297c5f5a042acb5bf997fa3600cf0e7b84a2a`.

### 3. Smoke Test Output

```text
ok   /health -> 200, version 30e297c5f5a042acb5bf997fa3600cf0e7b84a2a
ok   /ready -> 200 {'status': 'ready', 'checks': {'database': True}}
ok   /v1/documents?limit=1 -> 200
Smoke test passed
```

### 4. Rollback Drill

Not performed. The deployment pipeline is currently blocked before the deploy step, so a rollback drill cannot be recorded as completed. After resolving the migration state, run the CD workflow manually with a known-good older image SHA, verify the smoke test, then run it again with the current `main` SHA and record both run links and durations here.

The latest migration attempt stopped because Neon already contains the `parse_failures` relation when Alembic revision `bd594d9d26b8` tried to create it. Verify the database schema and `alembic_version` before any stamp or schema change; no production database objects were changed by this investigation.

**Why is rollback safe here?**

The rollback changes the application image without reversing database migrations. It is safe only because the older application remains compatible with the newer database schema.

### 5. Secrets Configuration

- `DATABASE_URL`: GitHub Actions secret and Render environment variable.
- `RENDER_DEPLOY_HOOK`: GitHub Actions secret only.
- `LIVE_URL`: GitHub Actions variable.
- The migration job reached Neon, confirming the database connection is available. The latest CD run stopped before invoking the Render deploy hook; verify the hook on the next successful migration/deploy run.

No secret values should be stored in Git or inside the Docker image.

### 6. Monitoring

- Monitoring service: UptimeRobot.
- Monitor URL: https://rti-mate.onrender.com/health
- Check interval: Every 5 minutes.
- Alert email: yuvaraj11j@gmail.com
- Current endpoint check (2026-11-25): `/health` returned HTTP 200. The README health badge monitors this endpoint; confirm the UptimeRobot dashboard separately for monitor history and alert delivery.

**One improvement for faster first requests:** Use an always-on hosting service or paid plan to avoid cold starts.

## D06 · Collecting the corpus

- Start target: Act + rules + guides + 200 decisions
- Collected today: 13 files, 397 pages, 11.4 MB (from DATASET.md)
- Doors used: URL list and by hand (the three original PDFs were registered manually)

### Licence check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| dopt | Official government material; no collection-wide reuse licence verified. Keep attribution and verify document terms. | No; use only necessary excerpts until terms are confirmed. |
| rtionline | The [RTI Online Copyright Policy](https://rtionline.gov.in/Policies.php) allows accurate reproduction with prominent attribution, except third-party material. | Only if the specific material is not marked third-party and attribution is included. |
| kerala-rti | Government publication; reuse terms not independently verified. | No; use only necessary excerpts until terms are confirmed. |
| tamil-nadu-rti | Government of Tamil Nadu material; reuse terms not independently verified. | No; use only necessary excerpts until terms are confirmed. |

### robots.txt

- Checked the five source hosts: `rti.dopt.gov.in`, `documents.doptcirculars.nic.in`,
  `rti.img.kerala.gov.in`, `rtionline.gov.in` and `www.tn.gov.in`.
- Each `robots.txt` check returned 404 (no published directives); the downloader reported
  `blocked=0` for the ten URL sources. Recheck before adding new hosts.

### Resume check (non-destructive)

- I did not clear `data/raw/` or the manifest, or interrupt a production download; existing files
  were kept.
- Re-running the URL list reported `downloaded=0 skipped=10`.
- The isolated unit test `test_resume_fetches_only_what_is_missing` verifies that a partial set is
  skipped and only missing files are fetched.

### Capacity (from docs/CAPACITY.md)

- Tokens per page, estimated: 433 (characters divided by four; not a tokenizer measurement).
- Full corpus: 3.46 M estimated tokens, 9,960 chunks, about Rs 57 to embed, and 31 MB of vectors.
- The estimate is a planning baseline; PDF text and tokenization can differ from the sample.

### One thing that went wrong today, and how I fixed it
The source list was accidentally reduced to a fragment, causing a CSV URL validation error. I
restored the ten complete rows and verified that all ten were already downloaded and safely skipped.

## D07 · Parser comparison

<!-- parsers:start -->
| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |
|---|---|---|---|---|---|---|
| rtiactmarathi-6a26e5a9.pdf | PyMuPDF / pypdf | - | FAILED: no_text_layer | FAILED: no_text_layer | 5.36 s / 0.06 s | Neither: scanned; needs OCR |
| RTI_Online_User_Manual.pdf | PyMuPDF / pypdf | 29 | 8,729 chars, 37 headings, 0 tables | 8,525 chars, 0 headings, 0 tables | 0.67 s / 0.37 s | PyMuPDF: 37 headings vs 0, similar text |
| guidebook-rtiact-383e7792.pdf | PyMuPDF / pypdf | 37 | 50,511 chars, 16 headings, 19 tables | 46,890 chars, 0 headings, 0 tables | 7.28 s / 2.44 s | PyMuPDF finds tables; Tamil glyphs remain garbled |
| RTI_Act_2005.pdf | PyMuPDF / pypdf | 23 | 68,240 chars, 103 headings, 0 tables | 67,488 chars, 0 headings, 0 tables | 6.69 s / 0.31 s | PyMuPDF exposes section headings; some masthead noise |
| rti-act-c88215d2.pdf | PyMuPDF / pypdf | 23 | 68,240 chars, 103 headings, 0 tables | 67,488 chars, 0 headings, 0 tables | 6.18 s / 0.19 s | PyMuPDF exposes section headings; some masthead noise |
| rti-actinhindi-6e482adb.pdf | PyMuPDF / pypdf | 27 | 54,533 chars, 913 headings, 0 tables | 51,243 chars, 1 headings, 0 tables | 4.27 s / 0.71 s | pypdf: PyMuPDF over-tags lines as headings |
| rtiact-kannada-45ae87cf.pdf | PyMuPDF / pypdf | 30 | 73,878 chars, 0 headings, 0 tables | 74,460 chars, 0 headings, 0 tables | 0.19 s / 0.36 s | Neither: Kannada glyphs are garbled in both |
| rti-act-2005-gujarati-383159c1.pdf | PyMuPDF / pypdf | 77 | 157,808 chars, 74 headings, 15 tables | FAILED: corrupt | 2.40 s / 0.15 s | PyMuPDF: extracts 15 tables; pypdf fails |
| rti-rules-2019-036c0d50.pdf | PyMuPDF / pypdf | 7 | 27,220 chars, 20 headings, 0 tables | 32,847 chars, 0 headings, 0 tables | 1.57 s / 1.31 s | PyMuPDF: headings; pypdf has more text but no structure |
| RTI_Act_2005_Amended.pdf | PyMuPDF / pypdf | 25 | 69,731 chars, 1 headings, 0 tables | 69,358 chars, 0 headings, 0 tables | 0.37 s / 1.19 s | PyMuPDF: one heading and similar text, faster |
<!-- parsers:end -->

### D07 · Parsing my corpus

- Files in the manifest: 16 · parsed: 13 unique documents (15 entries including duplicates) · failed: 1 · pages in Postgres: 321
- Parsing coverage: 93% of unique content (13/14); 94% of manifest entries (15/16)

### Failures by reason

| Reason | Files | What I did |
|---|---|---|
| `no_text_layer` | 1 | Scanned Marathi PDF; preserve it and find a Unicode copy or OCR it |

- The one I fixed: none. `data/raw/dopt/rtiactmarathi-6a26e5a9.pdf` has no text layer on 31 pages; OCR needs Tesseract, which is not installed here. The original file and recorded failure are preserved.

### What I saw when I read my parsed pages

- A useful heading path: *User Manual*, page 3, `["(RTI)", "Citizen Module"]`, before the submit instructions.
- Something that came out wrong: Tamil in the Tamil Nadu guidebook and Kannada in the DOPT PDF are garbled by legacy font encodings.
- A table: the Tamil Nadu guidebook, page 4, is a Markdown grid (though its Tamil cell text is garbled).

### My parser choice

- For PDFs I use PyMuPDF by default: it finds 19 tables and 16 headings in the Tamil Nadu guidebook, and 103 headings in the English Act; pypdf finds none of those structures. It is slower, and pypdf avoids PyMuPDF's Hindi heading over-detection (913 vs 1).
- Neither parser handles image-only scans or legacy-font Tamil/Kannada well; those need OCR or a Unicode source.

### One thing that went wrong today, and how I fixed it

The Marathi scan has no extractable text. I left the raw PDF untouched and recorded `no_text_layer`; without Tesseract or a Unicode replacement, it remains an explicit corpus failure rather than pretending it parsed.
