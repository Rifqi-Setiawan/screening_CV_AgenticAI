"""Pre-flight CV classifier gatekeeper: classifies whether an uploaded document
is genuinely a CV/Resume or a non-CV document (pure portfolio, single certificate,
cover letter only, administrative document, or empty noise).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CERTIFICATE_PATTERNS = [
    re.compile(
        r"\b(?:sertifikat|certificate(?:\s+of)?|piagam|diberikan\s+kepada|awarded\s+to|has\s+completed|telah\s+menyelesaikan|ijazah|transkrip\s+nilai|surat\s+tanda\s+lulus)\b",
        re.IGNORECASE,
    ),
]

COVER_LETTER_PATTERNS = [
    re.compile(
        r"\b(?:surat\s+lamaran(?:\s+pekerjaan)?|cover\s+letter|application\s+letter|kepada\s+yth|dengan\s+hormat|hal\s*:\s*lamaran|sehubungan\s+dengan\s+informasi\s+lowongan|bersama\s+surat\s+ini\s+saya)\b",
        re.IGNORECASE,
    ),
]

ADMIN_DOC_PATTERNS = [
    re.compile(
        r"\b(?:kartu\s+tanda\s+penduduk|kartu\s+keluarga|surat\s+keterangan\s+catatan\s+kepolisian|skck|paspor|surat\s+izin\s+mengemudi|nomor\s+induk\s+kependudukan|nik\s*:\s*\d{12,16})\b",
        re.IGNORECASE,
    ),
]

CV_SECTIONS_PATTERNS = [
    re.compile(
        r"\b(?:pengalaman(?:\s+kerja)?|work\s+experience|professional\s+experience|employment\s+history|riwayat\s+pekerjaan|pengalaman\s+profesional)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:pendidikan|education|educational\s+background|riwayat\s+pendidikan|academic\s+history|latar\s+belakang\s+pendidikan)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:keahlian|skills|kemampuan|technical\s+skills|kompetensi|core\s+competencies|tools\s+&\s+technologies)\b",
        re.IGNORECASE,
    ),
]

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"(?:\+62|62|08)[0-9\s\-]{8,15}")


@dataclass
class ClassificationResult:
    is_cv: bool
    doc_type: str  # CV, PURE_PORTFOLIO, CERTIFICATE_ONLY, COVER_LETTER_ONLY, ADMIN_DOC, INSUFFICIENT_CONTENT
    confidence: float
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    extracted_contact: dict[str, Any] = field(default_factory=dict)


def classify_document_is_cv(full_text: str, page_count: int = 1, total_images: int = 0) -> ClassificationResult:
    """Evaluates whether the document content is a valid CV/Resume without hardcoded page count limits."""
    clean_text = full_text.strip()
    words = clean_text.split()
    word_count = len(words)
    text_chars = len(re.sub(r"\s+", "", clean_text))

    # 1. Check Insufficient text content
    if text_chars < 50 and total_images == 0:
        return ClassificationResult(
            is_cv=False,
            doc_type="INSUFFICIENT_CONTENT",
            confidence=0.99,
            reasons=["Dokumen kosong atau tidak memuat teks yang cukup untuk dianalisis."],
            flags=["EMPTY_OR_INSUFFICIENT_CONTENT"],
        )

    # 2. Extract basic contact signals
    emails = EMAIL_PATTERN.findall(clean_text)
    phones = PHONE_PATTERN.findall(clean_text)
    has_contact = len(emails) > 0 or len(phones) > 0
    contact_data = {
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
    }

    # 3. Check for CV Sections presence
    has_experience = bool(CV_SECTIONS_PATTERNS[0].search(clean_text))
    has_education = bool(CV_SECTIONS_PATTERNS[1].search(clean_text))
    has_skills = bool(CV_SECTIONS_PATTERNS[2].search(clean_text))

    # 4. Check for Non-CV indicators
    is_cover_letter = any(p.search(clean_text[:600]) for p in COVER_LETTER_PATTERNS)
    is_admin_doc = any(p.search(clean_text) for p in ADMIN_DOC_PATTERNS)

    # Case A: Pure Administrative Document (KTP, KK, SKCK)
    if is_admin_doc and not (has_experience and has_education):
        return ClassificationResult(
            is_cv=False,
            doc_type="ADMIN_DOC",
            confidence=0.95,
            reasons=["Dokumen teridentifikasi sebagai berkas administrasi/identitas (KTP/KK/SKCK), bukan CV."],
            flags=["NOT_A_CV", "ADMINISTRATIVE_DOCUMENT"],
            extracted_contact=contact_data,
        )

    # Case B: Certificate / Diploma / Academic Transcripts Only (Piagam / Ijazah / Transkrip)
    is_cert_present = any(p.search(clean_text) for p in CERTIFICATE_PATTERNS)
    if is_cert_present and not has_experience and not has_skills:
        return ClassificationResult(
            is_cv=False,
            doc_type="CERTIFICATE_ONLY",
            confidence=0.95,
            reasons=[
                "Dokumen teridentifikasi sebagai berkas sertifikat / ijazah / transkrip nilai akademik tanpa ringkasan CV dan riwayat kerja."
            ],
            flags=["NOT_A_CV", "CERTIFICATE_OR_ACADEMIC_ONLY"],
            extracted_contact=contact_data,
        )

    # Case C: Cover Letter / Surat Lamaran Only
    if is_cover_letter and not has_experience and not has_skills and not has_education:
        return ClassificationResult(
            is_cv=False,
            doc_type="COVER_LETTER_ONLY",
            confidence=0.95,
            reasons=["Dokumen hanya berupa surat lamaran / cover letter pengantar tanpa ringkasan CV."],
            flags=["NOT_A_CV", "COVER_LETTER_ONLY"],
            extracted_contact=contact_data,
        )

    # If the document has images and very little text (< 30 words), it might be a 1-2 page scanned CV.
    # We allow 1-2 page scanned documents to pass to OCR.
    # But if it has many pages (> 3 pages) with virtually no text and lots of images, it is a pure image portfolio!
    if total_images > 0 and word_count < 30:
        if page_count > 3:
            return ClassificationResult(
                is_cv=False,
                doc_type="PURE_PORTFOLIO",
                confidence=0.90,
                reasons=[
                    "Dokumen terdiri dari banyak halaman gambar/portofolio visual tanpa teks profil atau riwayat pekerjaan."
                ],
                flags=["NOT_A_CV", "PURE_PORTFOLIO"],
                extracted_contact=contact_data,
            )
        return ClassificationResult(
            is_cv=True,
            doc_type="SCANNED_CV_PENDING_OCR",
            confidence=0.75,
            reasons=[],
            flags=["SCANNED_FILE_OR_IMAGE"],
            extracted_contact=contact_data,
        )

    # Case D: Pure Portfolio / Presentation Slides without resume sections
    # (Lots of words, but zero experience, zero education, zero contact)
    if not has_contact and not has_experience and not has_education:
        return ClassificationResult(
            is_cv=False,
            doc_type="PURE_PORTFOLIO",
            confidence=0.90,
            reasons=["Dokumen berupa portofolio visual / slide karya tanpa profil dan riwayat pekerjaan."],
            flags=["NOT_A_CV", "PURE_PORTFOLIO"],
            extracted_contact=contact_data,
        )

    # 5. Positive Consensus: Valid CV
    # A valid CV must have contact info AND at least one core pillar (Experience OR Education)
    cv_score = 0.5
    if has_contact:
        cv_score += 0.2
    if has_experience:
        cv_score += 0.2
    if has_education:
        cv_score += 0.1
    if has_skills:
        cv_score += 0.1

    return ClassificationResult(
        is_cv=True,
        doc_type="CV",
        confidence=min(0.99, cv_score),
        reasons=[],
        flags=[],
        extracted_contact=contact_data,
    )
