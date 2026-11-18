"""Text parsing helpers for applicant CV prefill."""

from __future__ import annotations

import re
from typing import Any

MONTHS_MAP = {
    "jan": "01",
    "januari": "01",
    "january": "01",
    "feb": "02",
    "februari": "02",
    "pebruari": "02",
    "february": "02",
    "mar": "03",
    "maret": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "mei": "05",
    "may": "05",
    "jun": "06",
    "juni": "06",
    "june": "06",
    "jul": "07",
    "juli": "07",
    "july": "07",
    "agu": "08",
    "agt": "08",
    "agus": "08",
    "agustus": "08",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "okt": "10",
    "oktober": "10",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "nopember": "11",
    "november": "11",
    "des": "12",
    "desember": "12",
    "dec": "12",
    "december": "12",
}

PRESENT_SET = {"sekarang", "saat ini", "kini", "present", "now", "current", "currently", "to date"}
MONTHS_REGEX_STR = r"(?:jan(?:uari|uary)?|feb(?:ruari|ruary)?|mar(?:et|ch)?|apr(?:il)?|mei|may|jun(?:i|e)?|jul(?:i|y)?|agu(?:stus)?|aug(?:ust)?|sep(?:t(?:ember)?)?|okt(?:ober)?|oct(?:ober)?|nov(?:ember)?|des(?:ember)?|dec(?:ember)?)"

RANGE_REGEX = re.compile(
    rf"({MONTHS_REGEX_STR}(?:\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b)\s*(?:[-–—=]|s/d|sd|to|sampai|hingga|until)\s*({MONTHS_REGEX_STR}(?:\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|sekarang|present|saat ini|current|now)",
    re.IGNORECASE,
)


SNAPSHOT_DURATION = re.compile(
    r"^\(\s*(\d+\s*(?:tahun|thn|years?|yrs?|bulan|bln|months?|mos?)(?:\s+\d+\s*(?:bulan|bln|months?|mos?))?)\s*\)",
    re.I,
)


def norm_single_date(s: str, is_end: bool = False, ref_year: str = "") -> dict[str, Any]:
    s_clean = s.strip().lower()
    if any(p in s_clean for p in PRESENT_SET):
        return {"raw": s.strip(), "value": "present", "precision": "month", "kind": "FACT"}

    m = re.match(r"(\d{1,2})/(\d{4})", s_clean)
    if m:
        val = f"{m.group(2)}-{int(m.group(1)):02d}"
        return {"raw": s.strip(), "value": val, "precision": "month", "kind": "FACT"}

    m = re.match(rf"({MONTHS_REGEX_STR})\s+(\d{{4}})", s_clean)
    if m:
        mname = m.group(1)
        year = m.group(2)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        return {"raw": s.strip(), "value": f"{year}-{mcode}", "precision": "month", "kind": "FACT"}

    m = re.match(rf"^({MONTHS_REGEX_STR})$", s_clean)
    if m and ref_year:
        mname = m.group(1)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        year_num = int(ref_year) + (1 if is_end else 0)
        return {"raw": s.strip(), "value": f"{year_num}-{mcode}", "precision": "month", "kind": "FACT"}

    m = re.match(r"^\d{4}$", s_clean)
    if m:
        y = m.group(0)
        val = f"{y}-01" if not is_end else f"{y}-12"
        return {"raw": s.strip(), "value": val, "precision": "year", "kind": "INFERENCE"}

    return {"raw": s.strip(), "value": None, "precision": "unknown", "kind": "FACT"}


def parse_experiences(section_text: str) -> list[dict[str, Any]]:
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    entries: list[dict[str, Any]] = []

    date_lines = []
    for idx, l in enumerate(lines):
        m = RANGE_REGEX.search(l)
        if m:
            date_lines.append((idx, m.group(1), m.group(2), m.start(), m.end()))
        else:
            m_single = re.search(r"\b(19\d{2}|20\d{2})\b\s*[|—–-]\s*(.+)", l)
            if m_single:
                date_lines.append((idx, m_single.group(1), m_single.group(1), 0, len(l)))

    for i, (idx, raw_start, raw_end, m_start, m_end) in enumerate(date_lines):
        ref_y = ""
        m_y = re.search(r"\b(\d{4})\b", raw_start)
        if m_y:
            ref_y = m_y.group(1)
        else:
            m_y2 = re.search(r"\b(\d{4})\b", raw_end)
            if m_y2:
                ref_y = m_y2.group(1)

        start_date = norm_single_date(raw_start, is_end=False, ref_year=ref_y)
        end_date = norm_single_date(raw_end, is_end=True, ref_year=ref_y)

        curr_line = lines[idx]
        pre_text = curr_line[:m_start].strip().strip("(-|•— ")

        title = ""
        org = ""

        # Extract title and organization from pre_text or preceding lines
        if pre_text:
            parts = re.split(r"[—|]", pre_text)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = pre_text.strip()
        elif idx > 0:
            prev_line = lines[idx - 1].strip("(-|•— ")
            parts = re.split(r"[—|]", prev_line)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = prev_line.strip()
                org = lines[idx - 2].strip().split(",")[0].strip() if idx > 1 else ""
                title = re.sub(
                    r"^(?:interned\s+as\s+a|worked\s+as\s+an|worked\s+as\s+a|sebagai)\s+", "", title, flags=re.I
                ).strip()

        if not title:
            candidate_next = (
                lines[idx + 1].strip("•-* ")
                if (idx + 1 < len(lines) and not RANGE_REGEX.search(lines[idx + 1]))
                else ""
            )
            candidate_prev = (
                lines[idx - 1].strip("•-* ") if (idx > 0 and not RANGE_REGEX.search(lines[idx - 1])) else ""
            )

            if candidate_next and (
                "," in candidate_next
                or "-" in candidate_next
                or any(
                    k in candidate_next.lower()
                    for k in [
                        "analyst",
                        "engineer",
                        "manager",
                        "staff",
                        "intern",
                        "developer",
                        "consultant",
                        "officer",
                        "lead",
                        "head",
                        "specialist",
                        "direktur",
                        "spv",
                        "project",
                        "asisten",
                        "asst",
                    ]
                )
            ):
                parts = re.split(r"[,|—–-]", candidate_next)
                if len(parts) >= 2:
                    p0, p1 = parts[0].strip(), parts[1].strip()
                    if any(
                        k in p1.lower()
                        for k in [
                            "analyst",
                            "engineer",
                            "manager",
                            "staff",
                            "intern",
                            "developer",
                            "consultant",
                            "spv",
                            "lead",
                            "officer",
                        ]
                    ):
                        title, org = p1, p0
                    else:
                        title, org = p0, p1
                else:
                    title = candidate_next
                    if candidate_prev:
                        org = candidate_prev
            elif candidate_prev:
                parts = re.split(r"[,|—–-]", candidate_prev)
                if len(parts) >= 2:
                    p0, p1 = parts[0].strip(), parts[1].strip()
                    if any(
                        k in p1.lower()
                        for k in [
                            "analyst",
                            "engineer",
                            "manager",
                            "staff",
                            "intern",
                            "developer",
                            "consultant",
                            "spv",
                            "lead",
                            "officer",
                        ]
                    ):
                        title, org = p1, p0
                    else:
                        title, org = p0, p1
                else:
                    title = candidate_prev
                    if candidate_next:
                        org = candidate_next
            elif candidate_next:
                title = candidate_next

        next_idx = date_lines[i + 1][0] if i + 1 < len(date_lines) else len(lines)
        start_bullet = idx + 2 if (idx + 1 < len(lines) and lines[idx + 1].strip("•-* ") == title) else idx + 1
        bullet_lines = lines[start_bullet:next_idx]
        bullets = []
        duration = SNAPSHOT_DURATION.match(curr_line[m_end:].strip())
        if duration:
            bullets.append(f"Durasi tercantum di CV: {duration[1]}.")
        if end_date["value"] == "present":
            bullets.append("Status terkini belum dikonfirmasi.")
        for bullet in bullet_lines:
            cleaned = bullet.lstrip("•-* ").strip()
            if len(cleaned) > 5 and not RANGE_REGEX.search(bullet):
                bullets.append(cleaned)

        if title:
            title = re.split(r"[—|]", title)[0].strip()
            entries.append(
                {
                    "title": title,
                    "organization": org,
                    "start": start_date,
                    "end": end_date,
                    "bullets": bullets,
                }
            )

    return entries


def parse_skills(section_text: str) -> list[str]:
    items = re.split(r"[,•\n\r]+", section_text)
    cleaned = []
    for it in items:
        s = it.strip().strip("-*").strip()
        if s and len(s) < 50 and not s.lower().startswith("keahlian"):
            cleaned.append(s)
    return cleaned


def parse_certifications(text: str) -> list[str]:
    lines = [l.strip().lstrip("-•*~ ").strip() for l in text.splitlines() if l.strip()]
    merged = []
    curr = ""
    for l in lines:
        if curr and (
            l.startswith("Developer")
            or l.startswith("Engineer")
            or l.startswith("(")
            or l.startswith("—")
            or l.startswith("-")
        ):
            curr += " " + l
        else:
            if curr:
                merged.append(curr)
            curr = l
    if curr:
        merged.append(curr)

    return [
        l for l in merged if len(l) > 3 and not l.lower().startswith("keahlian") and not l.lower().startswith("skills")
    ]
