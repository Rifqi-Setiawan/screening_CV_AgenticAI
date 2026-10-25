"""Candidate identity separation, redaction, and PII protection module."""

from __future__ import annotations

import re
from typing import Any

from src.domain.pii import DEMOGRAPHIC_LINE_REGEX, EMAIL_REGEX, PHONE_REGEX

DEMOGRAPHIC_PATTERNS = [
    re.compile(r"jenis\s+kelamin\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"gender\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"agama\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"religion\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"tanggal\s+lahir\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"date\s+of\s+birth\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"status\s*(?:pernikahan)?\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"marital\s+status\s*:\s*[^\n]+", re.IGNORECASE),
    re.compile(r"personal\s+details", re.IGNORECASE),
    re.compile(r"data\s+pribadi", re.IGNORECASE),
]


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


def extract_identity_and_redact(
    raw_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Separates identity PII into `identity_data` and returns `matching_profile` + `chunks`."""
    identity = raw_profile.get("identity", {})
    name = identity.get("full_name") or ""
    emails = [identity["email"]] if identity.get("email") else []
    phones = [identity["phone"]] if identity.get("phone") else []

    identity_record = {
        "full_name": name,
        "email": identity.get("email"),
        "phone": identity.get("phone"),
        "location_raw": identity.get("location_raw"),
        "links": identity.get("links", []),
        "other_personal": identity.get("other_personal", {}),
    }

    # Deep copy profile and strip identity block
    matching = {
        "document_id": raw_profile.get("document_id"),
        "headline": redact_text(raw_profile.get("headline", ""), name, emails, phones),
        "summary": redact_text(raw_profile.get("summary", ""), name, emails, phones),
        "language": raw_profile.get("language", ["id"]),
        "experiences": [],
        "education": [],
        "certifications": raw_profile.get("certifications", []),
        "skills": raw_profile.get("skills", []),
        "projects": [],
        "organizations": [],
        "portfolio_attachments": raw_profile.get("portfolio_attachments", []),
        "quality": raw_profile.get("quality", {}),
    }

    chunks: list[dict[str, Any]] = []

    # Experience entries
    for exp in raw_profile.get("experiences", []):
        redacted_bullets = []
        for b in exp.get("bullets", []):
            b_text = redact_text(b.get("text", ""), name, emails, phones)
            if b_text:
                redacted_bullets.append({**b, "text": b_text})

        redacted_exp = {
            **exp,
            "title": redact_text(exp.get("title", ""), name, emails, phones),
            "organization": redact_text(exp.get("organization", ""), name, emails, phones),
            "bullets": redacted_bullets,
        }
        matching["experiences"].append(redacted_exp)

        # Create chunk for experience
        bullet_combined = " ".join([b["text"] for b in redacted_bullets])
        chunk_text = f"{redacted_exp['title']} di {redacted_exp['organization']}: {bullet_combined}".strip()
        if chunk_text:
            chunks.append(
                {
                    "kind": "experience",
                    "entry_ref": exp.get("entry_id"),
                    "text_redacted": chunk_text,
                }
            )

    # Projects
    for prj in raw_profile.get("projects", []):
        prj_text = redact_text(prj.get("text", "") or prj.get("title", ""), name, emails, phones)
        matching["projects"].append({**prj, "title": prj_text, "text": prj_text})
        if prj_text:
            chunks.append(
                {
                    "kind": "project",
                    "entry_ref": prj.get("entry_id"),
                    "text_redacted": prj_text,
                }
            )

    # Organizations
    for org in raw_profile.get("organizations", []):
        org_text = redact_text(org.get("text", "") or org.get("title", ""), name, emails, phones)
        matching["organizations"].append({**org, "title": org_text, "text": org_text})
        if org_text:
            chunks.append(
                {
                    "kind": "organization",
                    "entry_ref": org.get("entry_id"),
                    "text_redacted": org_text,
                }
            )

    # Achievements
    matching["achievements"] = []
    for ach in raw_profile.get("achievements", []):
        ach_text = redact_text(ach.get("text", "") or ach.get("title", ""), name, emails, phones)
        matching["achievements"].append({**ach, "title": ach_text, "text": ach_text})
        if ach_text:
            chunks.append(
                {
                    "kind": "achievement",
                    "entry_ref": ach.get("entry_id"),
                    "text_redacted": ach_text,
                }
            )

    # Education
    for edu in raw_profile.get("education", []):
        edu_text = f"{edu.get('level', '')} {edu.get('degree_raw', '')} {edu.get('institution', '')}".strip()
        redacted_edu_text = redact_text(edu_text, name, emails, phones)
        matching["education"].append(
            {
                **edu,
                "institution": redact_text(edu.get("institution", ""), name, emails, phones),
            }
        )
        if redacted_edu_text:
            chunks.append(
                {
                    "kind": "education",
                    "entry_ref": edu.get("entry_id"),
                    "text_redacted": redacted_edu_text,
                }
            )

    # Skills list chunk
    skills_items = [s["name"] if isinstance(s, dict) else str(s) for s in matching.get("skills", [])]
    skills_text = ", ".join(skills_items)
    if skills_text:
        chunks.append(
            {
                "kind": "skills",
                "entry_ref": "skills_block",
                "text_redacted": f"Keahlian: {skills_text}",
            }
        )

    return identity_record, matching, chunks
