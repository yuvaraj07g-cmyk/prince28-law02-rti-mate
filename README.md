# RTI Mate

Helps citizens write effective RTI applications and appeals, with the right authority, fees, time limits and Information Commission decisions cited.

**Status:** Day 1 foundation (FastAPI skeleton, quality gates). Live URL from Day 5.

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
uv run pytest
uv run ruff check .
```
