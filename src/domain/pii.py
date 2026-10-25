"""Unified PII and demographic patterns for redaction and policy enforcement."""

from __future__ import annotations

import re

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+62|62|08)[0-9\s-]{8,15}")

# Demographic line scrubbers matching full line
DEMOGRAPHIC_LINE_REGEX = re.compile(
    r"(?im)^.*?\b(?:tempat(?:[,\s]+(?:dan\s+|&\s*)?|\s+)tanggal\s+lahir|tanggal\s+lahir|tgl\s+lahir|ttl|date\s+of\s+birth|dob|born|lahir|jenis\s+kelamin|gender|sex|kelamin|agama|religion|status\s*(?:pernikahan)?|marital\s+status)\b.*$",
    re.MULTILINE,
)


def sanitize_contact_pii(text: str) -> str:
    """Replaces email and phone numbers with placeholders."""
    if not text:
        return ""
    res = EMAIL_REGEX.sub("[KONTAK_HR]", text)
    res = PHONE_REGEX.sub("[KONTAK_HR]", res)
    return res
