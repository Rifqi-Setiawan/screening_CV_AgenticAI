"""Remove protected attributes from free text before AI assessment.

Labels in English are short words that also appear in ordinary work text ("address", "weight",
"race condition", "gender-responsive"), so they are only scrubbed when followed by a separator such as
"Address: ...". Indonesian labels such as "alamat" or "berat badan" are unambiguous and may stand alone.
Institution names that contain a religious word ("Universitas Islam Indonesia") are kept intact because
TIG compares campus names with the campus tier list.
"""

from __future__ import annotations

import re

PLACEHOLDER = "[ATTR]"
_SEP = r"\s*[:=]\s*"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (cat, re.compile(pat, re.IGNORECASE))
    for cat, pat in (
        (
            "BIRTH",
            r"\b(?:tempat\s*[/,]?\s*(?:dan\s+)?tanggal\s*lahir|tanggal\s*lahir|tgl\.?\s*lahir|tempat\s*lahir|ttl)\b"
            r"\s*[:=\-]?\s*[^\n;|]{0,50}"
            rf"|\b(?:date\s*of\s*birth|dob|born){_SEP}[^\n;|]{{0,50}}",
        ),
        (
            "AGE",
            r"\b(?:usia|umur)\b\s*[:=\-]?\s*\d{1,2}(?:\s*(?:tahun|thn))?\b"
            rf"|\bage{_SEP}\d{{1,2}}(?:\s*(?:years?|yo|tahun))?\b"
            r"|\bberusia\s*\d{1,2}\s*(?:tahun|thn)\b"
            r"|\b\d{1,2}\s*(?:years?|yrs?)\s*old\b",
        ),
        (
            "RELIGION",
            # "Kementerian Agama" is an employer, so "agama" needs a separator; "beragama Islam" does not.
            rf"\b(?:agama|religion){_SEP}[^\n;|,]{{0,25}}"
            r"|\bberagama\s+\w+"
            r"|\b(?:muslim(?:ah)?|kristen|katolik|protestan|hindu|buddh?a|konghucu|berhijab|hijab|gereja|masjid"
            r"|rohis|rohkris|pesantren)\b",
        ),
        (
            "GENDER",
            r"\bjenis\s*kelamin\b\s*[:=\-]?\s*[^\n;|,]{0,15}"
            rf"|\b(?:gender|sex){_SEP}[^\n;|,]{{0,15}}"
            r"|\b(?:laki[-\s]?laki|perempuan|pria|wanita|male|female)\b",
        ),
        (
            "MARITAL",
            r"\b(?:status\s*(?:pernikahan|perkawinan)?|marital\s*status)\s*[:=\-]?\s*"
            r"(?:belum\s*menikah|menikah|lajang|single|married|divorced|cerai|janda|duda)\b"
            r"|\b(?:belum\s*menikah|sudah\s*menikah|lajang|married|divorced)\b",
        ),
        (
            "ETHNICITY",
            r"\b(?:suku|etnis|kewarganegaraan|warga\s*negara)\b\s*[:=\-]?\s*[^\n;|,]{0,25}"
            rf"|\b(?:ethnicity|race|nationality){_SEP}[^\n;|,]{{0,25}}",
        ),
        (
            "PHYSICAL",
            r"\b(?:tinggi\s*badan|berat\s*badan|golongan\s*darah)\b\s*[:=\-]?\s*[^\n;|,]{0,15}"
            rf"|\b(?:height|weight|blood\s*type){_SEP}[^\n;|,]{{0,15}}",
        ),
        (
            "ADDRESS",
            r"\balamat\s+(?:rumah|lengkap|tinggal|ktp)\b\s*[:=\-]?\s*[^\n]{0,80}"
            rf"|\b(?:alamat|address|residence){_SEP}[^\n]{{0,80}}",
        ),
    )
)

# Institution names are protected from the religion keywords above.
_INSTITUTION = re.compile(
    r"\b(?:universitas|institut|sekolah\s+tinggi|politeknik|akademi|stai|stie|uin|iain|smk|sma|ma|mts|sd|smp)"
    r"\s+(?:agama\s+)?(?:islam|kristen|katolik|muhammadiyah|nahdlatul\s+ulama|hindu|buddh?a)\b"
    r"(?-i:(?:\s+[A-Z][\w.'-]*){0,4})",
    re.IGNORECASE,
)


def scrub_protected_attributes(text: str) -> tuple[str, list[str]]:
    """Returns (`text` with protected-attribute statements replaced by a placeholder, categories found)."""
    if not text:
        return text, []
    kept: list[str] = []

    def keep(match: re.Match[str]) -> str:
        kept.append(match[0])
        return f"\x00{len(kept) - 1}\x00"

    out = _INSTITUTION.sub(keep, text)
    found: list[str] = []
    for category, pattern in _PATTERNS:
        out, n = pattern.subn(PLACEHOLDER, out)
        if n:
            found.append(category)
    out = re.sub(r"(?:\[ATTR\][\s,;:/|-]*){2,}", PLACEHOLDER + " ", out)
    out = re.sub(r"\x00(\d+)\x00", lambda match: kept[int(match[1])], out)
    return out.strip(), sorted(found)
