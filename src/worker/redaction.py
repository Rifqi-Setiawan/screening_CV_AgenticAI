"""Candidate identity separation, redaction, and PII protection module."""

from __future__ import annotations

import re

from src.domain.pii import DEMOGRAPHIC_LINE_REGEX, EMAIL_REGEX, PHONE_REGEX

NON_NAME_WORDS = {
    "fresh",
    "graduate",
    "backend",
    "frontend",
    "developer",
    "engineer",
    "lead",
    "senior",
    "junior",
    "manager",
    "staff",
    "intern",
    "internship",
    "analyst",
    "fullstack",
    "specialist",
    "supervisor",
    "executive",
    "pt",
    "cv",
    "indonesia",
    "jakarta",
    "bandung",
    "surabaya",
}


def redact_text(text: str, name: str = "", emails: list[str] | None = None, phones: list[str] | None = None) -> str:
    if not text:
        return ""
    result = text

    # Remove all demographic lines completely
    result = DEMOGRAPHIC_LINE_REGEX.sub("", result)

    # Redact known emails and general emails first to avoid token fragmentation
    if emails:
        for em in emails:
            if em:
                result = re.sub(re.escape(em), "[EMAIL]", result, flags=re.IGNORECASE)
    result = EMAIL_REGEX.sub("[EMAIL]", result)

    # Redact known phones and general phones
    if phones:
        for ph in phones:
            if ph:
                clean_ph = ph.strip()
                result = re.sub(re.escape(clean_ph), "[TELEPON]", result)
    result = PHONE_REGEX.sub("[TELEPON]", result)

    # Redact specific name tokens if provided (filtering out common role words)
    if name:
        tokens = [t.strip() for t in name.split() if len(t.strip()) > 2 and t.lower() not in NON_NAME_WORDS]
        for t in sorted(tokens, key=len, reverse=True):
            result = re.sub(rf"\b{re.escape(t)}\b", "[NAMA]", result, flags=re.IGNORECASE)

    # Clean redundant whitespace
    result = re.sub(r"\n\s*\n\s*\n+", "\n\n", result).strip()
    return result
