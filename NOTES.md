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
