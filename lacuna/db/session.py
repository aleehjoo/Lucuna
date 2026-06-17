# lacuna/db/session.py
from __future__ import annotations

import ssl

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from lacuna.config import get_settings


def build_ssl_context() -> ssl.SSLContext:
    """TLS for Supabase. Default: verify against the OS trust store (truststore),
    which handles public CAs and corporate roots installed at the OS level; falls
    back to certifi. Set LACUNA_DB_SSL_VERIFY=false to keep encryption but skip
    certificate verification — required on networks with a TLS-intercepting
    middlebox whose root is not installed in any trust store (still encrypted, but
    not authenticated; harden by supplying the Supabase CA cert instead)."""
    if not get_settings().database_ssl_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:  # pragma: no cover
        import certifi
        return ssl.create_default_context(cafile=certifi.where())


# Back-compat alias used by tests/older callers.
_ssl_context = build_ssl_context


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.async_database_url,
        connect_args={"ssl": build_ssl_context()},
        pool_pre_ping=True,
        echo=False,
    )


def build_sessionmaker(engine: AsyncEngine | None = None) -> async_sessionmaker:
    return async_sessionmaker(engine or build_engine(), expire_on_commit=False)
