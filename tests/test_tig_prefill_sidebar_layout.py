"""A two-column CV whose left sidebar holds Summary, Technical Skills and Languages and whose right column holds the jobs.

Found with a fourth real CV. Everything below is fictional; only the layout is reproduced: titles carry their dates in
parentheses, the company and city come on the next line, a degree names its major after "in", a wrapped degree line, a
labelled phone number with a bracketed country code, and sidebar list items wrapped in the middle of a parenthesis.
"""

from __future__ import annotations

import pytest

from src.worker.cv_text import parse_experiences
from src.worker.tig_prefill import display_date, prefill_form
from tests.test_tig_prefill_real_layouts import cv_docx
from tests.test_tig_prefill_rules import pdf

SIDEBAR = [
    "Summary", "Professional web developer", "with 9+ years of experience.",
    "Technical Skills", "- PHP, Laravel", "- RESTful APIs", "- Authentication &", "Authorization (JWT, OAuth)",
    "- MySQL, MariaDB,", "MongoDB", "- Version Control (Git,", "GitHub, GitLab)", "- Responsive Web Design", "- Performance Optimization", "& Debugging",
    "Languages", "- Indonesian Language - First", "Language", "- English - B2 (Upper", "Intermediate)",
]

BODY = [
    "## Sari Contoh", "phone: +62 812 0000 1234", "email: sari.contoh@example.test",
    "Work Experience",
    "Senior Web Developer (Sep 2017 - Current)", "Contoh Niaga CV - Bandung, Jawa Barat",
    "- Built responsive web applications using React.js and Laravel.", "- Led the development of dropshipping platforms.",
    "Web Developer (Oct 2016 - Aug 2017)", "Contoh.id - Jakarta Utara, DKI Jakarta",
    "- Designed and maintained dynamic web applications.",
    "IT Support (Sep 2014 - Aug 2015)", "Contoh Tiket PT - Jakarta Utara, DKI Jakarta",
    "- Maintained a hotel booking website.",
    "Education", "Bachelor's Degree in Information System", "Universitas Contoh | Jakarta Barat, DKI Jakarta", "Sep 2019",
]


@pytest.fixture(scope="module")
def form():
    return prefill_form(pdf(BODY, sidebar=SIDEBAR))["form"]


def test_sidebar_sections_are_split_from_the_jobs_even_when_summary_is_in_the_sidebar(form):
    assert [(j["title"], j["organization"], j["start"], j["end"]) for j in form["experiences"]] == [
        ("Senior Web Developer", "Contoh Niaga CV", "2017-09", "present"),
        ("Web Developer", "Contoh.id", "2016-10", "2017-08"),
        ("IT Support", "Contoh Tiket PT", "2014-09", "2015-08"),
    ]


def test_job_bullets_do_not_leak_into_skills_or_languages(form):
    assert not any("Built responsive" in s or "Led the development" in s for s in form["skills"] + form["languages"])
    assert form["experiences"][0]["description"].count("\n") >= 1


def test_sidebar_skills_are_split_and_wrapped_items_are_rejoined(form):
    for expected in ["PHP", "Laravel", "RESTful APIs", "Authentication & Authorization", "JWT", "OAuth", "MySQL", "MariaDB", "MongoDB", "Git", "GitHub", "Responsive Web Design", "Performance Optimization & Debugging"]:
        assert expected in form["skills"]


def test_sidebar_languages_rejoin_a_wrapped_parenthesis_and_a_hanging_word(form):
    assert form["languages"] == ["Indonesian Language - First Language", "English - B2 (Upper Intermediate)"]


def test_title_with_parenthesised_dates_takes_its_company_from_the_next_line():
    items = parse_experiences("\n".join([
        "Web Developer (Oct 2016 - Aug 2017)", "Contoh.id - Jakarta Utara, DKI Jakarta", "Designed web applications.",
        "IT Support (Sep 2014 - Aug 2015)", "Ticket Contoh PT - Jakarta Utara, DKI Jakarta", "Maintained a booking website.",
    ]))
    assert [(i["title"], i["organization"], display_date(i["start"]), display_date(i["end"])) for i in items] == [
        ("Web Developer", "Contoh.id", "2016-10", "2017-08"),
        ("IT Support", "Ticket Contoh PT", "2014-09", "2015-08"),
    ]
    assert items[0]["bullets"] == ["Designed web applications."]


def test_a_bullet_that_looks_like_a_title_does_not_become_the_company():
    items = parse_experiences("\n".join(["Web Developer (2019 - 2021)", "Built the API for developers.", "Wrote tests."]))
    assert items[0]["organization"] == ""
    assert items[0]["bullets"] == ["Built the API for developers.", "Wrote tests."]


def test_degree_with_in_major_associate_degree_and_wrapped_major():
    form = prefill_form(cv_docx([
        "## Sari Contoh", "Education",
        "Bachelor’s Degree in Information System", "Universitas Contoh | Jakarta Barat, DKI Jakarta", "Sep 2019",
        "Associate’s Degree in Computer and Informatics", "Engineering", "Politeknik Negeri Contoh | Bandung Barat, Jawa Barat", "Sep 2014",
    ]))["form"]
    assert form["education"] == [
        {"level": "S1", "campus": "Universitas Contoh", "major": "Information System", "gpa": None},
        {"level": "D3", "campus": "Politeknik Negeri Contoh", "major": "Computer and Informatics Engineering", "gpa": None},
    ]


@pytest.mark.parametrize("line", ["phone: +(62) 812 5550 0123", "Phone : +62 812-5550-0123", "Telepon: 0812 5550 0123", "WhatsApp: +62 812 5550 0123"])
def test_a_labelled_phone_number_is_read_whatever_its_punctuation(line):
    form = prefill_form(cv_docx(["## Sari Contoh", line, "email: sari.contoh@example.test", "Summary", "Developer."]))["form"]
    digits = "".join(c for c in form["phone"] if c.isdigit())
    assert digits.endswith("81255500123") and len(form["phone"]) <= 32


def lines(rows):
    from src.worker.visibility import PdfLine

    return [PdfLine(x, y, text) for x, y, text in rows]


def test_columns_are_split_when_the_summary_heading_sits_in_the_left_sidebar():
    # Reading order of the real file: blocks sorted by top edge, so the two columns interleave.
    page = lines([
        (20, 130, "Summary"), (258, 135, "Work Experience"),
        (258, 180, "Senior Web Developer (Sep 2017 - Current)"), (18, 160, "Professional web developer"),
        (20, 400, "Technical Skills"), (258, 420, "Web Developer (Oct 2016 - Aug 2017)"),
        (40, 440, "PHP, Laravel"), (20, 740, "Languages"), (258, 760, "Education"),
    ])
    from src.worker.tig_prefill import split_pdf_columns

    main, side = split_pdf_columns(page, 612)
    assert [l.text for l in main] == ["Work Experience", "Senior Web Developer (Sep 2017 - Current)", "Web Developer (Oct 2016 - Aug 2017)", "Education"]
    assert [l.text for l in side] == ["Summary", "Professional web developer", "Technical Skills", "PHP, Laravel", "Languages"]


def test_a_single_column_cv_with_all_headings_at_the_same_x_is_never_split():
    from src.worker.tig_prefill import split_pdf_columns

    page = lines([(50, 60, "Summary"), (50, 100, "Skills"), (50, 140, "Work Experience"), (50, 180, "Education")])
    assert split_pdf_columns(page, 612) == (page, [])


def test_a_sidebar_item_that_continues_on_page_two_stays_in_its_sidebar_section():
    import pymupdf

    doc = pymupdf.open()
    first = doc.new_page()
    for x, y, text in [
        (30, 60, "Languages"), (30, 76, "- Indonesian - First Language"),
        (190, 60, "Work Experience"), (190, 80, "Web Developer (Oct 2016 - Aug 2017)"), (190, 94, "Contoh.id - Jakarta Utara, DKI Jakarta"),
        (190, 108, "- Designed web applications."),
    ]:
        first.insert_text((x, y), text, fontsize=10, fontname="helv")
    second = doc.new_page()
    for x, y, text in [
        (30, 60, "- English - B2 (Upper"), (30, 74, "Intermediate)"),
        (190, 60, "Education"), (190, 80, "Bachelor's Degree in Information System"), (190, 94, "Universitas Contoh | Jakarta Barat"),
    ]:
        second.insert_text((x, y), text, fontsize=10, fontname="helv")
    data = doc.tobytes()
    doc.close()
    form = prefill_form(data)["form"]
    assert form["languages"] == ["Indonesian - First Language", "English - B2 (Upper Intermediate)"]
    assert form["education"][0]["campus"] == "Universitas Contoh"
