"""Text hygiene for untrusted CV content: invisible characters, homoglyphs and injection phrases (v2.2).

Applies to text that will reach an LLM. It never edits the stored CV text; callers use the cleaned copy
only at the LLM boundary and use the flags for audit and Critic routing.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width, bidi-control, invisible formatting and tag characters.
_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿­᠎\U000e0000-\U000e007f]")
_BIDI = re.compile("[‎‏‪-‮⁦-⁩]")
_WORD = re.compile(r"\w+", re.UNICODE)

# Prompt-injection phrases (Indonesian + English) and chat-template markers.
_INJECTION: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pat, re.IGNORECASE))
    for name, pat in (
        (
            "IGNORE_PREVIOUS_EN",
            r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)",
        ),
        (
            "DISREGARD_EN",
            r"disregard\s+(?:all\s+|the\s+|any\s+)?(?:previous\s+)?(?:criteria|instructions?|rules?|requirements?)",
        ),
        (
            "ABAIKAN_ID",
            r"(?:abaikan|lupakan|kesampingkan)\s+(?:semua\s+|seluruh\s+)?(?:instruksi|perintah|aturan|kriteria|petunjuk)",
        ),
        (
            "SCORE_MAX_EN",
            r"(?:give|assign|rate|score)\s+(?:this\s+)?(?:candidate|applicant|resume|cv)?\s*(?:a\s+)?(?:score\s+of\s+|as\s+)?(?:100|10/10|perfect|maximum|highest)",
        ),
        ("SCORE_MAX_ID", r"(?:beri(?:kan)?|berikan|tetapkan)\s+(?:nilai|skor)\s+(?:100|sempurna|maksimal|tertinggi)"),
        (
            "RECOMMEND_EN",
            r"(?:strongly\s+)?(?:recommend|shortlist|hire|select|rank\s+first)\s+(?:this\s+)?(?:candidate|applicant)",
        ),
        (
            "RECOMMEND_ID",
            r"(?:rekomendasikan|loloskan|pilih|terima|peringkat\s+(?:pertama|teratas))\s+(?:kandidat|pelamar)\s+ini",
        ),
        ("ROLE_OVERRIDE", r"you\s+are\s+now\s+(?:an?\s+)?[a-z ]{0,30}(?:evaluator|assistant|judge|unconditional)"),
        (
            "SYSTEM_MARKER",
            r"(?:^|\n)\s*(?:system\s*prompt|system\s*:|\[system\]|<\|im_start\|>|<\|system\|>|###\s*instruction)",
        ),
        ("MODE_SWITCH", r"(?:evaluation\s+override\s+mode|developer\s+mode|dan\s+mode|jailbreak)"),
        (
            "OUTPUT_FORCE",
            r"(?:output|respond|answer|jawab)\s+(?:only|hanya|exactly|persis)\s+(?:with\s+)?[\"'{\[]?\s*(?:entailed|strong|shortlist|band\s*a)",
        ),
        ("UNCONDITIONAL", r"unconditional\s+acceptance|terima\s+tanpa\s+syarat"),
    )
)

_SCRIPT_OF = {"LATIN": "L", "CYRILLIC": "C", "GREEK": "G"}


def _script(ch: str) -> str | None:
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    for prefix, code in _SCRIPT_OF.items():
        if name.startswith(prefix):
            return code
    return None


def neutralize_control_chars(text: str) -> str:
    """Removes zero-width / bidi / tag characters and applies NFKC. Safe to apply before any LLM call."""
    if not text:
        return text
    return unicodedata.normalize("NFKC", _INVISIBLE.sub("", text))


def find_homoglyph_words(text: str, limit: int = 5) -> list[str]:
    """Words mixing Latin letters with Cyrillic/Greek lookalikes (e.g. 'Pythоn'), a stuffing/evasion trick."""
    found: list[str] = []
    for word in _WORD.findall(text or ""):
        scripts = {_script(c) for c in word} - {None}
        if "L" in scripts and scripts & {"C", "G"}:
            found.append(word)
            if len(found) >= limit:
                break
    return found


def scan_injection(text: str) -> list[str]:
    """Names of injection patterns found in `text` (after removing invisible characters)."""
    cleaned = neutralize_control_chars(text or "")
    return sorted({name for name, pat in _INJECTION if pat.search(cleaned)})


def hygiene_flags(text: str) -> list[str]:
    """Audit flags for a document text: invisible characters, bidi controls, homoglyphs, injection phrases."""
    flags: list[str] = []
    if not text:
        return flags
    if _INVISIBLE.search(text):
        flags.append("INVISIBLE_CHARS")
    if _BIDI.search(text):
        flags.append("BIDI_CONTROL")
    if find_homoglyph_words(text, limit=1):
        flags.append("HOMOGLYPH_MIX")
    if scan_injection(text):
        flags.append("PROMPT_INJECTION")
    return flags
