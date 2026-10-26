"""Policy linter enforcing prohibited and administrative demographic criteria detection on JDs and Requirements."""

from __future__ import annotations

import re
from typing import Any

from src.infrastructure.config import settings

PROHIBITED_RULES = {
    "appearance": [
        r"berpenampilan\s+menarik",
        r"good\s+looking",
        r"tinggi\s+badan",
        r"berat\s+badan",
        r"tinggi\s+minimal",
        r"foto\s+full\s+body",
        r"proporsional",
    ],
    "religion": [
        r"\bagama\b",
        r"\bberagama\b",
        r"\bmuslim\b",
        r"\bmuslimah\b",
        r"\bkristen\b",
        r"\bkatolik\b",
        r"\bhindu\b",
        r"\bbuddha\b",
        r"\bberhijab\b",
        r"\breligion\b",
    ],
    "ethnicity": [
        r"\bsuku\b",
        r"\betnis\b",
        r"\bketurunan\b",
        r"\bras\b",
        r"\bpribumi\b",
        r"\bethnicity\b",
        r"\brace\b",
    ],
    "marital": [
        r"belum\s+menikah",
        r"\blajang\b",
        r"\bsingle\b",
        r"status\s+pernikahan",
        r"\bmarried\b",
        r"tidak\s+sedang\s+hamil",
        r"\bhamil\b",
    ],
    "health_misc": [
        r"golongan\s+darah",
        r"tidak\s+bertato",
        r"tidak\s+bertindik",
    ],
}

ADMIN_DEMOGRAPHIC_RULES = {
    "age": [
        r"\b(?:usia|umur)\s*(?:maksimal|maks|max|minimal|min)?\s*\d+\s*(?:tahun|thn|years)?\b",
        r"\b(?:maksimal|maks|max|maximum)\s*\d+\s*(?:tahun|thn|years)\b",
        r"\b(?:kelahiran\s+tahun)\b",
        r"\b(?:max|min)\s*age\b",
        r"\b(?:age\s*limit)\b",
        r"\b(?:usia|umur)\b",
    ],
    "gender": [
        r"\bpria\b",
        r"\bwanita\b",
        r"laki[\s-]laki",
        r"\bperempuan\b",
        r"\bmale\b",
        r"\bfemale\b",
        r"jenis\s+kelamin",
        r"diutamakan\s+(?:wanita|pria|perempuan|laki-laki)",
        r"khusus\s+(?:wanita|pria|perempuan|laki-laki)",
    ],
}

RISKY_RULES = {
    "age_proxy": [r"fresh\s+graduate", r"lulusan\s+tahun\s+\d+", r"tahun\s+lulus\s+minimal"],
    "institution": [r"\bptn\b", r"kampus\s+ternama", r"top\s+university", r"universitas\s+terkemuka"],
    "gpa": [r"ipk\s+minimal", r"ipk\s+min", r"gpa\s+minimum", r"minimum\s+gpa"],
    "domicile": [r"\bdomisili\b", r"\bberdomisili\b"],
}


def lint_text(text: str) -> dict[str, Any]:
    prohibited_flags: list[str] = []
    admin_flags: list[str] = []
    risky_flags: list[str] = []

    text_lower = text.lower()

    for category, patterns in PROHIBITED_RULES.items():
        if category == "religion" and settings.ALLOW_RELIGION_CRITERIA:
            continue
        for pat in patterns:
            if re.search(pat, text_lower):
                prohibited_flags.append(f"PROHIBITED_{category.upper()}")
                break

    for category, patterns in ADMIN_DEMOGRAPHIC_RULES.items():
        if category == "gender" and settings.ALLOW_GENDER_CRITERIA:
            continue
        if category == "age" and settings.ALLOW_AGE_CRITERIA:
            continue
        for pat in patterns:
            if re.search(pat, text_lower):
                admin_flags.append(f"ADMIN_ONLY_{category.upper()}")
                break

    for category, patterns in RISKY_RULES.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                risky_flags.append(f"RISKY_{category.upper()}")
                break

    prohibited_flags = sorted(list(set(prohibited_flags)))
    admin_flags = sorted(list(set(admin_flags)))
    risky_flags = sorted(list(set(risky_flags)))

    return {
        "is_valid": len(prohibited_flags) == 0,
        "prohibited_flags": prohibited_flags,
        "admin_flags": admin_flags,
        "risky_flags": risky_flags,
    }
