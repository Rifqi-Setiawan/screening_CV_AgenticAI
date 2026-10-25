"""Production adapter converting raw cv-extractor output into CandidateProfile with provenance."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# Ensure cv_extractor is accessible
CV_EXTRACTOR_SRC = Path("/srv/hermes-control/services/cv-extractor/src")
if str(CV_EXTRACTOR_SRC) not in sys.path:
    sys.path.insert(0, str(CV_EXTRACTOR_SRC))

from cv_extractor.application.config import LlmConfig, OcrConfig, PipelineConfig
from cv_extractor.bootstrap import build_service

from src.worker.anchor import resolve_candidate_name_consensus
from src.worker.boundary import isolate_document_boundaries
from src.worker.docling_parser import parse_with_docling

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

_extractor_service = None


def get_extractor_service():
    global _extractor_service
    if _extractor_service is None:
        _extractor_service = build_service(PipelineConfig(ocr=OcrConfig(), llm=LlmConfig(enabled=False)))
    return _extractor_service


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


def find_provenance(full_text: str, quote: str, default_page: int = 1) -> dict[str, Any]:
    if not quote or not full_text:
        return {"page": default_page, "char_start": 0, "char_end": 0, "text": quote, "verified": False}
    clean_q = quote.strip()
    idx = full_text.find(clean_q)
    if idx >= 0:
        return {
            "page": default_page,
            "char_start": idx,
            "char_end": idx + len(clean_q),
            "text": clean_q,
            "verified": True,
        }
    return {"page": default_page, "char_start": 0, "char_end": 0, "text": clean_q, "verified": False}


def parse_experiences(section_text: str, full_doc_text: str) -> list[dict[str, Any]]:
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

    for i, (idx, raw_start, raw_end, m_start, _m_end) in enumerate(date_lines):
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
        block_text = " ".join([curr_line, title, org] + bullet_lines).lower()

        # Context & employment type classification
        emp_type = "full_time"
        context_type = "experience"
        if "intern" in block_text or "magang" in block_text:
            emp_type = "internship"
            context_type = "internship"
        elif "freelance" in block_text or "lepas" in block_text:
            emp_type = "freelance"
            context_type = "freelance"
        elif "kontrak" in block_text or "contract" in block_text:
            emp_type = "contract"
        elif "part-time" in block_text or "paruh waktu" in block_text:
            emp_type = "part_time"

        bullets = []
        for bl in bullet_lines:
            bl_clean = bl.lstrip("•-* ").strip()
            if len(bl_clean) > 5 and not RANGE_REGEX.search(bl):
                bullets.append(
                    {
                        "text": bl_clean,
                        "source": find_provenance(full_doc_text, bl_clean),
                        "has_quantified_result": bool(
                            re.search(r"\d+[%kKmM]|meningkatkan|menurunkan|cut|reduced", bl_clean)
                        ),
                    }
                )

        if title:
            title = re.split(r"[—|]", title)[0].strip()
            entries.append(
                {
                    "entry_id": f"exp_{len(entries) + 1}",
                    "title": title,
                    "organization": org,
                    "start": start_date,
                    "end": end_date,
                    "context": context_type,
                    "employment_type": emp_type,
                    "bullets": bullets,
                    "source": find_provenance(full_doc_text, title),
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


def parse_certifications(ce_text: str, ed_text: str) -> list[str]:
    combined = ce_text
    if "sertifikasi" in ed_text.lower() or "certification" in ed_text.lower():
        parts = re.split(r"~?\s*(?:sertifikasi|certifications?)\b", ed_text, flags=re.IGNORECASE)
        if len(parts) > 1:
            combined += "\n" + parts[1]

    lines = [l.strip().lstrip("-•*~ ").strip() for l in combined.splitlines() if l.strip()]
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


def parse_education(section_text: str, full_doc_text: str) -> list[dict[str, Any]]:
    levels = []
    t = (section_text + " " + full_doc_text).lower()
    if re.search(r"\bs1\b|sarjana|bachelor|\bs\.e\b|\bs\.stat\b", t):
        levels.append("S1")
    if re.search(r"\bs2\b|magister|master|\bmba\b", t):
        levels.append("S2")
    if re.search(r"\bd3\b|diploma 3|diploma iii", t):
        levels.append("D3")
    if re.search(r"\bd4\b|diploma 4|diploma iv", t):
        levels.append("D4")
    if re.search(r"\bsmk\b", t):
        levels.append("SMK")
    if re.search(r"\bsma\b", t):
        levels.append("SMA")
    if not levels and re.search(r"universitas|institut|politeknik|college|uin|graduate|lulusan", t):
        levels.append("S1")

    entries = []
    ed_lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    for idx, lvl in enumerate(levels):
        deg_raw = " ".join(ed_lines[:4]) if ed_lines else lvl
        inst = ""
        for l in ed_lines:
            if any(
                u in l.lower()
                for u in [
                    "universitas",
                    "university",
                    "institut",
                    "institute",
                    "politeknik",
                    "uin",
                    "itb",
                    "ugm",
                    "unpad",
                    "unri",
                    "unisba",
                    "unpas",
                    "ipb",
                ]
            ):
                inst = l
                break
        entries.append(
            {
                "entry_id": f"edu_{idx + 1}",
                "level": lvl,
                "degree_raw": deg_raw,
                "institution": inst,
                "source": find_provenance(full_doc_text, lvl),
            }
        )
    return entries


def strip_hidden_pdf_spans(content: bytes) -> bytes:
    """Strips micro-font (<4pt) and injection phrases from PDF to prevent evaluation pollution."""
    try:
        import fitz

        doc = fitz.open(stream=content, filetype="pdf")
        has_hidden = False
        inj_pats = [
            re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
            re.compile(r"evaluation\s+override\s+mode", re.IGNORECASE),
            re.compile(r"abaikan\s+semua\s+instruksi", re.IGNORECASE),
            re.compile(r"beri\s+nilai\s+100", re.IGNORECASE),
        ]
        for page in doc:
            for b in page.get_text("dict").get("blocks", []):
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        sz = span.get("size", 10)
                        txt = span.get("text", "")
                        is_inj = any(pat.search(txt) for pat in inj_pats)
                        if sz < 4.0 or is_inj:
                            has_hidden = True
                            rect = fitz.Rect(span["bbox"])
                            page.add_redact_annot(rect)
            if has_hidden:
                page.apply_redactions()
        if has_hidden:
            out = doc.write()
            doc.close()
            return out
        doc.close()
        return content
    except Exception:
        return content


def sanitize_extracted_name(name: str | None, full_text: str, filename: str) -> str | None:
    bad_pats = [
        r"hiring\s+manager",
        r"^hal\s*:",
        r"lamaran",
        r"curriculum\s+vitae",
        r"^resume",
        r"job\s+application",
        r"application\s+letter",
        r"kepada\s+yth",
    ]
    raw_clean = (name or "").strip()
    is_bad = not raw_clean or any(re.search(p, raw_clean, re.IGNORECASE) for p in bad_pats)

    if raw_clean and not is_bad:
        parts = re.split(r"\s{2,}|\n", raw_clean)
        if len(parts) >= 2:
            longest = max(parts, key=len).strip()
            if len(longest.split()) >= 2:
                raw_clean = longest
        return re.sub(r"\s+", " ", raw_clean)

    # 1. Cover letter self-intro: e.g. 'I am, Pijar Sulthan Muhammad, excited to apply'
    m_intro = re.search(
        r"(?:I\s+am|saya),?\s+([A-Z][A-Za-z\s]{2,35})(?:,|\s+excited|\s+bermaksud|\.|\s+ingin)",
        full_text,
    )
    if m_intro:
        cand = m_intro.group(1).strip()
        if len(cand.split()) >= 2 and not any(re.search(p, cand, re.IGNORECASE) for p in bad_pats):
            return re.sub(r"\s+", " ", cand)

    # 2. Uppercase header block from first lines of full_text
    for line in full_text.splitlines()[:60]:
        line_clean = line.strip()
        if (
            line_clean.isupper()
            and 2 <= len(line_clean.split()) <= 4
            and not any(re.search(p, line_clean, re.IGNORECASE) for p in bad_pats)
            and not any(
                w in line_clean
                for w in ["EDUCATION", "SKILLS", "EXPERIENCE", "SUMMARY", "CURRICULUM", "VITAE"]
            )
        ):
            return line_clean.title()

    # 3. Fallback from filename: e.g. '2404_Pijar Sulthan Muhammad_CV...'
    fname_stem = Path(filename).stem
    parts = fname_stem.split("_")
    if len(parts) >= 2 and parts[0].isdigit():
        return parts[1].strip()

    return raw_clean or None


def extract_candidate_profile(content: bytes, filename: str) -> dict[str, Any]:
    portfolio_attachments: list[dict[str, Any]] = []
    if filename.lower().endswith(".pdf"):
        content = strip_hidden_pdf_spans(content)
        # Smart Document Boundary Isolator (Decision 2: Opsi A - isolate attachments)
        try:
            import pymupdf as fitz

            doc = fitz.open(stream=content, filetype="pdf")
            pages_data = [{"text": doc[i].get_text(), "image_count": len(doc[i].get_images())} for i in range(len(doc))]
            boundary = isolate_document_boundaries(pages_data)
            portfolio_attachments = boundary.attachments

            # If there are attachment pages, trim content to only CV core pages for profile extraction
            if len(boundary.cv_core_pages) < len(pages_data) and boundary.cv_core_pages:
                trimmed_doc = fitz.open()
                for pno in boundary.cv_core_pages:
                    trimmed_doc.insert_pdf(doc, from_page=pno - 1, to_page=pno - 1)
                content = trimmed_doc.tobytes()
                trimmed_doc.close()
            doc.close()
        except Exception:
            pass

    service = get_extractor_service()
    raw = service.extract(content, filename).to_dict()

    sec_map: dict[str, list[str]] = {}
    for s in raw.get("sections", []):
        sec_map.setdefault(s["label"], []).append(s.get("text", ""))

    exp_text = "\n".join(sec_map.get("experience", []))
    sk_text = "\n".join(sec_map.get("skills", []))
    ce_text = "\n".join(sec_map.get("certifications", []))
    ed_text = "\n".join(sec_map.get("education", []))
    sum_text = "\n".join(sec_map.get("summary", []))
    prj_text = "\n".join(sec_map.get("projects", []))
    org_text = "\n".join(sec_map.get("organizations", []) + sec_map.get("training", []))
    ach_text = "\n".join(sec_map.get("awards", []) + sec_map.get("achievements", []))

    # Docling Hybrid Fallback for messy/disordered layouts (Decision 3: Opsi A)
    if (raw.get("meta", {}).get("confidence", 1.0) < 0.60 or not exp_text.strip()) and filename.lower().endswith(".pdf"):
        docling_res = parse_with_docling(content, filename)
        if docling_res and docling_res.get("sections"):
            for s in docling_res["sections"]:
                h_lower = s.get("heading", "").lower()
                t_content = s.get("text", "").strip()
                if not t_content:
                    continue
                if any(w in h_lower for w in ["experience", "pengalaman", "pekerjaan", "kerja"]):
                    sec_map.setdefault("experience", []).append(t_content)
                elif any(w in h_lower for w in ["education", "pendidikan", "akademik", "studi"]):
                    sec_map.setdefault("education", []).append(t_content)
                elif any(w in h_lower for w in ["skill", "keahlian", "kemampuan", "tools"]):
                    sec_map.setdefault("skills", []).append(t_content)
            exp_text = "\n".join(sec_map.get("experience", []))
            ed_text = "\n".join(sec_map.get("education", []))
            sk_text = "\n".join(sec_map.get("skills", []))

    full_text = "\n".join(s.get("text", "") for s in raw.get("sections", []))

    # Fallback for skills: harvest lines from additional_info, other, and summary if skills are sparse
    sk_lines = [sk_text] if sk_text else []
    for extra_lbl in ("additional_info", "other", "summary"):
        for text in sec_map.get(extra_lbl, []):
            m_sk = re.search(
                r"(?:skills?|keahlian|kemampuan|technical skills?|hard skills?)\s*:\s*(.+)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if m_sk:
                sk_lines.append(m_sk.group(1).strip())
            else:
                for line in text.splitlines():
                    if any(
                        w in line.lower()
                        for w in [
                            "skill",
                            "keahlian",
                            "kemampuan",
                            "tools",
                            "software",
                            "excel",
                            "stata",
                            "spss",
                            "python",
                            "sql",
                            "tableau",
                            "power bi",
                            "looker",
                            "accounting",
                        ]
                    ):
                        sk_lines.append(line)
    if sk_lines:
        sk_text = "\n".join(sk_lines)

    # Harvest any experiences in other that contain dates and professional job keywords
    extra_exp_blocks = []
    for text in sec_map.get("other", []):
        if RANGE_REGEX.search(text) and any(
            w in text.lower()
            for w in [
                "developer",
                "engineer",
                "analyst",
                "manager",
                "intern",
                "magang",
                "specialist",
                "officer",
                "consultant",
                "staff",
                "supervisor",
                "freelance",
                "trainer",
                "volunteer",
            ]
        ):
            extra_exp_blocks.append(text)

    if extra_exp_blocks:
        exp_text = exp_text + "\n" + "\n".join(extra_exp_blocks) if exp_text.strip() else "\n".join(extra_exp_blocks)

    # Fallback for experience: if exp_text is still empty, inspect other and summary
    if not exp_text.strip():
        exp_fallbacks = []
        for extra_lbl in ("other", "summary"):
            for text in sec_map.get(extra_lbl, []):
                if any(
                    w in text.lower() for w in ["magang", "intern", "experience", "kerja", "analyst"]
                ) or RANGE_REGEX.search(text):
                    exp_fallbacks.append(text)
        if exp_fallbacks:
            exp_text = "\n".join(exp_fallbacks)

    # Fallback for education: if ed_text is empty, inspect other and summary
    if not ed_text.strip():
        ed_fallbacks = []
        for extra_lbl in ("other", "summary"):
            for text in sec_map.get(extra_lbl, []):
                if any(
                    w in text.lower()
                    for w in [
                        "universitas",
                        "university",
                        "institut",
                        "bachelor",
                        "master",
                        "sarjana",
                        "s1",
                        "s2",
                        "d3",
                    ]
                ):
                    ed_fallbacks.append(text)
        if ed_fallbacks:
            ed_text = "\n".join(ed_fallbacks)

    # Parse sections
    experiences = parse_experiences(exp_text, full_text)
    education = parse_education(ed_text, full_text)
    certifications = parse_certifications(ce_text, ed_text)
    skills = parse_skills(sk_text)

    # Demographics & Identity
    contact = raw.get("contact", {})
    emails = contact.get("emails", [])
    phones = contact.get("phones", [])
    links = contact.get("urls", [])
    if contact.get("linkedin"):
        links.append(contact["linkedin"])

    # Look for demographic lines in full text
    other_personal = {}
    m_gender = re.search(r"jenis\s+kelamin\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_gender:
        other_personal["gender"] = m_gender.group(1).strip()
    m_rel = re.search(r"agama\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_rel:
        other_personal["religion"] = m_rel.group(1).strip()
    m_dob = re.search(r"tanggal\s+lahir\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_dob:
        other_personal["date_of_birth"] = m_dob.group(1).strip()
    m_mar = re.search(r"status(?:\s+pernikahan)?\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_mar:
        other_personal["marital_status"] = m_mar.group(1).strip()

    identity = {
        "full_name": resolve_candidate_name_consensus(
            raw.get("name"), full_text, filename, email=emails[0] if emails else None
        ),
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "location_raw": contact.get("location"),
        "links": links,
        "other_personal": other_personal,
    }

    projects = []
    if prj_text:
        projects.append(
            {
                "entry_id": "prj_1",
                "title": prj_text.splitlines()[0] if prj_text else "Proyek",
                "text": prj_text,
                "source": find_provenance(full_text, prj_text[:40]),
            }
        )

    organizations = []
    if org_text:
        organizations.append(
            {
                "entry_id": "org_1",
                "title": org_text.splitlines()[0] if org_text else "Organisasi",
                "text": org_text,
                "source": find_provenance(full_text, org_text[:40]),
            }
        )

    achievements = []
    if ach_text:
        for idx, block in enumerate([b.strip() for b in ach_text.split("\n\n") if b.strip()]):
            achievements.append(
                {
                    "entry_id": f"ach_{idx+1}",
                    "title": block.splitlines()[0] if block else "Achievement",
                    "text": block,
                    "source": find_provenance(full_text, block[:40]),
                }
            )

    profile = {
        "document_id": filename,
        "extractor": {
            "name": "cv-extractor",
            "version": "1.0.0",
            "ocr_used": raw.get("meta", {}).get("llm_used", False)
            or any(p.get("source") == "ocr" for p in raw.get("meta", {}).get("pages", [])),
        },
        "language": ["id"],
        "identity": identity,
        "headline": raw.get("headline"),
        "summary": sum_text or raw.get("summary"),
        "skills": skills,
        "experiences": experiences,
        "education": education,
        "certifications": certifications,
        "projects": projects,
        "organizations": organizations,
        "achievements": achievements,
        "portfolio_attachments": portfolio_attachments,
        "quality": {
            "confidence": raw.get("meta", {}).get("confidence", 1.0),
            "warnings": raw.get("meta", {}).get("warnings", []),
        },
    }
    return profile
