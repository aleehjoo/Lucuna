# lacuna/db/session.py
from __future__ import annotations

import ssl

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from lacuna.config import get_settings


def _ssl_context() -> ssl.SSLContext:
    # Supabase requires TLS. The pooler presents a valid public cert, so the
    # default verifying context works.
    return ssl.create_default_context()


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.async_database_url,
        connect_args={"ssl": _ssl_context()},
        pool_pre_ping=True,
        echo=False,
    )


def build_sessionmaker(engine: AsyncEngine | None = None) -> async_sessionmaker:
    return async_sessionmaker(engine or build_engine(), expire_on_commit=False)
