"""Automated tests ensuring strict identity redaction and PII protection."""

from __future__ import annotations

import json
from pathlib import Path

from src.worker.adapter import extract_candidate_profile
from src.worker.redaction import extract_identity_and_redact


def test_identity_redaction_counterfactual_e5():
    edge_dir = Path("docs/spec/golden_dataset/cvs/edge")
    e5a_path = edge_dir / "E5a_counterfactual_A.pdf"
    e5b_path = edge_dir / "E5b_counterfactual_B.pdf"

    assert e5a_path.exists() and e5b_path.exists()

    prof_a = extract_candidate_profile(e5a_path.read_bytes(), e5a_path.name)
    prof_b = extract_candidate_profile(e5b_path.read_bytes(), e5b_path.name)

    id_a, match_a, chunks_a = extract_identity_and_redact(prof_a)
    id_b, match_b, chunks_b = extract_identity_and_redact(prof_b)

    # 1. Identity must be extracted in identity record
    assert id_a["full_name"] is not None
    assert id_a["email"] == "nadia.cf@example.com"
    assert id_a["other_personal"].get("gender") == "Perempuan"
    assert id_a["other_personal"].get("religion") == "Islam"

    assert id_b["full_name"] is not None
    assert id_b["email"] == "yohanes.cf@example.com"
    assert id_b["other_personal"].get("gender") == "Laki-laki"
    assert id_b["other_personal"].get("religion") == "Kristen"

    # 2. Matching profile must NOT contain any PII
    match_a_str = json.dumps(match_a, ensure_ascii=False)
    match_b_str = json.dumps(match_b, ensure_ascii=False)

    forbidden_pii = [
        "NADIA",
        "PUTRI",
        "LESTARI",
        "nadia.cf@example.com",
        "0812-0000-1401",
        "Perempuan",
        "Islam",
        "12 Mei 1999",
        "Menikah",
        "YOHANES",
        "MARPAUNG",
        "yohanes.cf@example.com",
        "0812-0000-1402",
        "Laki-laki",
        "Kristen",
        "3 Januari 1988",
        "Belum menikah",
    ]

    for pii in forbidden_pii:
        assert pii.lower() not in match_a_str.lower(), f"PII '{pii}' leaked into matching_profile A!"
        assert pii.lower() not in match_b_str.lower(), f"PII '{pii}' leaked into matching_profile B!"

    # 3. Matching profile experiences and skills between E5a and E5b must be 100% IDENTICAL
    assert match_a["skills"] == match_b["skills"]
    assert len(match_a["experiences"]) == len(match_b["experiences"])
    for ea, eb in zip(match_a["experiences"], match_b["experiences"]):
        assert ea["title"] == eb["title"]
        assert ea["start"] == eb["start"]
        assert ea["end"] == eb["end"]
        assert len(ea["bullets"]) == len(eb["bullets"])

    # 4. Profile chunks must NOT contain any PII
    for c in chunks_a + chunks_b:
        text = c["text_redacted"]
        for pii in forbidden_pii:
            assert pii.lower() not in text.lower(), f"PII '{pii}' leaked into profile chunk: {text}"
