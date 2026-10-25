"""Unit tests for CV Extractor v2 components:
- CVClassifierGate (Pre-flight CV vs Non-CV filter)
- Smart Document Boundary Isolator (Multi-page CV without arbitrary page limits)
- Orthogonal Anchor Consensus Engine (Anti-Headline and Anti-Institution bias)
"""

from __future__ import annotations

from src.worker.anchor import (
    is_blacklisted_as_name,
    resolve_candidate_name_consensus,
)
from src.worker.boundary import isolate_document_boundaries
from src.worker.classifier import classify_document_is_cv


def test_cv_classifier_accepts_valid_standard_cv():
    sample_text = """
    Rifqi Setiawan
    Email: rifqi@example.com | Phone: 081234567890
    
    PENGALAMAN KERJA
    Backend Engineer - PT Teknologi Bangsa (2022 - 2024)
    - Membangun REST API dengan FastAPI dan PostgreSQL.
    
    PENDIDIKAN
    S1 Teknik Informatika - Institut Teknologi Bandung (2018 - 2022)
    
    KEAHLIAN
    Python, FastAPI, Docker, SQL
    """
    res = classify_document_is_cv(sample_text, page_count=1, total_images=0)
    assert res.is_cv is True
    assert res.doc_type == "CV"
    assert res.confidence >= 0.70
    assert res.extracted_contact["email"] == "rifqi@example.com"


def test_cv_classifier_accepts_multi_page_senior_cv_without_page_cutoff():
    # Long 6-page CV simulation with work experiences across all pages
    page_text = """
    John Doe, Senior Architect
    Email: john@example.com | Phone: 081987654321
    
    PENGALAMAN PROFESIONAL
    Head of Engineering - PT Solusi Digital (2020 - Present)
    - Leading 25 engineers across core services.
    
    RIWAYAT PEKERJAAN SEBELUMNYA
    Senior Developer - Startup ABC (2016 - 2020)
    - Designed microservices architecture.
    
    PENDIDIKAN
    S1 Ilmu Komputer - Universitas Indonesia
    """
    # 6 pages, all valid CV content
    res = classify_document_is_cv(page_text, page_count=6, total_images=0)
    assert res.is_cv is True
    assert res.doc_type == "CV"


def test_cv_classifier_rejects_certificate_only():
    cert_text = """
    SERTIFIKAT PENGHARGAAN
    Certificate of Completion
    
    Diberikan kepada:
    Budi Santoso
    
    Telah menyelesaikan kursus Dasar Pemrograman Python selama 40 jam pelatihan.
    Jakarta, 12 Januari 2024.
    """
    res = classify_document_is_cv(cert_text, page_count=1, total_images=1)
    assert res.is_cv is False
    assert res.doc_type == "CERTIFICATE_ONLY"
    assert "NOT_A_CV" in res.flags


def test_cv_classifier_rejects_administrative_document_ktp():
    ktp_text = """
    PROVINSI JAWA BARAT KOTA BANDUNG
    KARTU TANDA PENDUDUK
    NIK : 3273012345678901
    Nama : AHMAD FAUZI
    Tempat/Tgl Lahir : BANDUNG, 15-05-1995
    Jenis Kelamin : LAKI-LAKI
    Alamat : JL. MERDEKA NO. 10
    Agama : ISLAM
    Status Perkawinan : BELUM KAWIN
    Pekerjaan : KARYAWAN SWASTA
    Kewarganegaraan : WNI
    """
    res = classify_document_is_cv(ktp_text, page_count=1, total_images=1)
    assert res.is_cv is False
    assert res.doc_type == "ADMIN_DOC"
    assert "NOT_A_CV" in res.flags


def test_cv_classifier_rejects_pure_portfolio_without_profile():
    portfolio_text = """
    PROJECT SHOWCASE 2024
    Desain Interior Apartemen Minimalis Modern
    Rendering 3D SketchUp & V-Ray
    Denah Lantai 1 dan Lantai 2
    Skala 1:100
    """
    res = classify_document_is_cv(portfolio_text, page_count=15, total_images=20)
    assert res.is_cv is False
    assert res.doc_type == "PURE_PORTFOLIO"
    assert "NOT_A_CV" in res.flags


def test_smart_boundary_isolator_separates_attachments():
    pages = [
        {
            "text": "John Doe\nEmail: john@mail.com\nPengalaman Kerja:\nSoftware Engineer (2022 - 2024)\nPendidikan:\nS1 IT",
            "image_count": 0,
        },
        {"text": "Pengalaman Organisasi:\nKetua Himpunan Mahasiswa\nKeahlian:\nPython, SQL, Linux", "image_count": 0},
        {"text": "LAMPIRAN PORTOFOLIO PROYEK\nScreenshots aplikasi mobile dan arsitektur backend", "image_count": 2},
        {"text": "", "image_count": 1},
        {"text": "", "image_count": 1},
    ]
    res = isolate_document_boundaries(pages)
    assert res.total_pages == 5
    assert res.cv_core_pages == [1, 2]
    assert res.attachment_pages == [3, 4, 5]
    assert len(res.attachments) == 3


def test_anchor_engine_eliminates_headline_bias():
    assert is_blacklisted_as_name("Fullstack Developer") is True
    assert is_blacklisted_as_name("Backend Developer") is True
    assert is_blacklisted_as_name("Digital Marketing") is True
    assert is_blacklisted_as_name("Personal Background") is True
    assert is_blacklisted_as_name("Tentang Saya") is True
    assert is_blacklisted_as_name("Universitas Muhammadiyah Bandung") is True
    assert is_blacklisted_as_name("STMIK Dipanegara") is True
    assert is_blacklisted_as_name("Muhammad Akil") is False
    assert is_blacklisted_as_name("Yadi Apriyadi") is False


def test_anchor_consensus_prefers_filename_when_text_has_headline_bias():
    full_text = """
    FULLSTACK DEVELOPER
    Email: yadi@example.com
    
    Tentang Saya:
    Saya adalah pengembang web...
    """
    resolved = resolve_candidate_name_consensus(
        extracted_name="Fullstack Developer",
        full_text=full_text,
        filename="3554_Yadi Apriyadi_CV - YADI APRIYADI - 2025.pdf",
        email="yadi@example.com",
    )
    assert resolved == "Yadi Apriyadi"
