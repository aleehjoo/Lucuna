# tests/test_config.py
import pytest
from lacuna.config import normalize_database_url

@pytest.mark.parametrize("raw,expected", [
    # plain Supabase paste -> async driver scheme
    ("postgresql://postgres.ref:pw@aws-0-x.pooler.supabase.com:5432/postgres",
     "postgresql+asyncpg://postgres.ref:pw@aws-0-x.pooler.supabase.com:5432/postgres"),
    # short 'postgres://' alias also upgraded
    ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
    # already-correct scheme left intact
    ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
])
def test_normalize_scheme(raw, expected):
    assert normalize_database_url(raw) == expected

def test_sslmode_query_param_is_stripped():
    # asyncpg rejects libpq's sslmode; SSL is handled in connect_args instead.
    out = normalize_database_url("postgresql://u:p@h:5432/db?sslmode=require")
    assert "sslmode" not in out
    assert out.startswith("postgresql+asyncpg://")

def test_blank_url_raises():
    with pytest.raises(ValueError):
        normalize_database_url("")
