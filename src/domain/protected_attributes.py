"""Scrubbing of protected-attribute statements from text that reaches an LLM (v2.2).

The Matcher and Critic judge capability from evidence. Statements about religion, gender, age, marital status,
ethnicity, physical traits and home address are not evidence of capability and must not be visible to the
model as features. Names, e-mails and phone numbers are already redacted upstream (`redaction.py`); this module
covers the remaining demographic statements and obvious proxies (religious institution names, birth data).

It works on a copy used at the LLM boundary only: stored atoms and audit offsets are untouched.
"""

from __future__ import annotations

import re

PLACEHOLDER = "[ATTR]"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (cat, re.compile(pat, re.IGNORECASE))
    for cat, pat in (
        # labelled personal-data lines: "Tempat/Tanggal Lahir : ...", "Agama: ...", "Status: Menikah"
        (
            "BIRTH",
            r"\b(?:tempat\s*[/,]?\s*tanggal\s*lahir|tanggal\s*lahir|tempat\s*lahir|ttl|date\s*of\s*birth|dob|born)\b\s*[:\-]?\s*[^\n;|]{0,50}",
        ),
        (
            "AGE",
            r"\b(?:usia|umur|age)\s*[:\-]?\s*\d{1,2}(?:\s*(?:tahun|thn|years?|yo))?\b|\b\d{2}\s*(?:tahun|thn|years?)\s*(?:old)?\b(?=\s*[,;)|]|\s*$)",
        ),
        # "islam"/"islamic" alone is NOT scrubbed: it can be a domain skill (Islamic finance, syariah banking).
        (
            "RELIGION",
            r"\b(?:(?:ber)?agama|religion)\b\s*[:\-]?\s*[^\n;|,]{0,25}|\b(?:universitas|institut|sekolah|stai|uin|pesantren|madrasah)\s+(?:islam|kristen|katolik|muhammadiyah|nahdlatul)\b[^\n,;|]{0,30}|\b(?:muslim(?:ah)?|kristen|katolik|protestan|hindu|buddh?a|konghucu|berhijab|hijab|gereja|masjid|rohis|rohkris|pmk|pesantren)\b",
        ),
        (
            "GENDER",
            r"\b(?:jenis\s*kelamin|gender|sex)\s*[:\-]?\s*[^\n;|,]{0,15}|\b(?:laki[-\s]?laki|perempuan|pria|wanita|male|female)\b",
        ),
        (
            "MARITAL",
            r"\b(?:status\s*(?:pernikahan|perkawinan)?|marital\s*status)\s*[:\-]?\s*(?:belum\s*menikah|menikah|lajang|single|married|cerai|janda|duda)\b|\b(?:belum\s*menikah|menikah|lajang|married|divorced)\b",
        ),
        (
            "ETHNICITY",
            r"\b(?:suku|etnis|ethnicity|race|kewarganegaraan|nationality|warga\s*negara)\s*[:\-]?\s*[^\n;|,]{0,25}",
        ),
        (
            "PHYSICAL",
            r"\b(?:tinggi\s*badan|berat\s*badan|golongan\s*darah|height|weight|blood\s*type)\s*[:\-]?\s*[^\n;|,]{0,15}",
        ),
        ("ADDRESS", r"\b(?:alamat|domisili|address|residence)\s*[:\-]?\s*[^\n]{0,80}"),
    )
)


def scrub_protected_attributes(text: str) -> tuple[str, list[str]]:
    """Returns (`text` with protected-attribute statements replaced by a placeholder, categories found)."""
    if not text:
        return text, []
    found: list[str] = []
    out = text
    for category, pattern in _PATTERNS:
        out, n = pattern.subn(PLACEHOLDER, out)
        if n:
            found.append(category)
    out = re.sub(r"(?:\[ATTR\][\s,;:/|-]*){2,}", PLACEHOLDER + " ", out)
    return out.strip(), sorted(found)
