"""Unified PII and demographic patterns for redaction and policy enforcement."""

from __future__ import annotations

import re

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# The lookbehind keeps year ranges such as "2008 - 2012 - 2015" from looking like a phone number.
PHONE_REGEX = re.compile(r"(?<![\d.,])(?:\+62|62|08)[0-9\s-]{8,15}")

# Whole labelled personal-data lines ("Agama: ...", "Gender: ..."). A separator is required so that
# ordinary work text such as "Kementerian Agama" or "Gender-responsive budgeting" is kept.
DEMOGRAPHIC_LINE_REGEX = re.compile(
    r"(?im)^.*?\b(?:tempat(?:[,\s/]+(?:dan\s+|&\s*)?|\s+)tanggal\s+lahir|tanggal\s+lahir|tgl\.?\s+lahir|lahir|ttl"
    r"|date\s+of\s+birth|dob|born|jenis\s+kelamin|kelamin|gender|sex|agama|religion"
    r"|status\s+(?:pernikahan|perkawinan)|marital\s+status)\s*[:=].*$"
    r"|^.*?\bstatus\s*[:=]\s*(?:belum\s+menikah|menikah|lajang|single|married|divorced|cerai|janda|duda)\b.*$",
)


def sanitize_contact_pii(text: str) -> str:
    """Replaces email and phone numbers with placeholders."""
    if not text:
        return ""
    res = EMAIL_REGEX.sub("[KONTAK_HR]", text)
    res = PHONE_REGEX.sub("[KONTAK_HR]", res)
    return res
