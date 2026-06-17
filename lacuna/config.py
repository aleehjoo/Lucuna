# lacuna/config.py
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def normalize_database_url(raw: str) -> str:
    """Normalize a pasted Supabase URL to the asyncpg driver scheme.

    - postgresql:// / postgres://  ->  postgresql+asyncpg://
    - strips libpq 'sslmode' (asyncpg uses connect_args ssl, not the query param)
    """
    if not raw or not raw.strip():
        raise ValueError("DATABASE_URL is empty — paste the Supabase Session Pooler string into .env")
    parts = urlsplit(raw.strip())
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+asyncpg":
        pass
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "sslmode"]
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    """Secrets from .env (never logged)."""
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    hardcover_api_token: str | None = Field(default=None, alias="HARDCOVER_API_TOKEN")
    google_books_api_key: str | None = Field(default=None, alias="GOOGLE_BOOKS_API_KEY")
    nyt_books_api_key: str | None = Field(default=None, alias="NYT_BOOKS_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_default() -> dict:
    return load_yaml("default.yaml")


def load_advanced() -> dict:
    return load_yaml("advanced.yaml")


def get_settings() -> Settings:
    return Settings()  # reads .env at call time
