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

### 2. GitHub Actions

- Repository: https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate
- Actions: https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions
- CI run for pull request 1: (paste run link)
- First automatic deployment: (paste CD run link)
- Merge time: **__:__**
- Smoke test passed at: **__:__**
- Lead time: **___ minutes**

### 3. Smoke Test Output

```text
Paste the last four lines of the "Smoke test the live URL" step.
```

### 4. Rollback Drill

- Rolled back to SHA: __________
- Rollback started: **__:__**
- Smoke test passed: **__:__**
- Rollback duration: ___ minutes
- Rolled forward to SHA: __________
- Roll-forward duration: ___ minutes

**Why is rollback safe here?**

The rollback changes the application image without reversing database migrations. It is safe only because the older application remains compatible with the newer database schema.

### 5. Secrets Configuration

- `DATABASE_URL`: GitHub Actions secret and Render environment variable.
- `RENDER_DEPLOY_HOOK`: GitHub Actions secret only.
- `LIVE_URL`: GitHub Actions variable.

No secret values should be stored in Git or inside the Docker image.

### 6. Monitoring

- Monitoring service: UptimeRobot.
- Monitor URL: https://rti-mate.onrender.com/health
- Check interval: Every 5 minutes.
- Alert email: yuvaraj11j@gmail.com
- Current status: 502 Bad Gateway in North America.

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

- Files in the manifest: ___ · parsed: ___ · failed: ___ · pages in Postgres: ___
- Parsing coverage: ___ % of files

### Failures by reason

| Reason | Files | What I did |
|---|---|---|
| | | |

- The one I fixed: file ________ , reason ________ , fix: ________

### What I saw when I read my parsed pages

- A page where the heading path is right (document, page, path):
- Something that came out wrong (document, page, what):
- A table: Markdown grid or loose text? (document, page):

### My parser choice

- For PDFs I use ________ because (2 lines, with numbers from the table above):
- A kind of document in my corpus that neither parser handles well:

### One thing that went wrong today, and how I fixed it
