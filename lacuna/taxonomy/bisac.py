# lacuna/taxonomy/bisac.py
"""BISAC canonical spine. Ships a format validator + a small seed label map for the
example niches; the full BISAC catalog is proprietary, so the crosswalk learns the
rest (PRD §5/§9). Extend SEED_BISAC as needed."""
from __future__ import annotations

import re

_BISAC_RE = re.compile(r"^[A-Z]{3}\d{6}$")

# Seed subset (code -> canonical human label). Deliberately small; extended by learning.
SEED_BISAC: dict[str, str] = {
    "SEL036000": "Self-Help / Personal Growth / General",
    "SEL024000": "Self-Help / Motivational & Inspirational",
    "SEL027000": "Self-Help / Personal Growth / Success",
    "PHI011000": "Philosophy / Movements / Stoicism",
    "PHI000000": "Philosophy / General",
    "BUS019000": "Business & Economics / Decision-Making & Problem Solving",
    "PSY000000": "Psychology / General",
    "OCC011000": "Body, Mind & Spirit / Mindfulness & Meditation",
}


def is_valid_bisac(code: str) -> bool:
    return bool(code) and bool(_BISAC_RE.match(code))


def canonical_label(code: str) -> str | None:
    return SEED_BISAC.get(code)
