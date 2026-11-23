"""Turn any Postgres URL (Neon, Supabase, local) into one asyncpg understands."""

from sqlalchemy.engine import make_url

SYNC_DRIVERS = {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}


def to_asyncpg_url(raw: str) -> str:
    url = make_url(raw)
    if url.drivername in SYNC_DRIVERS:
        url = url.set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)  # asyncpg rejects this option; TLS stays on via ssl
    if sslmode and sslmode != "disable":
        query["ssl"] = "require"
    return url.set(query=query).render_as_string(hide_password=False)
