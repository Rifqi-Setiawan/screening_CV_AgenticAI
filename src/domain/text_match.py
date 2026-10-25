"""Text and skill matching utility with strict boundaries, negation detection, and disambiguation."""

from __future__ import annotations

import re

NEGATION_TERMS = {
    "tidak",
    "bukan",
    "belum",
    "tanpa",
    "kurang",
    "jangan",
    "tak",
    "tiada",
    "never",
    "not",
    "no",
    "lack",
    "except",
    "aside from",
    "without",
    "hardly",
    "barely",
}

# Words that need exact non-word boundary
SHORT_KEYWORDS_DISAMBIGUATION = {
    "c": r"(?<![a-zA-Z0-9_#+])c(?![a-zA-Z0-9_#+])",
    "r": r"(?<![a-zA-Z0-9_#+])r(?![a-zA-Z0-9_#+])",
    "go": r"(?<![a-zA-Z0-9_#+])go(?![a-zA-Z0-9_#+])",
    "sql": r"(?<![a-zA-Z0-9_#+])sql(?![a-zA-Z0-9_#+])",
    "java": r"(?<![a-zA-Z0-9_#+])java(?![a-zA-Z0-9_#+])",
}


def is_negated(text: str, match_start: int, window_words: int = 5) -> bool:
    """Checks if a match is preceded by a negation word within the preceding N words."""
    preceding_text = text[:match_start].strip()
    words = re.findall(r"\b[\w'-]+\b", preceding_text.lower())
    window = words[-window_words:] if len(words) >= window_words else words
    return any(neg in window for neg in NEGATION_TERMS)


def match_skill(text: str, skill_or_keyword: str) -> bool:
    """Matches a skill keyword within text with strict word boundaries and negation filtering.

    Returns True if matched and NOT negated.
    Returns False if not found or if negated or if ambiguous (e.g. java matching javascript).
    """
    if not text or not skill_or_keyword:
        return False

    kw = skill_or_keyword.strip().lower()

    # Disambiguation for specific collisions
    if (
        kw == "sql"
        and re.search(r"\bsqlite\b", text, re.IGNORECASE)
        and not re.search(r"(?<![\w])sql(?![\w])", text, re.IGNORECASE)
    ):
        return False

    if (
        kw == "java"
        and re.search(r"\bjavascript\b", text, re.IGNORECASE)
        and not re.search(r"(?<![\w])java(?![\w])", text, re.IGNORECASE)
    ):
        return False

    pattern = SHORT_KEYWORDS_DISAMBIGUATION.get(kw, rf"(?<![\w\-]){re.escape(kw)}(?![\w\-])")

    for m in re.finditer(pattern, text, re.IGNORECASE):
        start = m.start()
        if not is_negated(text, start):
            return True

    return False
