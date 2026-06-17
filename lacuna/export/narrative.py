# lacuna/export/narrative.py
"""Optional Anthropic narrative (PRD §12). Disabled when no key; only ever sees the
already-aggregated pack (never raw review text)."""
from __future__ import annotations

from collections.abc import Callable


def _default_caller(api_key: str, pack: dict) -> str:  # pragma: no cover
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=600,
        messages=[{"role": "user", "content":
                   "These are aggregated, anonymized market-gap candidates (no raw reviews). "
                   "Write a brief, skeptical analyst summary treating each as a hypothesis:\n"
                   + str(pack["candidates"])}],
    )
    return msg.content[0].text


def maybe_add_narrative(pack: dict, *, api_key: str | None,
                        _caller: Callable[[str, dict], str] = _default_caller) -> dict:
    if not api_key:
        return pack
    pack["narrative"] = _caller(api_key, pack)
    return pack
