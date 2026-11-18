"""Rule-based CV prefill: regression tests for the common CV layouts found in the intake audit.

All people, companies and campuses are fictional. These tests pin the behaviour that recruiters rely on:
campus, major, degree, GPA and the title/organisation split must come out of the CV, and a date range given
only as years must not be turned into invented months.
"""

from __future__ import annotations

import pymupdf
import pytest

from src.worker.cv_text import parse_experiences
from src.worker.tig_prefill import education_entries, prefill_form

HEAD = ["## Budi Contoh", "budi.contoh@example.test | 0812 3456 7890", "Jakarta, DKI Jakarta, Indonesia"]


def pdf(lines, sidebar=None) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for text in lines:
        big = text.startswith("##")
        page.insert_text((190 if sidebar else 50, y), text.lstrip("# "), fontsize=15 if big else 10, fontname="helv")
        y += 20 if big else 14
    for offset, text in enumerate(sidebar or []):
        page.insert_text((30, 60 + 13 * offset), text, fontsize=9, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def edu(level, campus, major, gpa):
    return {"level": level, "campus": campus, "major": major, "gpa": gpa}


def job(form, index=0):
    item = form["experiences"][index]
    return item["title"], item["organization"], item["start"], item["end"]


def test_clean_ats_cv_keeps_title_and_organisation_in_order():
    form = prefill_form(pdf(HEAD + [
        "Pendidikan", "Universitas Contoh", "Jurusan: Statistika", "S1 | IPK: 3.62", "2019 - 2023",
        "Pengalaman Kerja", "Data Analyst", "PT Contoh Maju", "Jan 2023 - Des 2025", "- Membangun dashboard penjualan",
        "Keahlian", "SQL, Python, Tableau"]))["form"]
    assert form["education"] == [edu("S1", "Universitas Contoh", "Statistika", 3.62)]
    assert job(form) == ("Data Analyst", "PT Contoh Maju", "2023-01", "2025-12")


def test_single_line_education_with_pipes_is_split_into_fields():
    form = prefill_form(pdf(HEAD + [
        "Pendidikan", "Universitas Indonesia | S1 Teknik Informatika | IPK 3.75 | 2018 - 2022",
        "Pengalaman Kerja", "Software Engineer - PT Digital Contoh (Mar 2022 - Sekarang)", "- Mengembangkan API layanan pembayaran",
        "Keahlian", "Java, Spring, PostgreSQL"]))["form"]
    assert form["education"] == [edu("S1", "Universitas Indonesia", "Teknik Informatika", 3.75)]
    assert job(form) == ("Software Engineer", "PT Digital Contoh", "2022-03", "present")


def test_english_degree_phrase_gives_major_without_degree_words_and_campus_without_gpa_or_dates():
    form = prefill_form(pdf(HEAD + [
        "Education", "Bachelor of Science in Computer Science", "Telkom University, GPA 3.60/4.00 (2019-2023)",
        "Work Experience", "Backend Developer, Contoh Startup, 2023 - 2025", "- Built REST services",
        "Skills", "Python, Docker, Kubernetes"]))["form"]
    assert form["education"] == [edu("S1", "Telkom University", "Computer Science", 3.6)]
    assert job(form) == ("Backend Developer", "Contoh Startup", "2023", "2025")  # years stay years


def test_campus_abbreviation_is_taken_from_the_first_institution_like_segment():
    form = prefill_form(pdf(HEAD + [
        "Pendidikan", "UB Malang - S1 Akuntansi (IPK 3,50) 2017-2021",
        "Pengalaman Kerja", "Staf Akuntansi - CV Contoh Sejahtera, 2021 - 2024",
        "Keahlian", "Excel, Accurate, Pajak"]))["form"]
    assert form["education"] == [edu("S1", "UB Malang", "Akuntansi", 3.5)]
    assert job(form) == ("Staf Akuntansi", "CV Contoh Sejahtera", "2021", "2024")


def test_two_column_cv_keeps_sidebar_contacts_and_orders_title_before_company():
    form = prefill_form(pdf(
        ["## Budi Contoh", "Pendidikan", "Politeknik Contoh Negeri", "Jurusan: Teknik Elektro", "D3 | IPK 3.40", "2016 - 2019",
         "Pengalaman Kerja", "Teknisi Lapangan", "PT Contoh Energi", "2019 - 2022", "- Pemeliharaan panel listrik"],
        sidebar=["Kontak", "budi.contoh@example.test", "0812 3456 7890", "Bandung, Jawa Barat, Indonesia", "Keahlian", "AutoCAD", "PLC", "K3"]))["form"]
    assert form["email"] == "budi.contoh@example.test"
    assert form["preferences"]["domicile"] == "Bandung"
    assert form["education"] == [edu("D3", "Politeknik Contoh Negeri", "Teknik Elektro", 3.4)]
    assert job(form) == ("Teknisi Lapangan", "PT Contoh Energi", "2019", "2022")
    assert form["skills"] == ["AutoCAD", "PLC", "K3"]


def test_study_history_heading_and_institute_line_are_recognised():
    form = prefill_form(pdf(HEAD + [
        "Riwayat Studi", "Institut Teknologi Contoh - S1 Teknik Industri - IPK 3.55",
        "Riwayat Pekerjaan", "Analis Produksi di PT Contoh Pabrik (2022-2025)",
        "Kemampuan", "Lean, Six Sigma, SAP"]))["form"]
    assert form["education"] == [edu("S1", "Institut Teknologi Contoh", "Teknik Industri", 3.55)]
    assert job(form) == ("Analis Produksi", "PT Contoh Pabrik", "2022", "2025")


@pytest.mark.parametrize("lines, expected", [
    (["Data Analyst", "PT Contoh Maju", "Jan 2023 - Des 2025"], ("Data Analyst", "PT Contoh Maju")),
    (["PT Contoh Maju", "Data Analyst", "Jan 2023 - Des 2025"], ("Data Analyst", "PT Contoh Maju")),
    (["Perusahaan Contoh", "Developer Intern", "April 2025 - Present (3 bulan)"], ("Developer Intern", "Perusahaan Contoh")),
    (["Software Engineer - PT Digital Contoh (Mar 2022 - Sekarang)"], ("Software Engineer", "PT Digital Contoh")),
    (["Analis Produksi di PT Contoh Pabrik (2022-2025)"], ("Analis Produksi", "PT Contoh Pabrik")),
    (["Backend Developer at Contoh Startup | 2023 - 2025"], ("Backend Developer", "Contoh Startup")),
    (["Contoh Startup, Backend Developer, 2023 - 2025"], ("Backend Developer", "Contoh Startup")),
])
def test_title_and_organisation_are_assigned_by_content_not_only_by_line_order(lines, expected):
    item = parse_experiences("\n".join(lines))[0]
    assert (item["title"], item["organization"]) == expected


@pytest.mark.parametrize("line, expected", [
    ("UNPAD – S1 Hukum, IPK 3,45 (2016–2020)", edu("S1", "UNPAD", "Hukum", 3.45)),
    ("Universitas Gadjah Mada | Sarjana Teknik Sipil | IPK 3.30", edu("S1", "Universitas Gadjah Mada", "Teknik Sipil", 3.3)),
    ("Binus University - S2 Magister Manajemen - GPA 3.80/4.00", edu("S2", "Binus University", "Manajemen", 3.8)),
])
def test_one_line_education_variants(line, expected):
    assert education_entries([line]) == [expected]


def test_two_schools_and_two_jobs_stay_separate_and_ordered():
    form = prefill_form(pdf(HEAD + [
        "Pendidikan", "Universitas Contoh | S1 Sistem Informasi | IPK 3.58 | 2016 - 2020", "SMAN 1 Contoh | IPA | 2013 - 2016",
        "Pengalaman Kerja", "Senior Data Analyst - PT Alfa Data (Jan 2022 - Sekarang)", "- memimpin tim analis",
        "Junior Analyst | PT Beta Solusi | Jul 2020 - Des 2021", "- membuat laporan harian"]))["form"]
    assert [(e["level"], e["campus"]) for e in form["education"]] == [("S1", "Universitas Contoh"), ("SMA/SMK", "SMAN 1 Contoh")]
    assert [(j["title"], j["organization"]) for j in form["experiences"]] == [
        ("Senior Data Analyst", "PT Alfa Data"), ("Junior Analyst", "PT Beta Solusi")]
    assert form["experiences"][1]["start"] == "2020-07" and form["experiences"][1]["end"] == "2021-12"


@pytest.mark.parametrize("text", ["- - - -", "|||", "S1", "Bachelor of", "IPK", "2020 - ", "UB", "x " * 3000, " , , ,", "S1 -"])
def test_nasty_lines_never_raise_and_stay_bounded(text):
    for item in parse_experiences(text):
        assert len(item["title"]) < 5000
    for entry in education_entries([text]):
        assert set(entry) == {"level", "campus", "major", "gpa"}


def test_scan_and_empty_cv_still_leave_the_form_manual():
    with pymupdf.open() as doc:
        doc.new_page()
        assert prefill_form(doc.tobytes())["form"] == {}
