"""Local, text-only CV prefill. Uploaded documents do not become submissions."""

from __future__ import annotations

import io
import re
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

import pymupdf

from src.domain.pii import EMAIL_REGEX, PHONE_REGEX
from src.worker.anchor import resolve_candidate_name_consensus
from src.worker.cv_text import parse_certifications, parse_experiences, parse_projects, parse_skills
from src.worker.visibility import PdfLine, visible_pdf_lines

WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SECTION_ALIASES = {
    "summary": [
        "summary",
        "profile",
        "about",
        "about me",
        "professional summary",
        "career summary",
        "objective",
        "career objective",
        "personal statement",
        "description",
        "ringkasan",
        "profil",
        "profil singkat",
        "tentang saya",
        "tentang",
        "deskripsi",
        "deskripsi diri",
        "ringkasan profesional",
    ],
    "experience": [
        "experience",
        "experiences",
        "work experience",
        "work experiences",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "internship",
        "internships",
        "internship experience",
        "pengalaman",
        "pengalaman kerja",
        "riwayat pekerjaan",
        "pengalaman profesional",
        "pengalaman magang",
        "riwayat kerja",
        "pengalaman bekerja",
    ],
    "education": [
        "education",
        "education history",
        "educational background",
        "academic background",
        "academic history",
        "pendidikan",
        "riwayat pendidikan",
        "latar belakang pendidikan",
        "pendidikan formal",
    ],
    "skills": [
        "skills",
        "skill",
        "relevant skills",
        "technical skills",
        "hard skills",
        "core competencies",
        "competencies",
        "skills & others",
        "skills & tools",
        "skills & interests",
        "tools",
        "tech stack",
        "expertise",
        "keahlian",
        "kemampuan",
        "keterampilan",
        "kompetensi",
        "keahlian teknis",
        "keahlian teratas",
        "top skills",
    ],
    "projects": [
        "projects",
        "project",
        "personal projects",
        "academic projects",
        "portfolio",
        "proyek",
        "projek",
        "portofolio",
        "pengalaman proyek",
    ],
    "training": [
        "training",
        "trainings",
        "courses",
        "course",
        "professional training",
        "ai & professional training",
        "bootcamp",
        "activities",
        "activity",
        "pelatihan",
        "kursus",
        "kegiatan",
        "pelatihan & kursus",
    ],
    "certifications": [
        "certifications",
        "certification",
        "certificates",
        "certificate",
        "licenses & certifications",
        "licenses and certifications",
        "sertifikasi",
        "sertifikat",
        "lisensi & sertifikasi",
    ],
    "organizations": [
        "organization",
        "organizations",
        "organizational experience",
        "leadership",
        "leadership experience",
        "volunteer",
        "volunteering",
        "volunteer experience",
        "organisasi",
        "pengalaman organisasi",
        "kepanitiaan",
        "kegiatan organisasi",
    ],
    "awards": [
        "awards",
        "award",
        "achievements",
        "achievement",
        "honors",
        "honors & awards",
        "prestasi",
        "penghargaan",
        "pencapaian",
    ],
    "soft_skills": [
        "soft skills",
        "soft skill",
        "interpersonal skills",
        "non-technical skills",
        "kemampuan non-teknis",
        "kemampuan non teknis",
        "keterampilan non-teknis",
    ],
    "languages": ["languages", "language", "bahasa", "kemampuan bahasa"],
    "contact": [
        "contact",
        "contacts",
        "contact info",
        "contact information",
        "contact me",
        "kontak",
        "informasi kontak",
        "hubungi saya",
        "hubungi",
    ],
    "personal_info": [
        "personal information",
        "personal info",
        "personal details",
        "personal data",
        "data diri",
        "informasi pribadi",
        "biodata",
        "data pribadi",
    ],
    "publications": ["publications", "publication", "research", "publikasi", "penelitian"],
    "interests": ["interests", "hobbies", "hobby", "minat", "hobi"],
    "references": ["references", "reference", "referensi"],
    "additional_info": [
        "additional information",
        "additional info",
        "others",
        "other information",
        "informasi tambahan",
        "lainnya",
        "lain-lain",
    ],
}
# Extra headings seen in Indonesian and English CVs.
for _label, _more in {
    "education": ["riwayat studi", "latar belakang akademik", "kualifikasi akademik", "academic qualifications", "studi"],
    "experience": ["riwayat kerja", "pengalaman bekerja"],
    "skills": ["kemampuan teknis", "keterampilan teknis", "penguasaan alat atau software", "penguasaan alat", "technical skill"],
    "certifications": [
        "course & certifications",
        "course & certification",
        "courses & certifications",
        "course and certifications",
        "courses and certifications",
        "training & certifications",
        "certifications & courses",
        "kursus & sertifikasi",
        "pelatihan & sertifikasi",
        "sertifikasi & pelatihan",
        "sertifikasi & kursus",
    ],
}.items():
    SECTION_ALIASES[_label] = [*SECTION_ALIASES[_label], *(alias for alias in _more if alias not in SECTION_ALIASES[_label])]
HEADINGS = {alias: label for label, aliases in SECTION_ALIASES.items() for alias in aliases}
DEGREES = (
    ("S3", r"\b(?:S[- ]?3|doktor|ph\.?d\.?)\b"),
    ("S2", r"\b(?:S[- ]?2|magister|master|mba)\b"),
    ("S1", r"\b(?:S[- ]?1|sarjana|bachelor)\b"),
    ("D4", r"\b(?:D[- ]?4|diploma (?:IV|4))\b"),
    ("D3", r"\b(?:D[- ]?3|diploma (?:III|3)|associate)\b"),
    ("SMA/SMK", r"\b(?:SM[AK][NS]?(?=\b|\d)|high school)\b"),
)
CAMPUS = re.compile(
    r"\b(?:universitas|university|institute|institut|politeknik|polytechnic|akademi|college|sekolah tinggi|UIN|ITB|UGM|UI|IPB|ITS|"
    r"UB|UNPAD|UNDIP|UNAIR|UNS|UNY|UNJ|UNM|UNHAS|UNAND|UNSRI|UPI|UPN|UII|UMY|UMM|UMS|UAJY|UNPAR|UNTAR|UNIKOM|STMIK|STIE|"
    r"STIKOM|STAN|PNJ|PENS|ITK|ITERA|BINUS|TELKOM|GUNADARMA|TRISAKTI)\b|\bSM[AK][NS]?(?=\b|\d)",
    re.I,
)
MAJOR = re.compile(
    r"(?:\b(?:jurusan|major|program studi|prodi)\s*[:–-]?\s*|"
    r"^\s*(?:bachelor of\s+|(?:bachelor(?:['’]s)? degree|master(?:['’]s)? degree|"
    r"high school diploma|S[1-3]|D[34])\s*[,:\-–]\s*))(.+)",
    re.I,
)
EDUCATION_DATES = re.compile(r"(?:\s*[·|]\s*)?\(?\b(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}\)?\s*$")
GPA = re.compile(r"\b(?:IPK|GPA)\s*[:=]?\s*([0-4](?:[.,]\d{1,3})?)", re.I)
INDONESIAN_LOCATION = re.compile(r"^([\w -]{2,60}),\s*[\w .-]{2,60},\s*Indonesia$", re.I)


# One-line education entries ("Campus | S1 Major | IPK 3.75 | 2018 - 2022") and degree phrases ("Bachelor of Science in X").
SEGMENT_SPLIT = re.compile(r"\s*[|·]\s*|\s+[–—-]\s+|,\s+(?=(?:IPK|GPA)\b)", re.I)
DATE_RANGE = re.compile(r"\(?\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|sekarang|present)\b\)?", re.I)
GPA_PHRASE = re.compile(r"\(?\b(?:IPK|GPA)\s*[:=]?\s*[0-4](?:[.,]\d{1,3})?(?:\s*/\s*4(?:[.,]0+)?)?\)?", re.I)
LONE_YEAR = re.compile(r"^\(?\s*(?:19|20)\d{2}\s*\)?$")
TRAILING_LOCATION = re.compile(r"(?:\s*,\s*[^,|]+){0,3}\s*,\s*(?:Indonesia|ID)\s*$", re.I)
DIRTY_CAMPUS = re.compile(r"[|·]|\s[–—-]\s|\b(?:IPK|GPA)\b|\b(?:19|20)\d{2}\b", re.I)


def education_segments(block: list[str]) -> list[str]:
    segments = []
    for line in block:
        for part in SEGMENT_SPLIT.split(line):
            part = GPA_PHRASE.sub(" ", DATE_RANGE.sub(" ", part)).strip(" ,;·|()–—-")
            if part and not LONE_YEAR.match(part):
                segments.append(part)
    return segments


def degree_tail(segment: str) -> str | None:
    """Major named after a degree ("S1 Hukum" -> "Hukum"); "" when only the degree is given; None when not a degree."""
    text = segment.strip()
    western = re.match(r"^(?:bachelor|master|associate)(?:['’]s)?(?:\s+degree)?\b[\s:,–-]*", text, re.I)
    if western:
        rest = re.sub(r"^(?:of|in)\s+", "", text[western.end():], flags=re.I)
        inner = re.match(
            r"^(?:science|arts|engineering|applied science|business administration|laws?|education|technology|fine arts)\s+in\s+(.+)",
            rest,
            re.I,
        )
        return (inner[1] if inner else rest).strip(" ,;·-–")
    local = re.match(r"^(?:S[- ]?[123]|D[- ]?[34]|diploma\s+(?:IV|III|4|3)|sarjana|magister|doktor|ph\.?d\.?|high school diploma)\b[\s:,–-]*", text, re.I)
    if not local:
        return None
    rest = re.sub(r"^(?:S[- ]?[123]|D[- ]?[34]|sarjana|magister|master|diploma|doktor)\b[\s:,–-]*", "", text[local.end():], flags=re.I)
    return rest.strip(" ,;·-–")


def refine_education(block: list[str], campus: str, major: str) -> tuple[str, str]:
    """Clean a campus that swallowed GPA/dates/separators and fill campus or major the line-based rules missed."""
    segments = education_segments(block)
    if not campus or DIRTY_CAMPUS.search(campus):
        named = next((s for s in segments if CAMPUS.search(s) and degree_tail(s) is None), "")
        if not named and not campus:
            named = next(
                (s for s in segments[:2] if degree_tail(s) is None and not MAJOR.search(s)
                 and re.match(r"[^\W\d_]", s) and 2 <= len(s) <= 80),
                "",
            )
        if named:
            campus = named
        elif campus:
            campus = SEGMENT_SPLIT.split(campus)[0].strip(" ,;·|()–—-")
    if not major or re.match(r"(?:science|arts|engineering)\s+in\s+", major, re.I):
        for index, segment in enumerate(segments):
            tail = degree_tail(segment)
            if tail is None:
                continue
            if not tail:
                tail = next((t for t in segments[index + 1:] if t != campus and degree_tail(t) is None and not CAMPUS.search(t)), "")
            else:
                following = segments[index + 1] if index + 1 < len(segments) else ""
                if (
                    following
                    and following != campus
                    and not CAMPUS.search(following)
                    and degree_tail(following) is None
                    and re.fullmatch(r"[A-Z][A-Za-z&/ -]{1,30}", following)
                    and len(following.split()) <= 2
                    and any(CAMPUS.search(s) for s in segments[index + 2 :])
                ):
                    tail = f"{tail} {following}"  # a major the PDF wrapped onto its own line ("... Informatics" / "Engineering")
            major = tail or major
            break
    if not major and re.match(r"SM[AK][NS]?(?=\b|\d)", campus):
        # A school has no degree word: the line below its name is the track ("Rekayasa Perangkat Lunak", "IPA").
        after = segments[segments.index(campus) + 1 :] if campus in segments else []
        major = next((s for s in after if degree_tail(s) is None and not CAMPUS.search(s) and re.match(r"[^\W\d_]", s)), "")
    return TRAILING_LOCATION.sub("", campus).strip(), major


def display_date(date: dict | None) -> str:
    """Keep YYYY-MM and "present" as parsed; a year-only date stays a year instead of an invented month."""
    if not date:
        return ""
    value = date.get("value") or ""
    return value[:4] if date.get("precision") == "year" else value


def column_boundary(lines: list[PdfLine], width: float) -> float | None:
    """x that separates a left sidebar from the main column, or None for a single-column page."""
    # Restrict the split to layouts with separate, clearly labelled sidebar and body sections.
    headings = [(line, HEADINGS.get(line.text.rstrip(":").strip().casefold())) for line in lines]
    main = [line.x for line, label in headings if label in {"experience", "education"}]
    # Summary can sit in either column, so it counts as sidebar only when it is clearly left of the jobs.
    sidebar_labels = {"contact", "skills", "languages", "certifications", "summary"}
    sidebar = [
        line.x for line, label in headings
        if label in sidebar_labels and main and min(main) - line.x >= max(60, width * 0.15)
    ]
    if not main or not sidebar:
        return None
    return (min(main) + min(sidebar)) / 2


def split_at(lines: list[PdfLine], boundary: float | None) -> tuple[list[PdfLine], list[PdfLine]]:
    if boundary is None:
        return lines, []
    return [line for line in lines if line.x >= boundary], sorted(
        (line for line in lines if line.x < boundary), key=lambda line: (line.y, line.x)
    )


def split_pdf_columns(lines: list[PdfLine], width: float) -> tuple[list[PdfLine], list[PdfLine]]:
    return split_at(lines, column_boundary(lines, width))


def word_text(content: bytes) -> str:
    if content.startswith(b"\xd0\xcf\x11\xe0"):
        with tempfile.TemporaryDirectory(prefix="tig-cv-") as folder:
            path = Path(folder) / "cv.doc"
            path.write_bytes(content)
            result = subprocess.run(["antiword", str(path)], capture_output=True, timeout=5, check=True)
            return result.stdout.decode("utf-8", errors="replace")

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
            raise ValueError("DOCX uncompressed content exceeds limit.")
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    w = WORD_NAMESPACE
    for paragraph in root.iter(f"{w}p"):
        visible: list[str] = []
        for run in paragraph.iter(f"{w}r"):
            properties = run.find(f"{w}rPr")
            if properties is not None:
                hidden = properties.find(f"{w}vanish")
                color = properties.find(f"{w}color")
                if hidden is not None and hidden.get(f"{w}val", "true").lower() not in {"false", "0", "off"}:
                    continue
                if color is not None and color.get(f"{w}val", "").casefold() == "ffffff":
                    continue
            visible.extend(node.text or "" for node in run.iter(f"{w}t"))
        paragraphs.append("".join(visible))
    return "\n".join(paragraphs)


def cv_text(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            if doc.is_encrypted or len(doc) > 25:
                return ""
            body: list[str] = []
            sidebars: list[str] = []
            boundary = None
            for page in doc:
                lines = visible_pdf_lines(page)
                # A later page often has no sidebar heading of its own but keeps the same two columns.
                boundary = column_boundary(lines, page.rect.width) or boundary
                main, sidebar = split_at(lines, boundary)
                body.extend(line.text for line in main)
                sidebars.extend(line.text for line in sidebar)
        return "\n".join(body + sidebars)
    if content.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0")):
        return word_text(content)
    return ""


def education_major(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        match = MAJOR.search(line)
        if not match:
            continue
        major = match[1].strip()
        if not EDUCATION_DATES.search(major) and index + 1 < len(lines):
            continuation = lines[index + 1]
            if not GPA.search(continuation) and not MAJOR.search(continuation) and EDUCATION_DATES.search(continuation):
                major += " " + continuation
        return EDUCATION_DATES.sub("", major).strip(" ·,|")
    return ""


def education_entries(lines: list[str]) -> list[dict]:
    # Each explicit institution starts an entry; preserve adjacent degree and GPA lines for review.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        new_campus = CAMPUS.search(line) and not MAJOR.search(line) and any(CAMPUS.search(prior) for prior in current)
        # Degree-first layout: a second degree line starts the next entry once the current one has its campus and degree.
        new_degree = (
            degree_tail(line) is not None
            and any(CAMPUS.search(prior) for prior in current)
            and any(degree_tail(prior) is not None for prior in current)
        )
        if new_campus or new_degree:
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)

    entries = []
    for block in blocks[:12]:
        combined = "\n".join(block)
        level = next((value for value, pattern in DEGREES if re.search(pattern, combined, re.I)), None)
        campus = next((line for line in block if CAMPUS.search(line) and not MAJOR.search(line)), "")
        major = education_major(block)
        gpa = GPA.search(combined)
        gpa_value = float(gpa[1].replace(",", ".")) if gpa else None
        campus, major = refine_education(block, campus, major)
        entries.append(
            {
                "level": level,
                "campus": campus[:220],
                "major": major[:220],
                "gpa": gpa_value if gpa_value is not None and gpa_value <= 4 else None,
            }
        )
    return entries


DESCRIBED_SECTIONS = {"projects", "experience", "training", "organizations"}
# Zero-width characters, bidi marks, soft hyphens and private-use glyphs (Symbol/Wingdings bullets) carry no text.
INVISIBLE = re.compile("[­​-‏⁠﻿-]")
LOCATION_LABEL = re.compile(r"^\s*(?:domisili|kota|location|address|alamat)\s*:\s*(.+)$", re.I | re.M)
EXPLICIT_LINK = re.compile(
    r"(?:https?://|www\.)[^\s|,;]+|\b(?:[\w-]+\.)?(?:linkedin\.com/in|github\.com|gitlab\.com|behance\.net|dribbble\.com)/[^\s|,;]+",
    re.I,
)
LABELLED_LINKS = (
    (re.compile(r"\blinkedin\s*:\s*((?:https?://)?(?:www\.)?(?:linkedin\.com/)?(?:in/)?[\w%.-]+)", re.I), "https://linkedin.com/in/"),
    (re.compile(r"\bgithub\s*:\s*((?:https?://)?(?:www\.)?(?:github\.com/)?[\w%.-]+)", re.I), "https://github.com/"),
    (re.compile(r"\b(?:website|portfolio|portofolio|situs|blog)\s*:\s*((?:https?://)?[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}(?:/[^\s|,;]*)?)", re.I), "https://"),
)


def drop_repeated_page_header(lines: list[str]) -> list[str]:
    """Multi-page CVs repeat the name block at the top of every page; keep the first copy only."""
    if len(lines) < 8:
        return lines
    kept = lines[:1]
    index = 1
    while index < len(lines):
        if index >= 4 and lines[index] == lines[0]:
            cursor, offset = index + 1, 1
            while cursor < len(lines) and offset < 6 and lines[cursor] == lines[offset]:
                cursor, offset = cursor + 1, offset + 1
            index = cursor
            continue
        kept.append(lines[index])
        index += 1
    return kept


LABELLED_PHONE = re.compile(
    r"^\s*(?:phone|telepon|telp|tel|hp|mobile|whatsapp|wa|no\.?\s*hp)\s*[:.]?\s*(\+?[\d(][\d()\s.-]{7,22}\d)", re.I | re.M
)


def contact_location(lines: list[str]) -> str:
    """"Cibiru, Bandung 40615 • 0812 … • name@host": the place on a contact line, without the postal code."""
    for line in lines[:6]:
        if not (EMAIL_REGEX.search(line) or PHONE_REGEX.search(line)):
            continue
        for segment in re.split(r"\s*[•|·]\s*", line):
            place = re.sub(r"\s+\d{5}\b.*$", "", segment.strip())
            if re.fullmatch(r"[^\W\d_][\w .'-]*(?:\s*,\s*[^\W\d_][\w .'-]*)+", place):
                return place
    return ""


def wrapped_header_location(lines: list[str]) -> str:
    """"... |Bandung," on one line and "Indonesia" on the next."""
    for first, second in zip(lines[:8], lines[1:9]):
        if second.casefold() == "indonesia":
            city = re.split(r"\s*\|\s*", first)[-1].strip(" ,")
            if re.fullmatch(r"[^\W\d_][\w .'-]{1,38}", city):
                return f"{city}, Indonesia"
    return ""


def extract_links(lines: list[str]) -> list[str]:
    blob = "\n".join(lines)
    found: list[str] = []

    def add(url: str) -> None:
        url = url.strip().rstrip(".,;|)")
        if not re.match(r"https?://", url, re.I):
            url = "https://" + url
        if url.casefold() not in {known.casefold() for known in found}:
            found.append(url)

    for match in EXPLICIT_LINK.finditer(blob):
        add(match[0])
    for pattern, prefix in LABELLED_LINKS:
        for match in pattern.finditer(blob):
            value = match[1].removeprefix("in/") if prefix.endswith("/in/") else match[1]
            add(value if re.match(r"(?:https?://|www\.|[\w-]+\.(?:com|net)/)", value, re.I) else prefix + value)
    return found[:5]


def prefill_form(content: bytes) -> dict:
    try:
        text = INVISIBLE.sub("", cv_text(content)).strip()[:40_000]
    except (
        RuntimeError,
        ValueError,
        OSError,
        zipfile.BadZipFile,
        KeyError,
        ElementTree.ParseError,
        subprocess.SubprocessError,
    ):
        text = ""
    if not text:
        return {"form": {}, "notice": "Teks CV tidak terbaca. Silakan isi formulir secara manual."}

    sections: dict[str, list[str]] = defaultdict(list)
    section = "header"
    clean_lines = [raw.strip(" \t•●▪◦■") for raw in text.splitlines()]
    for line in drop_repeated_page_header([line for line in clean_lines if line]):
        heading, separator, tail = line.partition(":")
        label = HEADINGS.get(heading.strip().casefold())
        if label == "languages" and section == "languages" and not separator and heading.strip().casefold() == "language":
            label = None  # "Indonesian - First" / "Language": the word wrapped onto its own line, not a new heading
        if label == "summary" and tail.strip() and section in DESCRIBED_SECTIONS:
            label = None  # "Deskripsi: ..." inside a project or job is that entry's description, not a new section
        if label:
            section = label
            line = tail.strip() if separator else ""
        if line:
            sections[section].append(line)

    contact_lines = sections["contact"] + sections["personal_info"] + sections["header"]
    email = next((match for line in contact_lines if (match := EMAIL_REGEX.search(line))), None) or EMAIL_REGEX.search(
        text
    )
    phone = next((match for line in contact_lines if (match := PHONE_REGEX.search(line))), None)
    labelled_phone = LABELLED_PHONE.search(text)
    phone_text = phone[0].strip() if phone else (labelled_phone[1].strip() if labelled_phone else "")
    header_name = next(
        (
            line
            for line in sections["header"]
            if re.fullmatch(r"[^\W\d_][^\W\d_. -]*(?:[. -]+[^\W\d_][^\W\d_. -]*){1,5}", line)
        ),
        None,
    )
    if header_name is None:
        named_line = re.search(r"^\s*(?:nama lengkap|nama|full name)\s*:\s*(.+)$", text, re.I | re.M)
        header_name = named_line[1].strip() if named_line else None
    full_name = resolve_candidate_name_consensus(header_name, text, email=email[0] if email else None)

    domicile = LOCATION_LABEL.search(text)
    domicile_text = re.split(r"\s+\|\s+", domicile[1])[0].strip() if domicile else ""
    if not domicile_text:
        match = next((match for line in contact_lines if (match := INDONESIAN_LOCATION.fullmatch(line))), None)
        head_lines = [line for line in clean_lines if line][:10]
        domicile_text = match[1].strip() if match else contact_location(head_lines) or wrapped_header_location(head_lines)
    experience = parse_experiences("\n".join(sections["experience"]))[:20]
    return {
        "form": {
            "full_name": (full_name or "")[:160],
            "email": (email[0] if email else "")[:254],
            "phone": phone_text[:32],
            "preferences": {"domicile": domicile_text[:220]},
            "education": education_entries(sections["education"]),
            "experiences": [
                {
                    "title": str(item.get("title") or "")[:220],
                    "organization": str(item.get("organization") or "")[:220],
                    "start": display_date(item.get("start"))[:220],
                    "end": display_date(item.get("end"))[:220],
                    "description": "\n".join(item.get("bullets", []))[:1800],
                }
                for item in experience
            ],
            "skills": [item[:220] for item in parse_skills("\n".join(sections["skills"]))[:40]],
            "languages": [item[:220] for item in parse_skills("\n".join(sections["languages"]), expand_parentheses=False)[:12]],
            "certifications": [item[:220] for item in parse_certifications("\n".join(sections["certifications"]))[:20]],
            "projects": [item[:1800] for item in parse_projects("\n".join(sections["projects"]))[:12]],
            "links": extract_links(sections["header"] + sections["contact"] + sections["personal_info"]),
        },
        "notice": "Isian yang terbaca sudah dimasukkan. Periksa dan koreksi sebelum mengirim.",
    }
