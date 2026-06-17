# lacuna/seed/normalization.py
"""Versioned title/author normalization (PRD §6.3). Bump NORM_VERSION to trigger
a full rebuild of affected works (handled by seed.py --rebuild)."""
from __future__ import annotations

import re

NORM_VERSION = 1

_SUBTITLE = re.compile(r":.*$")
_FORMAT_TOKENS = re.compile(
    r"\b(kindle|paperback|hardcover|audiobook|unabridged|abridged|illustrated|"
    r"edition|editions|volume|vol|book|series|reprint|annotated|deluxe)\b",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    t = (title or "").strip()
    t = _SUBTITLE.sub("", t)          # drop subtitle after first ':'
    t = t.lower()
    t = _PUNCT.sub(" ", t)            # punctuation -> space
    t = _FORMAT_TOKENS.sub(" ", t)    # remove format/series tokens
    t = _WS.sub(" ", t).strip()
    return t


def normalize_author(author: str | None) -> str:
    a = (author or "").strip().lower()
    a = _PUNCT.sub(" ", a)
    a = _WS.sub(" ", a).strip()
    return a


def author_surname(author: str | None) -> str:
    a = normalize_author(author)
    return a.split(" ")[-1] if a else ""


def normalized_key(title: str, author: str | None) -> str:
    return f"{normalize_title(title)}|{normalize_author(author)}"
