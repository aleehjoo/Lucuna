# scripts/pin_revisions.py
"""Resolve, validate, and pin Hugging Face dataset/model revisions (PRD §15).
Fails loud (SystemExit != 0) if any revision can't be resolved or verified.
Usage:  uv run python -m scripts.pin_revisions [--no-verify]
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
ADVANCED = ROOT / "config" / "advanced.yaml"
_api = HfApi()


def _model_sha(name: str) -> str | None:
    try:
        return _api.model_info(name).sha
    except Exception:
        return None


def _dataset_sha(name: str) -> str | None:
    try:
        return _api.dataset_info(name).sha
    except Exception:
        return None


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _verify_model_loads(name: str, revision: str) -> None:
    # Heavy: downloads weights to the local HF cache (one-time). Skipped with --no-verify.
    from transformers import AutoConfig
    try:
        AutoConfig.from_pretrained(name, revision=revision)
    except Exception as exc:  # noqa: BLE001
        _die(f"model {name}@{revision} failed to load: {exc}")


def pin(cfg_path: Path = ADVANCED, *, verify: bool = True) -> None:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    for key in ("embedding", "zero_shot"):
        node = cfg.get("models", {}).get(key)
        if not node:
            continue
        sha = _model_sha(node["name"])
        if not sha:
            _die(f"could not resolve revision for model {node['name']!r}")
        node["revision"] = sha
        if verify:
            _verify_model_loads(node["name"], sha)

    ds = cfg.get("dataset", {}).get("amazon_reviews")
    if ds:
        sha = _dataset_sha(ds["name"])
        if not sha:
            _die(f"could not resolve revision for dataset {ds['name']!r}")
        ds["revision"] = sha

    text = yaml.safe_dump(cfg, sort_keys=False)
    if "<resolved-at-build>" in text or "PINNED" in text:
        _die("placeholder revision text still present after pinning")
    cfg_path.write_text(text, encoding="utf-8")
    print("Pinned revisions:")
    print(text)


if __name__ == "__main__":
    pin(verify="--no-verify" not in sys.argv)
