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
    rf"({MONTHS_REGEX_STR}(?:,?\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b)\s*(?:[-–—=]|s/d|sd|to|sampai|hingga|until)\s*({MONTHS_REGEX_STR}(?:,?\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|sekarang|present|saat ini|current|now)",
    re.IGNORECASE,
)


SNAPSHOT_DURATION = re.compile(
    r"^\(\s*(\d+\s*(?:tahun|thn|years?|yrs?|bulan|bln|months?|mos?)(?:\s+\d+\s*(?:bulan|bln|months?|mos?))?)\s*\)",
    re.I,
)


# Content cues decide which fragment is the job title and which is the employer; line order is only the tie-breaker.
ORG_CUES = re.compile(
    r"\b(?:pt|cv|ud|tbk|persero|bumn|inc|ltd|llc|corp|corporation|company|bank|universitas|university|institut|institute|"
    r"politeknik|yayasan|kementerian|dinas|rumah sakit|rsud?|studio|group|grup|technologies|technology|teknologi|solutions?|"
    r"solusi|systems|sistem|labs?|startup|perusahaan|agency|agensi|konsultan|foundation|school|sekolah|hospital|hotel|"
    r"restoran|toko|pabrik|koperasi)\b",
    re.I,
)
TITLE_CUES = re.compile(
    r"\b(?:analyst|analis|engineer|insinyur|manager|manajer|developer|programmer|designer|desainer|architect|arsitek|"
    r"administrator|admin|staff|staf|intern|magang|trainee|officer|specialist|spesialis|consultant|konsultan|coordinator|"
    r"koordinator|supervisor|spv|kepala|head|lead|director|direktur|executive|asisten|assistant|teknisi|technician|"
    r"akuntan|accountant|auditor|sales|marketing|secretary|sekretaris|operator|surveyor|mekanik|guru|dosen|perawat|"
    r"apoteker|researcher|peneliti|scientist|editor|writer|penulis|freelancer?|associate|representative|agent|cashier|"
    r"kasir|driver|pengemudi|recruiter|generalist|owner|leader)\b",
    re.I,
)


def order_title_org(first: str, second: str) -> tuple[str, str]:
    """(title, organization) for two fragments. Content cues win; with no evidence the first fragment is the title."""
    if not second:
        return first, ""
    straight = len(TITLE_CUES.findall(first)) + len(ORG_CUES.findall(second))
    swapped = len(TITLE_CUES.findall(second)) + len(ORG_CUES.findall(first))
    return (second, first) if swapped > straight else (first, second)


def split_header(text: str, commas: bool = True) -> list[str]:
    """Split "Title - Organisation", "Title at Organisation", "Title, Organisation" style headers (first pattern wins)."""
    # A lone lowercase "l" between spaces is how some PDF exports render the "|" separator.
    patterns = [r"\s*[—|]\s*|\s+l\s+", r"\s+[–-]\s+", r"\s+(?:at|di|pada|@)\s+"] + ([r"\s*,\s*"] if commas else [])
    for pattern in patterns:
        parts = [part.strip(" ,;·") for part in re.split(pattern, text, maxsplit=2) if part.strip(" ,;·")]
        if len(parts) >= 2:
            return parts
    return [text.strip(" ,;·")]


def norm_single_date(s: str, is_end: bool = False, ref_year: str = "") -> dict[str, Any]:
    s_clean = s.strip().lower()
    if any(p in s_clean for p in PRESENT_SET):
        return {"raw": s.strip(), "value": "present", "precision": "month", "kind": "FACT"}

    m = re.match(r"(\d{1,2})/(\d{4})", s_clean)
    if m:
        val = f"{m.group(2)}-{int(m.group(1)):02d}"
        return {"raw": s.strip(), "value": val, "precision": "month", "kind": "FACT"}

    m = re.match(rf"({MONTHS_REGEX_STR})[,\s]+(\d{{4}})", s_clean)
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


WORK_TYPE = re.compile(r"^(?:on-?site|remote|hybrid|wfo|wfh|contract|kontrak|full[- ]?time|part[- ]?time|permanent|tetap)$", re.I)
LONE_YEAR_LINE = re.compile(r"(?:19|20)\d{2}")
SELF_EMPLOYED = re.compile(r"^(?:freelance|freelancer|self[- ]employed|wiraswasta|wirausaha)$", re.I)
BULLET_MARKS = "•●▪◦■-* "
CONTACT_LINE = re.compile(r"@|https?://|www\.", re.I)
COUNTRY_LOCATION = re.compile(r"[\w .'-]+(?:,\s*[\w .'-]+){1,3}")


def work_type_only(text: str) -> bool:
    """"Onsite | Contract" carries neither a title nor an employer."""
    pieces = [piece.strip() for piece in re.split(r"[|,/·•]", text) if piece.strip()]
    return bool(pieces) and all(WORK_TYPE.match(piece) for piece in pieces)


def names_a_title(part: str) -> bool:
    """"Freelance" in the employer slot is an employer, not a job title."""
    return bool(TITLE_CUES.search(part)) and not SELF_EMPLOYED.match(part.strip())


def header_candidate(lines: list[str], index: int) -> str:
    """A short, sentence-less line that can be part of a job header; "" for bullets, dates and contact lines."""
    if index < 0 or index >= len(lines):
        return ""
    text = lines[index].strip("(-|•●▪◦■— ")
    if not text or len(text.split()) > 12 or text.endswith((".", ":", ";")) or CONTACT_LINE.search(text) or RANGE_REGEX.search(text):
        return ""
    return text


def header_above(lines: list[str], idx: int) -> tuple[str, str, int] | None:
    """"Title", "Company | City", then the dates on their own line: (title, employer, first header line)."""
    if idx < 2:
        return None
    two_up, prev = header_candidate(lines, idx - 2), header_candidate(lines, idx - 1)
    parts = split_header(lines[idx - 1].strip("(-|•— "), commas=False)
    if two_up and prev and TITLE_CUES.search(two_up) and not any(names_a_title(part) for part in parts):
        return two_up, clean_org(next((part for part in parts if ORG_CUES.search(part)), parts[0])), idx - 2
    return None


def header_below(lines: list[str], idx: int) -> tuple[str, str] | None:
    """Dates first (PDF reading order puts a right-aligned date above its row), then "Title", then "Company | City"."""
    title, second = header_candidate(lines, idx + 1), header_candidate(lines, idx + 2)
    if not (title and second and names_a_title(title)):
        return None
    parts = split_header(second, commas=False)
    if len(parts) < 2 and not ORG_CUES.search(second):
        return None
    return title, clean_org(next((part for part in parts if ORG_CUES.search(part)), parts[0]))


def clean_org(text: str) -> str:
    """Employer without a trailing city or country ("PT Contoh - Bandung, Indonesia" -> "PT Contoh")."""
    return re.split(r"\s+[–-]\s+|,\s*", text.strip(), maxsplit=1)[0].strip()


def is_noise_bullet(text: str) -> bool:
    if CONTACT_LINE.search(text):
        return True
    return bool(COUNTRY_LOCATION.fullmatch(text)) and bool(re.search(r"\b(?:Indonesia|ID)$", text))


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
            elif idx > 0 and LONE_YEAR_LINE.fullmatch(l):
                date_lines.append((idx, l, l, 0, len(l)))

    # First pass: header (title, employer, dates) of every entry. Second pass: descriptions, which stop where the
    # next entry's header begins, so a header written above its date line never leaks into the previous entry.
    heads: list[dict[str, Any]] = []
    for idx, raw_start, raw_end, m_start, m_end in date_lines:
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
        if pre_text and work_type_only(pre_text):
            pre_text = ""

        title = ""
        org = ""
        header_start = idx  # first line that belongs to this entry's header
        body_start = idx + 1  # first line of the description

        # Extract title and organization from pre_text or preceding lines
        if pre_text:
            parts = split_header(pre_text)
            above = header_candidate(lines, idx - 1)
            if above and TITLE_CUES.search(above) and not any(names_a_title(part) for part in parts):
                # "Title" on its own line, then "Company - City | dates".
                title = above
                org = clean_org(next((part for part in parts if ORG_CUES.search(part)), parts[0]))
                header_start = idx - 1
            elif len(parts) >= 2:
                title, org = order_title_org(parts[0], parts[1])
                org = org.split(",")[0].strip()
            else:
                title = pre_text.strip()
        else:
            above = header_above(lines, idx)
            below = None if above else header_below(lines, idx)
            if above:
                title, org, header_start = above
            elif below:
                title, org = below
                body_start = idx + 3
            elif idx > 0:
                prev_line = lines[idx - 1].strip("(-|•— ")
                parts = split_header(prev_line, commas=False)
                header_start = idx - 1
                if len(parts) >= 2:
                    title, org = order_title_org(parts[0], parts[1])
                    org = org.split(",")[0].strip()
                else:
                    title = prev_line.strip()
                    org = lines[idx - 2].strip().split(",")[0].strip() if idx > 1 else ""
                    title, org = order_title_org(title, org)
                    title = re.sub(
                        r"^(?:interned\s+as\s+a|worked\s+as\s+an|worked\s+as\s+a|sebagai)\s+", "", title, flags=re.I
                    ).strip()
                    header_start = max(idx - 2, 0)

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

        heads.append(
            {
                "idx": idx,
                "m_end": m_end,
                "header_start": header_start,
                "body_start": body_start,
                "title": title,
                "org": org,
                "start": start_date,
                "end": end_date,
                "curr_line": curr_line,
            }
        )

    for i, head in enumerate(heads):
        idx, title = head["idx"], head["title"]
        next_idx = heads[i + 1]["header_start"] if i + 1 < len(heads) else len(lines)
        start_bullet = head["body_start"]
        if start_bullet == idx + 1 and idx + 1 < len(lines) and lines[idx + 1].strip(BULLET_MARKS) == title:
            start_bullet = idx + 2
        bullets = []
        duration = SNAPSHOT_DURATION.match(head["curr_line"][head["m_end"] :].strip())
        if duration:
            bullets.append(f"Durasi tercantum di CV: {duration[1]}.")
        if head["end"]["value"] == "present":
            bullets.append("Status terkini belum dikonfirmasi.")
        for bullet in lines[start_bullet:next_idx]:
            cleaned = bullet.lstrip(BULLET_MARKS).strip()
            if len(cleaned) > 5 and not RANGE_REGEX.search(bullet) and not is_noise_bullet(cleaned):
                bullets.append(cleaned)

        if title:
            title = re.split(r"[—|]", title)[0].strip()
            entries.append(
                {
                    "title": title,
                    "organization": head["org"],
                    "start": head["start"],
                    "end": head["end"],
                    "bullets": bullets,
                }
            )

    return entries


SKILL_SEPARATORS = re.compile(r"\s*[|•;]\s*|\s+/\s+")
NOT_A_SKILL = re.compile(
    r"\b(?:smk|sma|smp|universitas|university|politeknik|institut|institute|sekolah|ipk|gpa)\b|^(?:19|20)\d{2}(?:\s*[-–—]\s*(?:19|20)\d{2})?$",
    re.I,
)
SOFT_LABEL = re.compile(r"soft\s*skills?|non[- ]?teknis|non[- ]?technical|interpersonal", re.I)
LABEL_LINE = re.compile(r"^([^:|,()]{2,40}?)\s*:\s*(.*)$")
MAX_SKILL_WORDS = 6


def split_top_level(text: str, separators: re.Pattern[str] = SKILL_SEPARATORS) -> list[str]:
    """Split on commas and the usual list separators, but never inside parentheses."""
    pieces: list[str] = []
    depth = 0
    start = 0
    for position, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            pieces.append(text[start:position])
            start = position + 1
    pieces.append(text[start:])
    return [part.strip() for piece in pieces for part in separators.split(piece) if part.strip()]


def logical_lines(section_text: str) -> list[str]:
    """Join lines the PDF wrapped in the middle of a sentence (next line starts lower case, or the list ends in a comma)."""
    merged: list[str] = []
    for raw in section_text.splitlines():
        line = raw.strip().strip(BULLET_MARKS).strip()
        if not line:
            continue
        if merged and (line[0].islower() or merged[-1].endswith((",", "&", "(", "-"))):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def is_group_label(line: str) -> bool:
    """"DATABASES:" / "BAHASA PEMROGRAMAN": a heading above the real list, not a skill."""
    if line.endswith(":"):
        return True
    words = line.split()
    return len(words) >= 2 and line.upper() == line and not re.search(r"[|,/]", line)


def parse_skills(section_text: str, expand_parentheses: bool = True) -> list[str]:
    skills: list[str] = []
    skipping = False
    for line in logical_lines(section_text):
        label = LABEL_LINE.match(line)
        if label:
            skipping = bool(SOFT_LABEL.search(label[1]))
            line = label[2].strip()
        elif is_group_label(line):
            skipping = bool(SOFT_LABEL.search(line))
            continue
        if skipping or not line or NOT_A_SKILL.search(line):
            continue
        for item in split_top_level(line):
            item = item.strip(" -*.")
            inner = re.match(r"^(.*?)\s*\((.+,.+)\)$", item) if expand_parentheses else None
            candidates = [inner[1], *split_top_level(inner[2])] if inner else [item]
            for candidate in candidates:
                candidate = candidate.strip(" -*")
                if candidate and len(candidate) < 50 and len(candidate.split()) <= MAX_SKILL_WORDS and not candidate.endswith("."):
                    if candidate.lower() not in {s.lower() for s in skills} and not candidate.lower().startswith("keahlian"):
                        skills.append(candidate)
    return skills


def parse_projects(section_text: str) -> list[str]:
    """One entry per project: a short title line starts a block when the previous line ended a sentence."""
    blocks: list[list[str]] = []
    previous = ""
    for raw in section_text.splitlines():
        line = raw.strip().strip(BULLET_MARKS).strip()
        if not line or re.match(r"^link\b.*:", line, re.I):
            continue
        line = re.sub(r"^(?:deskripsi|description)\s*:\s*", "", line, flags=re.I)
        titled = (
            len(line) <= 90
            and not line.endswith((".", ":", ";", ","))
            and not line[0].islower()
            and (not previous or previous.endswith((".", "!", "?")))
        )
        if titled or not blocks:
            blocks.append([line])
        else:
            blocks[-1].append(line)
        previous = line
    # One line per project: the form field is "one entry per line", so a newline inside an entry would split it.
    return [f"{block[0]} — {join_wrapped(block[1:])}" if len(block) > 1 else block[0] for block in blocks]


def join_wrapped(lines: list[str]) -> str:
    """Join wrapped lines; a word split at a hyphen ("E-" + "Commerce") is glued back together."""
    text = ""
    for line in lines:
        if text.endswith("-") and len(text) > 1 and text[-2] != " ":
            text += line
        else:
            text = f"{text} {line}".strip()
    return text


def parse_certifications(text: str) -> list[str]:
    lines = [l.strip().lstrip("-•*~ ").strip() for l in text.splitlines() if l.strip()]
    if any(LONE_YEAR_LINE.fullmatch(l) for l in lines):
        # Each entry has its year on a line of its own: after the name ("Name", "2023") or, in the reading order some
        # PDFs produce, before it ("2023", "Name").
        year_first = bool(LONE_YEAR_LINE.fullmatch(lines[0]))
        entries: list[tuple[str, list[str]]] = []
        body: list[str] = []
        for l in lines:
            if LONE_YEAR_LINE.fullmatch(l):
                if year_first:
                    entries.append((l, []))
                else:
                    entries.append((l, body))
                    body = []
            elif year_first and entries:
                entries[-1][1].append(l)
            else:
                body.append(l)
        if body:
            entries.append(("", body))
        return [f"{join_wrapped(words)} {year}".strip() for year, words in entries if len(join_wrapped(words)) > 3]

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
