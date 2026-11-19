# Engineering notes: RTI Mate

## D03 - PostgreSQL

### Migrations

Run the following commands on the configured database:

```text
uv run alembic downgrade -1
uv run alembic current
uv run alembic upgrade head
uv run alembic history
```

The migration chain contains:

```text
<base> -> 001 (create documents and pages) -> 002 (add GIN index) (head)
```

### Loader is idempotent

```text
run 1: uv run python scripts/load_db.py
run 2: uv run python scripts/load_db.py
run 3: edit one JSON value, then uv run python scripts/load_db.py
```

Use SHA-256 fingerprints of canonical JSON records to distinguish inserted, updated, and unchanged records.

### EXPLAIN

```text
uv run python scripts/explain.py <field> <value>
```

On a small table, PostgreSQL may choose a Sequential Scan because reading all 20 rows is cheaper than an index lookup. As the table grows or a selective filter is used, the planner can switch to `ix_documents_metadata_gin`, using the JSONB GIN index with `jsonb_path_ops`.

## D04 · Docker, Compose and tests

### The image

```text
$ docker images rti_mate:dev
IMAGE          ID             DISK USAGE   CONTENT SIZE   EXTRA
rti_mate:dev   e9208fd168f0        300MB           70MB

$ docker run --rm rti_mate:dev id
uid=999(app) gid=999(app) groups=999(app)
```

- Size: 70 MB content size (300 MB local disk usage), under the 400 MB target.
- Clean-clone BuildKit image export took 69.9 s; total build and one-line incremental rebuild were not timed separately.
- `COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/` was cached because the pinned builder image had not changed.

### The stack

```text
$ docker compose ps -a
rti_mate-api-1       Up (healthy)     8000/tcp (not published to host)
rti_mate-db-1        Up (healthy)     5433->5432
rti_mate-migrate-1   Exited (0)
rti_mate-redis-1     Up (healthy)     6379->6379

The unrelated `demo_api` container owns host port 8000, so RTI Mate was checked on port 8001.
The migration service logged: records=20 inserted=15 updated=0 unchanged=5
Idempotent rerun: records=20 inserted=0 updated=0 unchanged=20
```

### Breaking the database on purpose

```text
Checked on port 8001 because port 8000 was occupied:
db stopped:  /health → HTTP 200 {"status":"ok"}
db stopped:  /ready  → HTTP 503 {"status":"not ready","checks":{"database":false}}
db started:  /ready  → HTTP 200 {"status":"ready","checks":{"database":true}}
```

A load balancer should stop routing to an instance that cannot reach its database.
Restarting the app will not fix the dependency; readiness recovers when the database returns.

### Tests and coverage

```text
uv run poe test              → 13 passed
uv run poe test-integration  → 7 passed
coverage TOTAL, unit only    → 81% (13 passed, 7 skipped)
coverage TOTAL, with integration tests → 93% (20 passed)
```

`api/errors.py:3-8` has 0% coverage and no callers; it currently has no runtime effect.
`db/repository.py:15` is an uncalled filter helper; it has no runtime effect until wired into validation.
