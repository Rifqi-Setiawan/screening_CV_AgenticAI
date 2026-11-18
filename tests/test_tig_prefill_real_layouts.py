"""Rule-based CV prefill against three real-world CV layouts found while testing the applicant flow end to end.

Every name, company and campus below is fictional; only the *layout* of each CV is reproduced:

* layout A: "Company | Title" line, then a separate "Onsite | Contract | <dates>" line, then a location line;
* layout B: title line, "Company l City" line (the pipe extracted as a lowercase L), a month-range line or a bare
  year for internships, a contact line in the middle of the text, and skills hidden under "INFORMASI TAMBAHAN";
* layout C: title line, then "Company - City, Country | | April, 2024 – April, 2025", zero-width spaces, a page
  header repeated on every page, skills under capitalised sub-labels with " | " separators, project blocks.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

import pymupdf
import pytest

from src.worker.cv_text import parse_experiences
from src.worker.tig_prefill import display_date, prefill_form


def cv_docx(lines) -> bytes:
    """Word export of the same text. Used for layout C because the PDF base fonts turn zero-width spaces and en dashes into dots."""
    body = "".join(f"<w:p><w:r><w:t>{escape(text.lstrip('# '))}</w:t></w:r></w:p>" for text in lines)
    xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return out.getvalue()


def cv_pdf(lines) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for text in lines:
        big = text.startswith("##")
        if y > 790:
            page, y = doc.new_page(), 60
        page.insert_text((50, y), text.lstrip("# "), fontsize=15 if big else 10, fontname="helv")
        y += 20 if big else 14
    data = doc.tobytes()
    doc.close()
    return data


def jobs(items):
    return [(i["title"], i["organization"], display_date(i["start"]), display_date(i["end"])) for i in items]


def form_jobs(form):
    return [(j["title"], j["organization"], j["start"], j["end"]) for j in form["experiences"]]


# ---------------------------------------------------------------- experience headers

LAYOUT_A = """Contoh Teknologi Nusantara | Web Engineer
Onsite | Contract | June 2024 - May 2025
South Jakarta, DKI Jakarta, Indonesia
Provided ongoing maintenance and support for a banking web application as a third-party Web
Engineer.
Maintained and resolved reported bugs or performance issues in a timely manner.
Contoh Studio | Full Stack Developer
Remote | Contract | July 2023 - January 2024
Bandung, West Java, Indonesia
Collaborate with cross-functional teams to understand the product vision and roadmap.
Successfully delivered two client projects"""

LAYOUT_B = """Membuat aplikasi dashboard iklan menggunakan Laravel
Technical Leader
PT Contoh Niaga Integrasi (Contoh Tech) l Bandung
Januari 2024 -  April 2025
Cibiru, Bandung 40615 • 0812 3456 7890 • dewi.contoh@example.test
Membuat aplikasi integrasi dashboard ads dengan Laravel
Membuat aplikasi download report dengan Laravel
Backend Engineer
PT. Contoh Distributor | Bandung
Maret 2020 -  Mei 2023
Support backend layanan asuransi
Mix Vue js dan Golang
Web Developer - Freelance
PT Contoh Guna | Bandung
Juli 2017 -  Oktober 2017
Membuat aplikasi GIS menggunakan PHP
Web Developer - PKL
PT. Contoh Persero| Bandung
2015
Membuat program entry data peserta pelatihan
Web Developer - PKL
BBPLK Contoh| Bandung
2011"""

LAYOUT_C = """Backend Developer
PT. Contoh Teknologi - Bandung, Indonesia | | April, 2024 – April, 2025
Membangun dan memelihara sistem integrasi media sosial untuk manajemen iklan
menggunakan Laravel dan PostgreSQL.
Mengembangkan RESTful API yang meningkatkan latensi sistem hingga 30%.
Web Developer
PT. Digital Contoh Media - Bandung, Indonesia | | Januari, 2023 – April, 2024
Mengembangkan dan memelihara aplikasi perhotelan untuk Smart TV.
Full Stack Developer
Freelance - Bandung, Indonesia | | April, 2021 – November, 2022
Membangun aplikasi kustom sesuai kebutuhan klien."""


def test_company_title_line_above_a_work_type_line_gives_title_company_and_dates():
    items = parse_experiences(LAYOUT_A)
    assert jobs(items) == [
        ("Web Engineer", "Contoh Teknologi Nusantara", "2024-06", "2025-05"),
        ("Full Stack Developer", "Contoh Studio", "2023-07", "2024-01"),
    ]


def test_work_type_and_location_lines_and_the_next_header_do_not_leak_into_the_description():
    first, second = parse_experiences(LAYOUT_A)
    assert first["bullets"][0].startswith("Provided ongoing maintenance")
    assert not any("Contoh Studio" in b or "Full Stack Developer" in b or "Jakarta" in b for b in first["bullets"])
    assert not any("Bandung" in b for b in second["bullets"])


def test_title_company_and_city_on_three_lines_with_lowercase_l_pipe_and_bare_year_internships():
    items = parse_experiences(LAYOUT_B)
    assert jobs(items) == [
        ("Technical Leader", "PT Contoh Niaga Integrasi (Contoh Tech)", "2024-01", "2025-04"),
        ("Backend Engineer", "PT. Contoh Distributor", "2020-03", "2023-05"),
        ("Web Developer - Freelance", "PT Contoh Guna", "2017-07", "2017-10"),
        ("Web Developer - PKL", "PT. Contoh Persero", "2015", "2015"),
        ("Web Developer - PKL", "BBPLK Contoh", "2011", "2011"),
    ]


def test_next_job_header_and_contact_lines_stay_out_of_the_previous_description():
    items = parse_experiences(LAYOUT_B)
    everything = [b for item in items for b in item["bullets"]]
    assert not any("@" in b or "0812" in b for b in everything)
    assert not any(b.startswith(("Backend Engineer", "Web Developer", "PT ", "PT.")) for b in everything)
    assert items[1]["bullets"] == ["Support backend layanan asuransi", "Mix Vue js dan Golang"]


def test_title_line_above_company_and_city_line_with_commas_in_month_year_dates():
    items = parse_experiences(LAYOUT_C)
    assert jobs(items) == [
        ("Backend Developer", "PT. Contoh Teknologi", "2024-04", "2025-04"),
        ("Web Developer", "PT. Digital Contoh Media", "2023-01", "2024-04"),
        ("Full Stack Developer", "Freelance", "2021-04", "2022-11"),
    ]
    assert not any("Web Developer" in b or "Full Stack" in b for b in items[0]["bullets"] + items[1]["bullets"])


# ---------------------------------------------------------------- whole-CV layouts

CV_A = [
    "## Sari Contoh",
    "Address: Cilacap, Central Java, ID | Email: sari.contoh@example.test | Linkedin: in/saricontoh | Github: saricontoh |",
    "Website: saricontoh.example.dev",
    "SUMMARY", "Web Developer with two years of experience, focusing primarily on Laravel development.",
    "SKILLS",
    "Technical Skills: Tailwind CSS, Bootstrap, JavaScript, Node.js, Responsive Design, PHP, Laravel, MySQL, Web",
    "app deployment and hosting management using cPanel, Skilled in utilizing AI tools like ChatGPT to find solutions",
    "through effective prompt engineering.",
    "Software & Tools: Visual Studio Code, Git, GitLab, Postman",
    "Operating System: Windows, Mac-OS, Linux (Ubuntu)",
    "Soft Skills: Self Learn, Good Attitude, Team Work",
    "Language: Javanese (Native), Indonesian (Fluent), English (Passive, TOEFL 487)",
    "EXPERIENCE", *LAYOUT_A.splitlines(),
    "PROJECTS",
    "Content Management System & Portfolio Web",
    "Developed a Portfolio Website and CMS using Laravel 10, Bootstrap, and SQL",
    "Database.",
    "Implemented a multi-role permission system with Spatie.",
    "Automated feature testing using PHPUnit to ensure stability.",
    "Guidance Counseling Knowledge System",
    "Designed a Guidance and Counseling Management System using Laravel 8.",
    "Successfully integrated a Case-Based Reasoning algorithm.",
    "EDUCATION",
    "Bachelor Degree of Informatics Engineering",
    "Computer University of Indonesia (UNIKOM)",
    "Bandung, West Java, Indonesia",
    "GPA 3.09/4.00",
    "Related Subject:",
    "Algorithm and Programming |Data Structure | Database",
    "COURSE & CERTIFICATIONS",
    "LSP Teknologi Digital: Junior Web", "Programmer (BNSP)", "2023",
    "BuildWithAngga: Fullstack Web Developer -", "Website Freelancer", "2022",
]


@pytest.fixture(scope="module")
def form_a():
    return prefill_form(cv_pdf(CV_A))["form"]


def test_layout_a_contact_links_and_domicile(form_a):
    assert form_a["preferences"]["domicile"] == "Cilacap, Central Java, ID"
    assert form_a["links"] == ["https://linkedin.com/in/saricontoh", "https://github.com/saricontoh", "https://saricontoh.example.dev"]


def test_layout_a_education_experience_and_certifications(form_a):
    assert form_a["education"] == [
        {"level": "S1", "campus": "Computer University of Indonesia (UNIKOM)", "major": "Informatics Engineering", "gpa": 3.09}
    ]
    assert form_jobs(form_a) == [
        ("Web Engineer", "Contoh Teknologi Nusantara", "2024-06", "2025-05"),
        ("Full Stack Developer", "Contoh Studio", "2023-07", "2024-01"),
    ]
    assert form_a["certifications"] == [
        "LSP Teknologi Digital: Junior Web Programmer (BNSP) 2023",
        "BuildWithAngga: Fullstack Web Developer - Website Freelancer 2022",
    ]


def test_layout_a_skills_come_from_labelled_lines_without_labels_sentences_or_soft_skills(form_a):
    skills = form_a["skills"]
    for expected in ["Tailwind CSS", "Node.js", "Laravel", "MySQL", "Visual Studio Code", "Git", "Postman", "Windows", "Linux (Ubuntu)"]:
        assert expected in skills
    assert not any(":" in s or len(s.split()) > 6 or s.endswith(".") for s in skills)
    assert "Self Learn" not in skills and "Good Attitude" not in skills


def test_layout_a_languages_keep_a_comma_inside_parentheses(form_a):
    assert form_a["languages"] == ["Javanese (Native)", "Indonesian (Fluent)", "English (Passive, TOEFL 487)"]


def test_layout_a_projects_are_grouped_by_title_not_one_per_line(form_a):
    assert len(form_a["projects"]) == 2
    assert form_a["projects"][0].startswith("Content Management System & Portfolio Web")
    assert "PHPUnit" in form_a["projects"][0] and "Database." in form_a["projects"][0]
    assert form_a["projects"][1].startswith("Guidance Counseling Knowledge System")
    assert "Case-Based Reasoning" in form_a["projects"][1]


PAGE_HEADER_C = ["Rina Contoh", "Backend Developer | Web Developer", "0812 3456 7890 | rina.contoh@example.test | linkedin.com/in/rinacontoh | github.com/rinacontoh |Bandung,", "Indonesia"]

CV_C = [
    "## " + PAGE_HEADER_C[0], *PAGE_HEADER_C[1:],
    "RINGKASAN", "Backend Developer dengan pengalaman lebih dari 3 tahun dalam membangun aplikasi web dan API.",
    "KEAHLIAN​", "BAHASA PEMROGRAMAN  ​", "​", "PHP | Go | TypeScript |  JavaScript | Java",
    "FRAMEWORKS & LIBRARIES:​", "​", "React | Laravel | CodeIgniter | Node.js | jQuery",
    "TOOLS & TECHNOLOGIES:​", "​", "Git | Docker | Webpack |Swagger | Postman |CI/CD",
    "DATABASES:​", "​", "​", "MySQL | MongoDB | PostgreSQL | Redis",
    "OPERATING SYSTEMS:​​", "​", "Windows | macOS | Linux Distributions",
    "PENGALAMAN",
    "Backend Developer", "PT. Contoh Teknologi - Bandung, Indonesia | | April, 2024 – April, 2025",
    "●​", "Membangun dan memelihara sistem integrasi media sosial untuk manajemen iklan",
    "menggunakan Laravel dan PostgreSQL.",
    "●​", "Mengembangkan RESTful API yang meningkatkan latensi sistem hingga 30%.",
    "Web Developer", "PT. Digital Contoh Media - Bandung, Indonesia | | Januari, 2023 – April, 2024",
    "●​", "Mengembangkan dan memelihara aplikasi perhotelan untuk Smart TV.",
    "●​", "Menerapkan prinsip OOP dan arsitektur MVC untuk meningkatkan keterbacaan dan",
    "pemeliharaan kode.",
    *PAGE_HEADER_C,
    "Backend Developer", "PT. Contoh Lama - Bandung, Indonesia | | April, 2021 – November, 2022",
    "●​", "Merancang dan mengembangkan API untuk kebutuhan aplikasi mobile dan web.",
    "Full Stack Developer", "Freelance - Bandung, Indonesia | | April, 2021 – November, 2022",
    "●​", "Membangun aplikasi kustom sesuai kebutuhan klien.",
    "PENDIDIKAN",
    "D4 - Teknik Informatika", "Politeknik Contoh Bandung,Bandung, Indonesia | 19 (September,2019)", "IPK: 3.70",
    "PROYEK",
    "LANDING PAGE WEBSITE RESTORAN CONTOH",
    "Restoran Contoh | 01 (Februari, 2020)",
    "Deskripsi: Membangun landing page website untuk restoran contoh.",
    "Link Project: View the Project",
    *PAGE_HEADER_C,
    "SYSTEM POINT OF SALES RESTORAN CONTOH",
    "Restoran Contoh | 20 (September, 2024)",
    "Deskripsi: Merancang, membangun fitur baru, dan memaintenance system untuk kebutuhan",
    "internal restoran contoh.",
    "Link to the project: View the Project",
]


@pytest.fixture(scope="module")
def form_c():
    return prefill_form(cv_docx(CV_C))["form"]


def test_layout_c_jobs_ignore_zero_width_bullets_and_the_page_header_repeated_between_pages(form_c):
    assert form_jobs(form_c) == [
        ("Backend Developer", "PT. Contoh Teknologi", "2024-04", "2025-04"),
        ("Web Developer", "PT. Digital Contoh Media", "2023-01", "2024-04"),
        ("Backend Developer", "PT. Contoh Lama", "2021-04", "2022-11"),
        ("Full Stack Developer", "Freelance", "2021-04", "2022-11"),
    ]
    for item in form_c["experiences"]:
        assert "Rina Contoh" not in item["description"] and "rina.contoh" not in item["description"]
        assert "|" not in item["description"]


def test_layout_c_education_drops_the_trailing_city_and_country_from_the_campus(form_c):
    assert form_c["education"] == [{"level": "D4", "campus": "Politeknik Contoh Bandung", "major": "Teknik Informatika", "gpa": 3.7}]


def test_layout_c_skills_split_on_pipes_and_skip_group_labels(form_c):
    skills = form_c["skills"]
    for expected in ["PHP", "Go", "TypeScript", "JavaScript", "React", "Laravel", "Node.js", "Docker", "CI/CD", "MySQL", "Redis", "Windows", "Linux Distributions"]:
        assert expected in skills
    assert not any(s.upper() == s and len(s.split()) > 1 for s in skills)
    assert not any(":" in s or "|" in s or "​" in s for s in skills)
    assert form_c["languages"] == []


def test_layout_c_domicile_and_links_come_from_the_header_even_when_the_country_wraps(form_c):
    assert form_c["preferences"]["domicile"] == "Bandung, Indonesia"
    assert form_c["links"] == ["https://linkedin.com/in/rinacontoh", "https://github.com/rinacontoh"]


def test_layout_c_projects_are_two_blocks_and_the_repeated_page_header_is_not_one_of_them(form_c):
    assert len(form_c["projects"]) == 2
    assert form_c["projects"][0].startswith("LANDING PAGE WEBSITE RESTORAN CONTOH")
    assert form_c["projects"][1].startswith("SYSTEM POINT OF SALES RESTORAN CONTOH")
    assert not any("View the Project" in p or "Rina Contoh" in p for p in form_c["projects"])


CV_B = [
    "## Dewi Contoh",
    "DESKRIPSI", "Seorang Backend Developer yang termotivasi dengan pengalaman membangun REST API.",
    "PENGALAMAN KERJA", *LAYOUT_B.splitlines(),
    "PENDIDIKAN",
    "S1 Teknik Informatika", "UIN Contoh Bandung", "2012 - 2016",
    "SMK Contoh 2 Bandung", "Rekayasa Perangkat Lunak", "2008 - 2011",
    "INFORMASI TAMBAHAN",
    "Kemampuan Non-Teknis: Komunikasi yang efektif, Kerja sama tim, Manajemen waktu,",
    "Penyelesaian masalah, Berpikir kritis",
    "Kemampuan Teknis : Pemrograman Laravel,PHP,CI, GO, Pengembangan REST API, Desain",
    "dan manajemen basis data (MySQL, PostgreSQL,SQLServer), Version Control (Git),",
    "Pengujian API (Postman), Dokumentasi teknis",
    "Penguasaan Alat atau Software : Visual Studio Code, GitHub / GitLab, Postman,",
    "MySQL,Trello / Jira (untuk manajemen tugas)",
]


@pytest.fixture(scope="module")
def form_b():
    return prefill_form(cv_pdf(CV_B))["form"]


def test_layout_b_school_takes_the_line_below_as_major(form_b):
    assert form_b["education"] == [
        {"level": "S1", "campus": "UIN Contoh Bandung", "major": "Teknik Informatika", "gpa": None},
        {"level": "SMA/SMK", "campus": "SMK Contoh 2 Bandung", "major": "Rekayasa Perangkat Lunak", "gpa": None},
    ]


def test_layout_b_skills_come_from_the_technical_lines_under_additional_information(form_b):
    skills = form_b["skills"]
    for expected in ["PHP", "CI", "GO", "MySQL", "PostgreSQL", "SQLServer", "Postman", "Visual Studio Code", "Pengembangan REST API"]:
        assert expected in skills
    assert not any("Komunikasi" in s or "Kerja sama" in s or "SMK" in s for s in skills)
    assert not any(":" in s for s in skills)


def test_layout_b_jobs_survive_the_whole_pdf_round_trip(form_b):
    assert [j[:2] for j in form_jobs(form_b)] == [
        ("Technical Leader", "PT Contoh Niaga Integrasi (Contoh Tech)"),
        ("Backend Engineer", "PT. Contoh Distributor"),
        ("Web Developer - Freelance", "PT Contoh Guna"),
        ("Web Developer - PKL", "PT. Contoh Persero"),
        ("Web Developer - PKL", "BBPLK Contoh"),
    ]


# ---------------------------------------------------------------- date line first (the PDF reading order of layout B)

LAYOUT_D = """Seorang Backend Developer yang termotivasi.
Januari 2024 -  April 2025
Technical Leader
PT Contoh Niaga Integrasi (Contoh Tech) l Bandung
Membuat aplikasi social media integrasi dashboard untuk pengelolaan iklan dari meta dan
tiktok menggunakan Laravel
Integrasi data ads dari meta dan tiktok menggunakan Laravel
Juli 2023 -  Desember 2023
Backend Engineer
PT Contoh Niaga Integrasi (Contoh Tech) l Bandung
Membuat Aplikasi Integrasi dashboard ads meta dengan Laravel
Membuat aplikasi download report dengan Laravel
Maret 2020 -  Mei 2023
Backend Engineer
PT. Contoh Distributor | Bandung
Support backend layanan asuransi
2015
Web Developer - PKL
PT. Contoh Persero| Bandung
Membuat program entry data peserta pelatihan"""


def test_dates_listed_before_the_title_and_company_still_belong_to_the_lines_below_them():
    items = parse_experiences(LAYOUT_D)
    assert jobs(items) == [
        ("Technical Leader", "PT Contoh Niaga Integrasi (Contoh Tech)", "2024-01", "2025-04"),
        ("Backend Engineer", "PT Contoh Niaga Integrasi (Contoh Tech)", "2023-07", "2023-12"),
        ("Backend Engineer", "PT. Contoh Distributor", "2020-03", "2023-05"),
        ("Web Developer - PKL", "PT. Contoh Persero", "2015", "2015"),
    ]


def test_dates_first_layout_keeps_headers_out_of_descriptions_and_bullets_with_their_job():
    items = parse_experiences(LAYOUT_D)
    assert items[0]["bullets"][0].startswith("Membuat aplikasi social media integrasi")
    assert items[0]["bullets"][-1] == "Integrasi data ads dari meta dan tiktok menggunakan Laravel"
    assert items[2]["bullets"] == ["Support backend layanan asuransi"]
    assert not any(b.startswith(("Backend Engineer", "PT ", "PT.", "Web Developer")) for item in items for b in item["bullets"])


def test_certification_years_that_the_pdf_puts_before_each_entry_are_attached_to_that_entry():
    form = prefill_form(cv_docx([
        "## Sari Contoh", "sari.contoh@example.test", "COURSE & CERTIFICATIONS",
        "2023", "LSP Teknologi Digital: Junior Web", "Programmer (BNSP)",
        "2022", "BuildWithAngga: Fullstack Web Developer -", "Website Freelancer",
        "2022", "BuildWithAngga: Fullstack Web Developer - E-", "Commerce",
    ]))["form"]
    assert form["certifications"] == [
        "LSP Teknologi Digital: Junior Web Programmer (BNSP) 2023",
        "BuildWithAngga: Fullstack Web Developer - Website Freelancer 2022",
        "BuildWithAngga: Fullstack Web Developer - E-Commerce 2022",
    ]


def test_private_use_bullet_glyphs_do_not_split_projects_or_become_lines():
    form = prefill_form(cv_docx([
        "## Sari Contoh", "sari.contoh@example.test", "PROJECTS",
        "Content Management System", "\uf0b7", "Developed a portfolio website using Laravel 10.", "\uf0b7",
        "Automated feature testing using PHPUnit.", "Guidance Counseling System", "\uf0b7", "Designed the system using Laravel 8.",
    ]))["form"]
    assert len(form["projects"]) == 2
    assert not any("\uf0b7" in p or p.startswith("\n") or "\n\n" in p for p in form["projects"])


def test_domicile_is_taken_from_the_contact_line_without_phone_email_or_postal_code():
    form = prefill_form(cv_docx([
        "## Dewi Contoh", "Cibiru, Bandung 40615 • 0812 3456 7890 • dewi.contoh@example.test",
        "DESKRIPSI", "Backend Developer.",
    ]))["form"]
    assert form["preferences"]["domicile"] == "Cibiru, Bandung"


def test_every_project_is_one_line_so_editing_the_one_entry_per_line_field_cannot_split_it(form_a, form_c):
    for form in (form_a, form_c):
        assert form["projects"] and all("\n" not in p for p in form["projects"])
    assert form_c["projects"][0].startswith("LANDING PAGE WEBSITE RESTORAN CONTOH — ")
    assert "Membangun landing page website untuk restoran contoh." in form_c["projects"][0]
