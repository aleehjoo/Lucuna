# tests/test_gitignore.py
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_gitignore_excludes_secrets():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for needed in (".env", ".claude.json"):
        assert needed in text, f"{needed} must be git-ignored"

def test_env_example_is_ignored():
    """Security policy (post-incident): .env.example was leaked with real keys, so
    it is now an untracked, local-only placeholder template — git must ignore it."""
    result = subprocess.run(
        ["git", "check-ignore", ".env.example"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0 and ".env.example" in result.stdout, (
        ".env.example must be git-ignored (no real secrets, never tracked)")
