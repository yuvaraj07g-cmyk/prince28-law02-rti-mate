# RTI Mate
**Live:** https://rti-mate.onrender.com
[![CI](https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions/workflows/ci.yml/badge.svg)](https://github.com/yuvaraj07g-cmyk/prince28-law02-rti-mate/actions/workflows/ci.yml)

Helps citizens write effective RTI applications and appeals, with the right authority, fees, time limits and Information Commission decisions cited.

**Status:** Week 1 foundation complete; public deployment pending Render configuration.

**Live:** Pending Render deployment. Add the live URL, API docs link, health link, and live/uptime badges after the service and UptimeRobot monitor are configured. The GitHub repository URL is not an application URL.

## Who it's for

Resident welfare association secretary in Tambaram who wants road-repair spending details from the municipality.

## The problem

People ask vague RTI questions, go to the wrong public authority or get rejected under exemptions, and don't know how commissions decided similar cases.

## Data sources

RTI Act 2005, RTI Rules 2012, Tamil Nadu RTI rules, DoPT RTI guides and FAQs, 1,000+ Central Information Commission decisions.

- https://cic.gov.in/
- https://rtionline.gov.in/
- https://rti.gov.in/
- Terms: Public law and decisions. Cite section or decision number.

## Hardest problem (my interview story)

Exemptions and jurisdiction: Section 8 exemptions decide many cases; answers must cite decisions correctly and tell central from state public authorities (a municipality goes to the State Information Commission).

## Signature feature

RTI builder: type what you want to know and get precise questions that avoid common exemptions, with the right authority.

## Target metric

Correct authority and time limits for 95%+ of 30 scenarios.

## Run it locally

```bash
uv sync
cp .env.example .env   # Windows: copy .env.example .env
uv run uvicorn rti_mate.api.main:create_app --factory --reload
```

Then open http://localhost:8000/docs

## Checks

```bash
uv run poe test
uv run poe lint
```

PostgreSQL integration tests use a dedicated test database. Start the Compose database
with `docker compose up -d db`, then run `uv run poe test-integration`. The integration
fixture creates a fresh database, applies migrations, and drops it after the run.
Without `TEST_DATABASE_URL`, the eight integration tests are skipped.

## Run locally in one command

You need Docker Desktop running. From a fresh clone:

```bash
docker compose up --build
```

This starts Postgres (with pgvector), Redis, runs the migrations and loads the sample data once, then starts the API.

- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health
- Readiness (checks the database): http://localhost:8000/ready

If port 8000 is already in use, set `$env:API_PORT = "8001"` in PowerShell before starting Compose, then use port 8001 for these URLs.

Stop with `Ctrl+C`, then `docker compose down`. Add `-v` to also delete the database volume.

## Develop and test

| Task | Mac / Linux | Windows |
|---|---|---|
| Run the API with reload | `make dev` | `uv run poe dev` |
| Unit tests (no network) | `make test` | `uv run poe test` |
| Integration tests (needs `docker compose up`) | `make test-integration` | `uv run poe test-integration` |
| Coverage report | `make cov` | `uv run poe cov` |
| Lint and format check | `make lint` | `uv run poe lint` |
