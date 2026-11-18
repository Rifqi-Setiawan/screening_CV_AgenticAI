"""Screen untrusted application form text for prompt injection."""

from __future__ import annotations

import re
import unicodedata

# Zero-width, bidi-control, invisible formatting and tag characters.
_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿­᠎\U000e0000-\U000e007f]")

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
            # Requires a candidate/score object so that "give 100% effort" is not flagged.
            "SCORE_MAX_EN",
            r"\b(?:give|assign|rate|score)\s+(?:this|the)\s+(?:candidate|applicant|resume|cv)\s+(?:a\s+)?"
            r"(?:score\s+(?:of\s+)?|as\s+)?(?:100|10/10|perfect|maximum|highest)\b"
            r"|\b(?:give|assign)\s+(?:me\s+|it\s+)?(?:a\s+)?(?:score|rating)\s+(?:of\s+)?(?:100|10/10|perfect|maximum|highest)\b",
        ),
        ("SCORE_MAX_ID", r"(?:beri(?:kan)?|berikan|tetapkan)\s+(?:nilai|skor)\s+(?:100|sempurna|maksimal|tertinggi)"),
        (
            # "Hire candidates for engineering teams" is ordinary recruiter work, so a demonstrative is required.
            "RECOMMEND_EN",
            r"\b(?:strongly\s+)?(?:recommend|shortlist|hire|select|rank\s+first)\s+(?:this|the\s+following)\s+"
            r"(?:candidate|applicant)\b",
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
        # "dan mode" is not matched: "dan" is the Indonesian word for "and" ("tren fashion dan mode").
        (
            "MODE_SWITCH",
            r"evaluation\s+override\s+mode|\b(?:enable|enter|activate|switch\s+to)\s+(?:developer|god|admin)\s+mode\b"
            r"|\bjailbreak\s+(?:mode|prompt|the\s+(?:model|ai|assistant))\b",
        ),
        (
            "OUTPUT_FORCE",
            r"(?:output|respond|answer|jawab)\s+(?:only|hanya|exactly|persis)\s+(?:with\s+)?[\"'{\[]?\s*(?:entailed|strong|shortlist|band\s*a)",
        ),
        ("UNCONDITIONAL", r"unconditional\s+acceptance|terima\s+tanpa\s+syarat"),
    )
)


def neutralize_control_chars(text: str) -> str:
    """Removes zero-width / bidi / tag characters and applies NFKC. Safe to apply before any LLM call."""
    if not text:
        return text
    return unicodedata.normalize("NFKC", _INVISIBLE.sub("", text))


def scan_injection(text: str) -> list[str]:
    """Names of injection patterns found in `text` (after removing invisible characters)."""
    cleaned = neutralize_control_chars(text or "")
    return sorted({name for name, pat in _INJECTION if pat.search(cleaned)})
