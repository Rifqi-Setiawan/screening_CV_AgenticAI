"""Administrative Eligibility Gate evaluation module (FX-24 Revision 2).

Enforces:
- I-1: Competency scores (skills, experience, education) are 100% blind and unaffected.
- I-2: Demographic data (DOB, gender) NEVER enters LLM prompts, scoring rubrics, or candidate scores.
- I-3: Zero automated rejection (Human-in-the-Loop only via badges/filters).
- I-4: Modern CVs without DOB/gender get UNKNOWN status (never disqualified).
- I-5: Explicit candidate data only (no graduation inference or photo/name guessing).
- I-6: Requires HR written justification (min 30 chars) and ADMIN approval.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

INDONESIAN_MONTHS = {
    "januari": "january",
    "februari": "february",
    "maret": "march",
    "april": "april",
    "mei": "may",
    "juni": "june",
    "juli": "july",
    "agustus": "august",
    "september": "september",
    "oktober": "october",
    "november": "november",
    "desember": "december",
    "agt": "aug",
    "okt": "oct",
    "des": "dec",
}

REASON_MESSAGES = {
    "AGE_ABOVE_MAX": "Melebihi batas usia maksimal yang ditetapkan untuk lowongan ini.",
    "AGE_BELOW_MIN": "Di bawah batas usia minimal yang ditetapkan untuk lowongan ini.",
    "AGE_WITHIN_RANGE": "Memenuhi syarat usia.",
    "DOB_MISSING": "Tanggal lahir tidak tercantum di CV. Perlu konfirmasi ke kandidat.",
    "DOB_YEAR_ONLY_AMBIGUOUS": "CV hanya mencantumkan tahun lahir. Perlu konfirmasi ke kandidat.",
    "GENDER_MATCH": "Memenuhi syarat administratif jenis kelamin.",
    "GENDER_MISMATCH": "Tidak memenuhi syarat administratif jenis kelamin.",
    "GENDER_MISSING": "Jenis kelamin tidak tercantum di CV. Perlu konfirmasi ke kandidat.",
}


def parse_dob(raw: Any) -> dict[str, Any]:
    """Parses date of birth string with support for Indonesian formats, place prefixes, and year-only precision.

    Returns:
        {"precision": "DAY" | "YEAR" | None, "value": date | int | None, "flags": list[str]}
    """
    if not raw:
        return {"precision": None, "value": None, "flags": []}
    if isinstance(raw, dict):
        if raw.get("precision") in ("DAY", "YEAR"):
            return raw
        val = raw.get("value") or raw.get("date") or raw.get("year")
        return parse_dob(val)
    if isinstance(raw, date):
        # Validate plausible age
        today = date.today()
        approx_age = today.year - raw.year
        if approx_age < 15 or approx_age > 80:
            return {"precision": None, "value": None, "flags": ["DOB_IMPLAUSIBLE"]}
        return {"precision": "DAY", "value": raw, "flags": []}

    s = str(raw).strip()
    # Strip place prefix with comma (e.g., 'Jakarta, 12 Maret 1999', 'Bandung, 1999-03-12')
    s = re.sub(r"^[A-Za-z\s]+,\s*(?=\d)", "", s).strip()
    s_lower = s.lower()

    # Translate Indonesian month names
    for id_mo, en_mo in INDONESIAN_MONTHS.items():
        s_lower = re.sub(rf"\b{id_mo}\b", en_mo, s_lower)

    # 1. Day precision: DD-MM-YYYY or DD/MM/YYYY or YYYY-MM-DD
    # Try ISO YYYY-MM-DD
    m_iso = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", s_lower)
    if m_iso:
        try:
            d = date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
            today = date.today()
            if today.year - d.year < 15 or today.year - d.year > 80:
                return {"precision": None, "value": None, "flags": ["DOB_IMPLAUSIBLE"]}
            return {"precision": "DAY", "value": d, "flags": []}
        except ValueError:
            pass

    # Try DD/MM/YYYY or DD-MM-YYYY
    m_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", s_lower)
    if m_dmy:
        part1 = int(m_dmy.group(1))
        part2 = int(m_dmy.group(2))
        year = int(m_dmy.group(3))
        # Indonesia default is DD/MM/YYYY
        flags = []
        if part1 <= 12 and part2 <= 12:
            flags.append("DOB_DMY_ASSUMED")
        day, month = part1, part2
        if part1 > 12:
            day, month = part1, part2
        elif part2 > 12:
            day, month = part2, part1
        try:
            d = date(year, month, day)
            today = date.today()
            if today.year - d.year < 15 or today.year - d.year > 80:
                return {"precision": None, "value": None, "flags": ["DOB_IMPLAUSIBLE"]}
            return {"precision": "DAY", "value": d, "flags": flags}
        except ValueError:
            pass

    # Try textual dates: '12 March 1999' or 'March 12, 1999'
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            # Clean punctuation
            clean_s = s_lower.replace(",", " ")
            clean_s = " ".join(clean_s.split())
            dt = datetime.strptime(clean_s, fmt).date()
            today = date.today()
            if today.year - dt.year < 15 or today.year - dt.year > 80:
                return {"precision": None, "value": None, "flags": ["DOB_IMPLAUSIBLE"]}
            return {"precision": "DAY", "value": dt, "flags": []}
        except ValueError:
            continue

    # 2. Year only precision: e.g. '1999'
    m_year = re.search(r"\b(19\d{2}|20\d{2})\b", s_lower)
    if m_year:
        y = int(m_year.group(1))
        today = date.today()
        if today.year - y < 15 or today.year - y > 80:
            return {"precision": None, "value": None, "flags": ["DOB_IMPLAUSIBLE"]}
        return {"precision": "YEAR", "value": y, "flags": []}

    return {"precision": None, "value": None, "flags": ["DOB_UNPARSABLE"]}


def normalize_gender(val: Any) -> str | None:
    """Normalizes gender string into 'M' (Male) or 'F' (Female). Explicit CV text only."""
    if not val:
        return None
    s = str(val).strip().lower()
    if s in ("l", "laki-laki", "laki laki", "pria", "male", "m"):
        return "M"
    if s in ("p", "perempuan", "wanita", "female", "f"):
        return "F"
    return None


def evaluate_rule(rule: dict[str, Any], ident: dict[str, Any]) -> dict[str, Any]:
    """Evaluates a single administrative eligibility rule deterministically.

    Minimization principle: NEVER returns candidate age or gender value.
    """
    rule_id = str(rule.get("id"))
    rule_type = str(rule.get("rule_type")).upper()
    val_spec = rule.get("value") or {}
    ref_raw = rule.get("reference_date") or date.today().isoformat()
    ref_date = date.fromisoformat(str(ref_raw)) if isinstance(ref_raw, str) else ref_raw

    # Extract demographic data from ident
    other_personal = ident.get("other_personal") or {}
    if isinstance(other_personal, str):
        import json

        try:
            other_personal = json.loads(other_personal)
        except Exception:
            other_personal = {}

    dob_raw = (
        ident.get("dob")
        or ident.get("date_of_birth")
        or other_personal.get("dob")
        or other_personal.get("date_of_birth")
    )
    gender_raw = ident.get("gender") or other_personal.get("gender")

    if rule_type == "AGE_MAX":
        target_years = int(val_spec.get("years", 99))
        dob_info = parse_dob(dob_raw)
        if dob_info["precision"] == "DAY":
            d = dob_info["value"]
            assert isinstance(d, date)
            age = ref_date.year - d.year - ((ref_date.month, ref_date.day) < (d.month, d.day))
            if age <= target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MAX",
                    "status": "ELIGIBLE",
                    "reason_code": "AGE_WITHIN_RANGE",
                    "message": REASON_MESSAGES["AGE_WITHIN_RANGE"],
                }
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MAX",
                "status": "NOT_ELIGIBLE",
                "reason_code": "AGE_ABOVE_MAX",
                "message": REASON_MESSAGES["AGE_ABOVE_MAX"],
            }
        elif dob_info["precision"] == "YEAR":
            y = int(dob_info["value"])
            min_possible = ref_date.year - y - 1
            max_possible = ref_date.year - y
            if max_possible <= target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MAX",
                    "status": "ELIGIBLE",
                    "reason_code": "AGE_WITHIN_RANGE",
                    "message": REASON_MESSAGES["AGE_WITHIN_RANGE"],
                }
            elif min_possible > target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MAX",
                    "status": "NOT_ELIGIBLE",
                    "reason_code": "AGE_ABOVE_MAX",
                    "message": REASON_MESSAGES["AGE_ABOVE_MAX"],
                }
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MAX",
                "status": "UNKNOWN",
                "reason_code": "DOB_YEAR_ONLY_AMBIGUOUS",
                "message": REASON_MESSAGES["DOB_YEAR_ONLY_AMBIGUOUS"],
            }
        else:
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MAX",
                "status": "UNKNOWN",
                "reason_code": "DOB_MISSING",
                "message": REASON_MESSAGES["DOB_MISSING"],
            }

    elif rule_type == "AGE_MIN":
        target_years = int(val_spec.get("years", 0))
        dob_info = parse_dob(dob_raw)
        if dob_info["precision"] == "DAY":
            d = dob_info["value"]
            assert isinstance(d, date)
            age = ref_date.year - d.year - ((ref_date.month, ref_date.day) < (d.month, d.day))
            if age >= target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MIN",
                    "status": "ELIGIBLE",
                    "reason_code": "AGE_WITHIN_RANGE",
                    "message": REASON_MESSAGES["AGE_WITHIN_RANGE"],
                }
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MIN",
                "status": "NOT_ELIGIBLE",
                "reason_code": "AGE_BELOW_MIN",
                "message": REASON_MESSAGES["AGE_BELOW_MIN"],
            }
        elif dob_info["precision"] == "YEAR":
            y = int(dob_info["value"])
            min_possible = ref_date.year - y - 1
            max_possible = ref_date.year - y
            if min_possible >= target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MIN",
                    "status": "ELIGIBLE",
                    "reason_code": "AGE_WITHIN_RANGE",
                    "message": REASON_MESSAGES["AGE_WITHIN_RANGE"],
                }
            elif max_possible < target_years:
                return {
                    "rule_id": rule_id,
                    "rule_type": "AGE_MIN",
                    "status": "NOT_ELIGIBLE",
                    "reason_code": "AGE_BELOW_MIN",
                    "message": REASON_MESSAGES["AGE_BELOW_MIN"],
                }
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MIN",
                "status": "UNKNOWN",
                "reason_code": "DOB_YEAR_ONLY_AMBIGUOUS",
                "message": REASON_MESSAGES["DOB_YEAR_ONLY_AMBIGUOUS"],
            }
        else:
            return {
                "rule_id": rule_id,
                "rule_type": "AGE_MIN",
                "status": "UNKNOWN",
                "reason_code": "DOB_MISSING",
                "message": REASON_MESSAGES["DOB_MISSING"],
            }

    elif rule_type == "GENDER":
        allowed = val_spec.get("allowed", [])
        cand_gender = normalize_gender(gender_raw)
        if cand_gender is None:
            return {
                "rule_id": rule_id,
                "rule_type": "GENDER",
                "status": "UNKNOWN",
                "reason_code": "GENDER_MISSING",
                "message": REASON_MESSAGES["GENDER_MISSING"],
            }
        elif cand_gender in allowed:
            return {
                "rule_id": rule_id,
                "rule_type": "GENDER",
                "status": "ELIGIBLE",
                "reason_code": "GENDER_MATCH",
                "message": REASON_MESSAGES["GENDER_MATCH"],
            }
        else:
            return {
                "rule_id": rule_id,
                "rule_type": "GENDER",
                "status": "NOT_ELIGIBLE",
                "reason_code": "GENDER_MISMATCH",
                "message": REASON_MESSAGES["GENDER_MISMATCH"],
            }

    return {
        "rule_id": rule_id,
        "rule_type": rule_type,
        "status": "UNKNOWN",
        "reason_code": "RULE_TYPE_UNSUPPORTED",
        "message": f"Aturan {rule_type} tidak didukung.",
    }


def evaluate_all(rules: list[dict[str, Any]], ident: dict[str, Any]) -> dict[str, Any]:
    """Evaluates all rules for a candidate identity.

    Returns:
        {"overall_status": "ELIGIBLE" | "NOT_ELIGIBLE" | "UNKNOWN" | "NOT_APPLICABLE", "details": [...]}
    """
    if not rules:
        return {
            "overall_status": "NOT_APPLICABLE",
            "details": [],
        }

    details = [evaluate_rule(r, ident) for r in rules]

    has_not_eligible = any(d["status"] == "NOT_ELIGIBLE" for d in details)
    has_unknown = any(d["status"] == "UNKNOWN" for d in details)

    if has_not_eligible:
        overall_status = "NOT_ELIGIBLE"
    elif has_unknown:
        overall_status = "UNKNOWN"
    else:
        overall_status = "ELIGIBLE"

    return {
        "overall_status": overall_status,
        "details": details,
    }
