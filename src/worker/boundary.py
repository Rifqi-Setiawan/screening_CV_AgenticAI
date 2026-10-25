"""Smart Document Boundary Isolator: separates core CV/Resume pages from
auxiliary portfolio showcases, scanned certificates, and academic transcripts
without imposing arbitrary page number limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ATTACHMENT_INDICATORS = [
    re.compile(
        r"^\s*(?:lampiran|attachment|kumpulan\s+karya|project\s+showcase|galeri\s+proyek|screens(?:hots)?|desain\s+arsitektur|denah|gambar\s+kerja)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*(?:transkrip\s+nilai|daftar\s+nilai|academic\s+transcript|kartu\s+hasil\s+studi|khs)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*(?:surat\s+keterangan\s+lulus|skl|ijazah|diploma|certificate\s+of\s+completion|piagam\s+penghargaan)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*(?:surat\s+keterangan\s+catatan\s+kepolisian|skck|kartu\s+tanda\s+penduduk|ktp|kartu\s+keluarga)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
]

CV_CORE_INDICATORS = [
    re.compile(
        r"\b(?:pengalaman(?:\s+kerja)?|work\s+experience|professional\s+experience|employment\s+history|riwayat\s+pekerjaan|pengalaman\s+organisasi)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:pendidikan|education|educational\s+background|riwayat\s+pendidikan|academic\s+history)\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(?:keahlian|skills|technical\s+skills|kemampuan|kompetensi|ringkasan\s+profesional|professional\s+summary)\b",
        re.IGNORECASE,
    ),
]


@dataclass
class PageClassification:
    page_num: int
    page_type: str  # CV_CORE, PORTFOLIO_PROJECT, ATTACHMENT_ACADEMIC, ATTACHMENT_ADMIN
    confidence: float
    detected_headers: list[str] = field(default_factory=list)


@dataclass
class BoundaryResult:
    total_pages: int
    cv_core_pages: list[int]
    attachment_pages: list[int]
    cv_core_text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)


def isolate_document_boundaries(pages: list[dict[str, Any]]) -> BoundaryResult:
    """Classifies each page structurally into CV_CORE vs ATTACHMENTS dynamically."""
    cv_core_pages: list[int] = []
    attachment_pages: list[int] = []
    classified_pages: list[PageClassification] = []
    attachments_list: list[dict[str, Any]] = []

    # State tracking: once we hit pure certificates/transcripts at the end, subsequent pages are attachments
    has_entered_attachments = False

    for idx, p in enumerate(pages, 1):
        text = p.get("text", "").strip()
        img_count = p.get("image_count", 0)
        word_count = len(text.split())

        has_cv_core = any(ind.search(text) for ind in CV_CORE_INDICATORS)
        is_attachment_title = any(ind.search(text[:300]) for ind in ATTACHMENT_INDICATORS)

        page_type = "CV_CORE"

        if is_attachment_title:
            has_entered_attachments = True
            page_type = (
                "PORTFOLIO_PROJECT"
                if "proyek" in text.lower() or "portfolio" in text.lower()
                else "ATTACHMENT_ACADEMIC"
            )
        elif has_entered_attachments:
            # If we already passed an attachment header and there are no strong CV Core headings, treat as attachment
            if not has_cv_core or word_count < 100:
                page_type = "PORTFOLIO_PROJECT"
        elif not has_cv_core and word_count < 80 and img_count > 0:
            # Low text with images on later pages
            if idx > 2:
                page_type = "PORTFOLIO_PROJECT"

        classified_pages.append(PageClassification(page_num=idx, page_type=page_type, confidence=0.9))

        if page_type == "CV_CORE":
            cv_core_pages.append(idx)
        else:
            attachment_pages.append(idx)
            attachments_list.append(
                {
                    "page_number": idx,
                    "type": page_type,
                    "preview": text[:200] if text else "[Image/Scan Page]",
                }
            )

    # Fallback safety: If by some edge-case no page was marked CV_CORE, designate page 1 as CV_CORE
    if not cv_core_pages and pages:
        cv_core_pages = [1]
        attachment_pages = [p for p in attachment_pages if p != 1]

    cv_core_text = "\n\n".join([pages[p - 1].get("text", "") for p in cv_core_pages if p - 1 < len(pages)])

    return BoundaryResult(
        total_pages=len(pages),
        cv_core_pages=cv_core_pages,
        attachment_pages=attachment_pages,
        cv_core_text=cv_core_text,
        attachments=attachments_list,
    )
