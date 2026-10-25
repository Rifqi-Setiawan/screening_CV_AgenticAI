from unittest.mock import AsyncMock, patch

import pytest

from src.domain.jd_compiler import compile_jd_rule_based, compile_job_requirements


def test_rule_based_importance_keywords():
    jd_nice = "- Menguasai Docker merupakan nilai tambah"
    reqs_nice = compile_jd_rule_based(jd_nice)
    assert len(reqs_nice) >= 1
    assert reqs_nice[0]["importance"] == "NICE_TO_HAVE"

    jd_must = "- Wajib memiliki pengalaman 3 tahun backend"
    reqs_must = compile_jd_rule_based(jd_must)
    assert len(reqs_must) >= 1
    assert reqs_must[0]["importance"] == "MUST_HAVE"


def test_section_parser_importance_and_order_invariance():
    jd1 = """Kualifikasi Wajib:
- Menguasai Microsoft Excel
- Pengalaman di bidang keuangan

Nilai tambah:
- Pengalaman di perbankan
- Memiliki sertifikasi CFA"""

    jd2 = """Nilai tambah:
- Memiliki sertifikasi CFA
- Pengalaman di perbankan

Kualifikasi Wajib:
- Pengalaman di bidang keuangan
- Menguasai Microsoft Excel"""

    res1 = compile_jd_rule_based(jd1)
    res2 = compile_jd_rule_based(jd2)

    # Check importance by description
    imp1 = {r["description"]: r["importance"] for r in res1}
    imp2 = {r["description"]: r["importance"] for r in res2}

    assert imp1["Menguasai Microsoft Excel"] == "MUST_HAVE"
    assert imp1["Pengalaman di bidang keuangan"] == "MUST_HAVE"
    assert imp1["Pengalaman di perbankan"] == "NICE_TO_HAVE"
    assert imp1["Memiliki sertifikasi CFA"] == "NICE_TO_HAVE"

    assert imp2["Menguasai Microsoft Excel"] == "MUST_HAVE"
    assert imp2["Pengalaman di bidang keuangan"] == "MUST_HAVE"
    assert imp2["Pengalaman di perbankan"] == "NICE_TO_HAVE"
    assert imp2["Memiliki sertifikasi CFA"] == "NICE_TO_HAVE"


def test_concept_regex_boundaries():
    # 'Familiar dengan Azure DevOps' should NOT match kubernetes
    jd = "- Familiar dengan Azure DevOps dan pipeline CI/CD"
    res = compile_jd_rule_based(jd)
    assert len(res) >= 1
    concepts = res[0]["concepts"]
    assert "skill:kubernetes" not in concepts


@pytest.mark.asyncio
async def test_llm_invalid_importance_coerced_or_fallback():
    mock_llm_res = {
        "requirements": [
            {
                "requirement_id": "R1",
                "description": "Menguasai Kubernetes merupakan nilai tambah",
                "importance": "SUPER_IMPORTANT",
                "weight": 500,
            }
        ]
    }

    with patch("src.domain.jd_compiler.gateway.call_chat", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_llm_res
        res = await compile_job_requirements("Sample JD text")
        reqs = res["requirements"]
        assert len(reqs) >= 1
        assert reqs[0]["importance"] == "NICE_TO_HAVE"
        # Weight clamped to max 30.0
        assert reqs[0]["weight"] <= 30.0
