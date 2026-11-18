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
from src.worker.cv_text import parse_certifications, parse_experiences, parse_skills
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
        "soft skills",
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
HEADINGS = {alias: label for label, aliases in SECTION_ALIASES.items() for alias in aliases}
DEGREES = (
    ("S3", r"\b(?:S[- ]?3|doktor|ph\.?d\.?)\b"),
    ("S2", r"\b(?:S[- ]?2|magister|master|mba)\b"),
    ("S1", r"\b(?:S[- ]?1|sarjana|bachelor)\b"),
    ("D4", r"\b(?:D[- ]?4|diploma (?:IV|4))\b"),
    ("D3", r"\b(?:D[- ]?3|diploma (?:III|3))\b"),
    ("SMA/SMK", r"\b(?:SM[AK][NS]?(?=\b|\d)|high school)\b"),
)
CAMPUS = re.compile(
    r"\b(?:universitas|university|institute|institut|politeknik|polytechnic|akademi|college|sekolah tinggi|UIN|ITB|UGM|UI|IPB|ITS)\b|\bSM[AK][NS]?(?=\b|\d)",
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


def split_pdf_columns(lines: list[PdfLine], width: float) -> tuple[list[PdfLine], list[PdfLine]]:
    # Restrict the split to layouts with separate, clearly labelled sidebar and body sections.
    headings = [(line, HEADINGS.get(line.text.rstrip(":").strip().casefold())) for line in lines]
    main = [line.x for line, label in headings if label in {"summary", "experience", "education"}]
    sidebar = [line.x for line, label in headings if label in {"contact", "skills", "languages", "certifications"}]
    if not main or not sidebar or min(main) - min(sidebar) < max(60, width * 0.15):
        return lines, []
    boundary = (min(main) + min(sidebar)) / 2
    return [line for line in lines if line.x >= boundary], sorted(
        (line for line in lines if line.x < boundary), key=lambda line: (line.y, line.x)
    )


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
            for page in doc:
                main, sidebar = split_pdf_columns(visible_pdf_lines(page), page.rect.width)
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
        if CAMPUS.search(line) and not MAJOR.search(line) and any(CAMPUS.search(prior) for prior in current):
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
        entries.append(
            {
                "level": level,
                "campus": campus[:220],
                "major": major[:220],
                "gpa": gpa_value if gpa_value is not None and gpa_value <= 4 else None,
            }
        )
    return entries


def prefill_form(content: bytes) -> dict:
    try:
        text = cv_text(content).strip()[:40_000]
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
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t•")
        if not line:
            continue
        heading, separator, tail = line.partition(":")
        label = HEADINGS.get(heading.strip().casefold())
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

    domicile = re.search(r"^\s*(?:domisili|kota|location)\s*:\s*(.+)$", text, re.I | re.M)
    if not domicile:
        domicile = next((match for line in contact_lines if (match := INDONESIAN_LOCATION.fullmatch(line))), None)
    experience = parse_experiences("\n".join(sections["experience"]))[:20]
    return {
        "form": {
            "full_name": (full_name or "")[:160],
            "email": (email[0] if email else "")[:254],
            "phone": (phone[0].strip() if phone else "")[:32],
            "preferences": {"domicile": domicile[1].strip()[:220] if domicile else ""},
            "education": education_entries(sections["education"]),
            "experiences": [
                {
                    "title": str(item.get("title") or "")[:220],
                    "organization": str(item.get("organization") or "")[:220],
                    "start": (item.get("start", {}).get("value") or "")[:220],
                    "end": (item.get("end", {}).get("value") or "")[:220],
                    "description": "\n".join(item.get("bullets", []))[:1800],
                }
                for item in experience
            ],
            "skills": [item[:220] for item in parse_skills("\n".join(sections["skills"]))[:40]],
            "languages": [item[:220] for item in parse_skills("\n".join(sections["languages"]))[:12]],
            "certifications": [item[:220] for item in parse_certifications("\n".join(sections["certifications"]))[:20]],
            "projects": [item[:1800] for item in sections["projects"][:12]],
        },
        "notice": "Isian yang terbaca sudah dimasukkan. Periksa dan koreksi sebelum mengirim.",
    }
