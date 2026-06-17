# lacuna/seed/works_grouping.py
"""3-pass works grouping (PRD §6.3): parent_asin -> normalized_key -> trigram tie-break."""
from __future__ import annotations

from dataclasses import dataclass, field

from lacuna.seed.normalization import author_surname, normalize_title, normalized_key


@dataclass
class EditionInput:
    asin: str
    parent_asin: str | None
    title: str
    author: str | None


@dataclass
class WorkGroup:
    normalized_key: str
    title: str
    author: str | None
    members: list[EditionInput] = field(default_factory=list)
    flagged: bool = False  # tie-break uncertainty


def _trigrams(s: str) -> set[str]:
    s = f"  {s} "
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}


def trigram_similarity(a: str, b: str) -> float:
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def group_editions(editions: list[EditionInput], *, trigram_threshold: float = 0.6) -> list[WorkGroup]:
    # Pass 1: group by shared parent_asin (fallback to own asin when parent missing).
    by_parent: dict[str, list[EditionInput]] = {}
    for ed in editions:
        key = ed.parent_asin or f"__solo__{ed.asin}"
        by_parent.setdefault(key, []).append(ed)

    # Build provisional groups, each keyed by the normalized_key of its first member.
    provisional: list[WorkGroup] = []
    for members in by_parent.values():
        head = members[0]
        provisional.append(WorkGroup(
            normalized_key=normalized_key(head.title, head.author),
            title=head.title, author=head.author, members=list(members),
        ))

    # Pass 2: merge provisional groups sharing an identical normalized_key.
    merged: dict[str, WorkGroup] = {}
    leftovers: list[WorkGroup] = []
    for grp in provisional:
        if grp.normalized_key in merged:
            merged[grp.normalized_key].members.extend(grp.members)
        else:
            merged[grp.normalized_key] = grp
    candidates = list(merged.values())

    # Pass 3: attempt cross-key merges only when title trigram sim >= threshold
    # AND author surname matches exactly; otherwise keep separate (flag if surname
    # matched but trigram failed — the ambiguous case).
    result: list[WorkGroup] = []
    for grp in candidates:
        placed = False
        for existing in result:
            same_surname = author_surname(grp.author) == author_surname(existing.author) and author_surname(grp.author) != ""
            sim = trigram_similarity(normalize_title(grp.title), normalize_title(existing.title))
            if same_surname and sim >= trigram_threshold:
                existing.members.extend(grp.members)
                placed = True
                break
            if same_surname and sim > 0:
                grp.flagged = True  # ambiguous: same author, partial title overlap
        if not placed:
            result.append(grp)
    return result
