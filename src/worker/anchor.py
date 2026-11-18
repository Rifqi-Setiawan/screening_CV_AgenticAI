"""Prefill candidate names from CV headers and email when available."""

from __future__ import annotations

import re

# Blacklist of job titles, roles, and professional headlines
ROLE_HEADLINE_PATTERNS = [
    re.compile(
        r"\b(?:software\s+engineer|full\s*stack|backend|frontend|web\s+developer|mobile\s+developer|devops|data\s+scientist|data\s+analyst|data\s+engineer|business\s+analyst|digital\s+marketing|marketing\s+specialist|civil\s+engineer|drafter|site\s+engineer|project\s+manager|product\s+manager|graphic\s+designer|ui/ux|content\s+creator|social\s+media|finance\s+staff|accounting|supervisor|technician|intern(?:ship)?|fresh\s+graduate)\b",
        re.IGNORECASE,
    ),
]

# Blacklist of academic institutions and organizations
INSTITUTION_PATTERNS = [
    re.compile(
        r"\b(?:universitas|university|univ|stmik|institut|institute|politeknik|polytechnic|sekolah\s+tinggi|fakultas|faculty|departemen|department|jurusan|program\s+studi|prodi|yayasan|foundation|sma|smk|smp|kemdikbud|dinas|kementerian)\b",
        re.IGNORECASE,
    ),
]

# Blacklist of section headers, formal greetings, and narrative phrases
NOISE_HEADER_PATTERNS = [
    re.compile(
        r"\b(?:tentang\s+saya|about\s+me|profile|profil|personal\s+background|curriculum\s+vitae|resume|biodata|hubungi|contact|phone|email|alamat|address|born\s+in|tempat(?:\s+dan)?\s+tanggal\s+lahir|ttl|ringkasan|summary|executive\s+summary|overview|objektif|objective)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:fresh\s+graduate|lulusan\s+baru|semangat\s+belajar|dengan\s+hormat|kepada\s+yth|dear\s+hiring|sehubungan\s+dengan|bersama\s+surat|surat\s+lamaran|hal\s*:)\b",
        re.IGNORECASE,
    ),
]


def clean_raw_name_string(raw: str) -> str:
    """Strips leading/trailing punctuation, colons, bullets, and excessive spaces."""
    s = re.sub(r"^[^\w\s]+", "", raw).strip()
    s = re.sub(r"[^\w\s\.\,\']+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def is_blacklisted_as_name(text: str) -> bool:
    """Returns True if the candidate name matches any job title, institution, or noise header."""
    clean = text.strip().lower()
    if not clean or len(clean) < 3:
        return True
    if any(p.search(clean) for p in ROLE_HEADLINE_PATTERNS):
        return True
    if any(p.search(clean) for p in INSTITUTION_PATTERNS):
        return True
    if any(p.search(clean) for p in NOISE_HEADER_PATTERNS):
        return True
    # If text is too long (> 45 chars) or too many words (> 5 words), it is likely a sentence
    words = clean.split()
    if len(words) > 5 or len(clean) > 45:
        return True
    # If text ends with a period, it is likely a sentence
    return bool(text.strip().endswith("."))


def extract_email_name_tokens(email: str | None) -> list[str]:
    """Extracts candidate name components from email local-part."""
    if not email or "@" not in email:
        return []
    local = email.split("@")[0].lower()
    # strip trailing numbers (e.g. 'yadi.apriyadi99' -> 'yadi.apriyadi')
    local = re.sub(r"\d+$", "", local)
    # split by dots, underscores, hyphens
    parts = re.split(r"[._\-+]+", local)
    return [p for p in parts if len(p) >= 3 and not p.isdigit()]


def resolve_candidate_name_consensus(
    extracted_name: str | None,
    full_text: str,
    email: str | None = None,
) -> str:
    """Prefer a plausible CV header, then look for a name in the document or email."""
    name_candidate = clean_raw_name_string(extracted_name or "")

    # If extracted name is valid and NOT blacklisted, check its quality
    if name_candidate and not is_blacklisted_as_name(name_candidate):
        # Additional check: multi-column duplicate e.g. 'Aryo B   Aryo Budi Hutomo'
        parts = re.split(r"\s{2,}|\n", name_candidate)
        if len(parts) >= 2:
            longest = max(parts, key=len).strip()
            if len(longest.split()) >= 2:
                name_candidate = longest
        name_candidate = re.sub(r"\s+", " ", name_candidate)

        return name_candidate

    # 3. Check Cover Letter self-intro: e.g. "Saya, Pijar Sulthan Muhammad" or "I am, ..."
    m_intro = re.search(
        r"(?:I\s+am|saya|nama\s+saya),?\s+([A-Z][A-Za-z\s]{2,35})(?:,|\s+excited|\s+bermaksud|\.|\s+ingin)",
        full_text,
    )
    if m_intro:
        cand = clean_raw_name_string(m_intro.group(1))
        if 2 <= len(cand.split()) <= 4 and not is_blacklisted_as_name(cand):
            return cand

    # 4. Scan the first 50 lines of full_text for candidate name lines that are NOT blacklisted
    lines = [clean_raw_name_string(l) for l in full_text.splitlines()[:50]]
    for line in lines:
        if not line or len(line) < 3:
            continue
        words = line.split()
        if (
            2 <= len(words) <= 4
            and not is_blacklisted_as_name(line)
            and all(w[0].isupper() or w.isupper() for w in words if w)
        ):
            return line.title()

    # 5. Fallback from Email local-part if informative
    email_tokens = extract_email_name_tokens(email)
    if len(email_tokens) >= 2:
        return " ".join(email_tokens[:3]).title()

    return ""
