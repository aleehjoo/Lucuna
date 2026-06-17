# tests/test_gitignore.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_gitignore_excludes_secrets():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for needed in (".env", ".claude.json"):
        assert needed in text, f"{needed} must be git-ignored"

def test_env_example_is_not_ignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!.env.example" in text
