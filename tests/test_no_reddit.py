# tests/test_no_reddit.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ["lacuna", "app", "alembic", "scripts", "config"]

def _all_text():
    chunks = []
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".yaml", ".yml", ".ini", ".toml", ".mako"}:
                chunks.append((p, p.read_text(encoding="utf-8", errors="ignore").lower()))
    return chunks

def test_no_reddit_anywhere_in_source():
    hits = [str(p) for p, t in _all_text() if "reddit" in t]
    assert not hits, f"Reddit reference found in source: {hits}"

def test_no_docker_or_local_postgres_scaffolding():
    hits = [str(p) for p, t in _all_text()
            if "docker-compose" in t or "dockerfile" in t]
    assert not hits, f"Docker scaffolding found: {hits}"
