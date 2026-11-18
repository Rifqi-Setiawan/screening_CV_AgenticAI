"""Scoring prompt rules found while scoring three real CVs end to end."""

from src.domain import tig


def prompt_text() -> str:
    return " ".join(tig.SYSTEM_PROMPT.lower().split())


def test_a_missing_graduation_status_is_not_counted_as_an_applicant_gap():
    # The form has no graduation field, so every applicant used to get the same unfixable "no graduation statement" gap.
    text = prompt_text()
    assert "formulir tidak memiliki isian status kelulusan" in text
    assert "jangan menjadikan ketiadaannya kekurangan" in text
    assert "jangan mengurangi skor" in text


def test_the_rule_that_forbids_claiming_graduation_without_evidence_stays():
    assert "hanya jika formulir menyatakan itu secara eksplisit" in prompt_text()


def test_prompt_version_changes_with_the_rule_so_hr_can_tell_which_rules_scored_an_application():
    assert tig.PROMPT_VERSION != "tig-2026-11-18"
