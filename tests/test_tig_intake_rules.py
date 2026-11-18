"""Required fields for a professional application, enforced on submit only.

The stored form (Application) stays lenient so every application already in the database still loads; the
submit body (ApplicationSubmission) carries the rules plus the consent and fresh-graduate declarations.
All data here is fictional.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from src.domain.tig import Application, ApplicationSubmission, TigConfig, assessment_payload

VALID = {
    "full_name": "Budi Contoh",
    "email": "budi.contoh@example.test",
    "phone": "0812 3456 7890",
    "education": [{"level": "S1", "campus": "Universitas Contoh", "major": "Statistika", "gpa": 3.5}],
    "experiences": [{"title": "Data Analyst", "organization": "PT Contoh Maju", "start": "2023-01", "end": "2025-12", "description": ""}],
    "skills": ["SQL"],
    "preferences": {"domicile": "Jakarta", "expected_salary": 9_000_000, "work_modes": [], "open_to_placement": None},
    "consent": True,
}


def payload(**changes):
    data = copy.deepcopy(VALID)
    for key, value in changes.items():
        data[key] = value
    return data


def messages(**changes) -> str:
    with pytest.raises(ValidationError) as caught:
        ApplicationSubmission.model_validate(payload(**changes))
    return " ".join(error["msg"] for error in caught.value.errors())


def test_a_complete_submission_is_valid_and_converts_to_the_stored_form():
    submission = ApplicationSubmission.model_validate(VALID)
    stored = Application.model_validate(submission.model_dump(exclude={"consent", "fresh_graduate"}))
    assert stored.full_name == "Budi Contoh" and stored.consent_at == ""


@pytest.mark.parametrize("changes, expected", [
    ({"phone": ""}, "Nomor telepon"),
    ({"preferences": {"domicile": "  ", "expected_salary": 9_000_000}}, "Domisili"),
    ({"education": []}, "Pendidikan terakhir"),
    ({"skills": []}, "keahlian"),
    ({"experiences": []}, "pengalaman"),
    ({"preferences": {"domicile": "Jakarta", "expected_salary": None}}, "Ekspektasi gaji"),
    ({"preferences": {"domicile": "Jakarta", "expected_salary": 0}}, "Ekspektasi gaji"),
    ({"consent": False}, "persetujuan"),
])
def test_each_required_field_is_reported_in_indonesian(changes, expected):
    assert expected.lower() in messages(**changes).lower()


def test_every_problem_is_reported_together_not_one_at_a_time():
    text = messages(phone="", skills=[], consent=False, education=[])
    for part in ("Nomor telepon", "keahlian", "persetujuan", "Pendidikan terakhir"):
        assert part.lower() in text.lower()


@pytest.mark.parametrize("row, expected", [
    ({"level": None, "campus": "Universitas Contoh", "major": "Statistika", "gpa": 3.5}, "jenjang"),
    ({"level": "S1", "campus": "", "major": "Statistika", "gpa": 3.5}, "sekolah atau kampus"),
    ({"level": "S1", "campus": "Universitas Contoh", "major": " ", "gpa": 3.5}, "jurusan"),
    ({"level": "S1", "campus": "Universitas Contoh", "major": "Statistika", "gpa": None}, "IPK"),
    ({"level": "D3", "campus": "Politeknik Contoh", "major": "Teknik", "gpa": None}, "IPK"),
])
def test_every_education_row_needs_level_campus_major_and_gpa_for_degrees(row, expected):
    assert expected.lower() in messages(education=[row]).lower()


def test_high_school_does_not_need_a_gpa():
    ApplicationSubmission.model_validate(payload(education=[{"level": "SMA/SMK", "campus": "SMAN 1 Contoh", "major": "IPA", "gpa": None}]))


def test_no_experience_is_allowed_only_with_the_fresh_graduate_declaration():
    assert "pengalaman" in messages(experiences=[]).lower()
    ApplicationSubmission.model_validate(payload(experiences=[], fresh_graduate=True))


@pytest.mark.parametrize("row, expected", [
    ({"title": "", "organization": "PT Contoh", "start": "2023", "end": "", "description": ""}, "posisi"),
    ({"title": "Analis", "organization": "", "start": "2023", "end": "", "description": ""}, "organisasi"),
    ({"title": "Analis", "organization": "PT Contoh", "start": "", "end": "", "description": ""}, "mulai"),
])
def test_a_listed_experience_needs_title_organisation_and_start(row, expected):
    assert expected in messages(experiences=[row]).lower()


@pytest.mark.parametrize("link", ["javascript:alert(1)", "ftp://example.test/cv", "linkedin.com/in/budi", "https://a b.example.test", "data:text/html,x"])
def test_only_plain_http_links_are_accepted(link):
    with pytest.raises(ValidationError):
        ApplicationSubmission.model_validate(payload(links=[link]))


def test_good_links_and_availability_are_accepted_with_limits():
    ok = ApplicationSubmission.model_validate(payload(links=["https://www.linkedin.com/in/budi-contoh", "http://portfolio.example.test/budi"], available_from="Segera"))
    assert len(ok.links) == 2
    with pytest.raises(ValidationError):
        ApplicationSubmission.model_validate(payload(links=["https://example.test/%d" % i for i in range(6)]))


def test_consent_and_fresh_graduate_are_not_part_of_the_stored_form():
    with pytest.raises(ValidationError):
        Application.model_validate({**{k: v for k, v in VALID.items() if k != "consent"}, "consent": True})


def test_applications_stored_before_this_change_still_load_with_empty_new_fields():
    old = Application.model_validate({"full_name": "Lama", "email": "lama@example.test"})
    assert (old.links, old.available_from, old.consent_at) == ([], "", "")


def test_links_availability_and_consent_time_never_reach_the_ai_prompt():
    stored = Application.model_validate({
        **{k: v for k, v in VALID.items() if k != "consent"},
        "links": ["https://www.linkedin.com/in/budi-contoh"], "available_from": "Segera", "consent_at": "2026-11-18T15:00:00+00:00",
    })
    text = str(assessment_payload(stored, "Analis", TigConfig()))
    for private in ("linkedin", "Segera", "2026-11-18T15", "budi.contoh@example.test", "0812 3456 7890"):
        assert private not in text
