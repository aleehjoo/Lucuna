# tests/test_acceptance_static.py
"""Static slices of PRD §17 acceptance criteria runnable without credentials."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_uv_lock_and_pins_present():  # §17.13, §17.4
    assert (ROOT / "uv.lock").exists()
    adv = (ROOT / "config" / "advanced.yaml").read_text(encoding="utf-8")
    assert "<resolved-at-build>" not in adv and "PINNED" not in adv
    # three pinned revision sha hex strings present (2 models + 1 dataset)
    assert len(re.findall(r"\b[0-9a-f]{40}\b", adv)) >= 3


def test_no_docker_compose_file():  # §17.1 (no Docker)
    assert not (ROOT / "docker-compose.yml").exists()
    assert not (ROOT / "Dockerfile").exists()


def test_env_example_has_no_reddit_key():  # §17.12
    assert "reddit" not in (ROOT / ".env.example").read_text(encoding="utf-8").lower()
