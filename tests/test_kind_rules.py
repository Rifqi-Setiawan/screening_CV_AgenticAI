"""Unit tests for pure functional kind rules (02_SCORING Section 4.2)."""

from __future__ import annotations

from src.domain.kind_rules import (
    eval_experience_duration,
    eval_leadership,
    eval_responsibility,
    eval_skill,
)


def test_duration_overlap_and_internship():
    # Job 1: 2020-01 to 2021-12 (24 months)
    # Job 2: 2021-06 to 2022-12 (overlaps with Job 1, ends 2022-12 -> total merged = 2020-01 to 2022-12 = 36 months)
    # Internship: 2023-01 to 2023-12 (12 months * 0.5 = 6 months)
    # Total = 36 + 6 = 42 months
    profile = {
        "experiences": [
            {
                "title": "Backend Engineer",
                "start": {"value": "2020-01"},
                "end": {"value": "2021-12"},
                "context": "experience",
                "employment_type": "full_time",
                "bullets": [],
            },
            {
                "title": "Backend Developer",
                "start": {"value": "2021-06"},
                "end": {"value": "2022-12"},
                "context": "experience",
                "employment_type": "full_time",
                "bullets": [],
            },
            {
                "title": "Backend Intern",
                "start": {"value": "2023-01"},
                "end": {"value": "2023-12"},
                "context": "internship",
                "employment_type": "internship",
                "bullets": [],
            },
        ]
    }
    req = {
        "kind": "EXPERIENCE_DURATION",
        "params": {"min_months": 36, "accepted_role_families": ["backend"]},
    }
    state, conf, metrics, ev, flags = eval_experience_duration(profile, req, as_of="2026-10-01")
    assert state == "STRONG"
    assert metrics["backend_months"] == 42.0


def test_duration_year_only_and_present():
    # Year-only: 2020 (defaults to 2020-07) to Present (2026-10) -> 2020-07 to 2026-10 = 76 months
    profile = {
        "experiences": [
            {
                "title": "Backend Engineer",
                "start": {"value": "2020"},
                "end": {"value": "present"},
                "context": "experience",
                "bullets": [],
            }
        ]
    }
    req = {
        "kind": "EXPERIENCE_DURATION",
        "params": {"min_months": 36, "accepted_role_families": ["backend"]},
    }
    state, conf, metrics, ev, flags = eval_experience_duration(profile, req, as_of="2026-10-01")
    assert state == "STRONG"
    assert metrics["backend_months"] >= 36.0


def test_context_hierarchy_dated_job_vs_project_vs_skills_list():
    req = {"kind": "SKILL", "concepts": ["skill:python"]}

    # Case A: in dated experience -> STRONG
    prof_job = {
        "experiences": [
            {"title": "Software Engineer", "bullets": [{"text": "Developed microservices with Python FastAPI."}]}
        ],
        "projects": [],
        "skills": [],
    }
    state_a, _, _, _, _ = eval_skill(prof_job, req)
    assert state_a == "STRONG"

    # Case B: in project only -> PARTIAL
    prof_prj = {
        "experiences": [],
        "projects": [{"title": "Web Scraper", "text": "Built a scraper with Python"}],
        "skills": [],
    }
    state_b, _, _, _, _ = eval_skill(prof_prj, req)
    assert state_b == "PARTIAL"

    # Case C: in skills list only -> PARTIAL
    prof_sk = {
        "experiences": [],
        "projects": [],
        "skills": ["Python", "FastAPI"],
    }
    state_c, _, _, _, _ = eval_skill(prof_sk, req)
    assert state_c == "PARTIAL"


def test_mysql_not_equal_postgresql():
    req_postgres = {"kind": "SKILL", "concepts": ["skill:postgresql"]}
    prof_mysql = {
        "experiences": [{"title": "Backend Dev", "bullets": [{"text": "Managed MySQL and MariaDB databases."}]}],
        "projects": [],
        "skills": ["MySQL"],
    }
    state, _, _, _, _ = eval_skill(prof_mysql, req_postgres)
    assert state == "NOT_DEMONSTRATED"


def test_docker_not_equal_kubernetes():
    req_k8s = {"kind": "SKILL", "concepts": ["skill:kubernetes"]}
    prof_docker = {
        "experiences": [{"title": "DevOps", "bullets": [{"text": "Packaged apps using Docker and Docker Compose."}]}],
        "projects": [],
        "skills": ["Docker"],
    }
    state, _, _, _, _ = eval_skill(prof_docker, req_k8s)
    assert state == "NOT_DEMONSTRATED"


def test_testing_api_not_equal_building_api():
    req_api = {"kind": "RESPONSIBILITY", "concepts": ["skill:rest_api"]}

    # Candidate 1: built production REST API -> STRONG
    prof_builder = {
        "experiences": [
            {
                "title": "Backend Engineer",
                "bullets": [{"text": "Membangun REST API performa tinggi untuk pembayaran online."}],
            }
        ]
    }
    st_build, _, _, _, _ = eval_responsibility(prof_builder, req_api)
    assert st_build == "STRONG"

    # Candidate 2: tested / QA automated tests for REST API -> PARTIAL (testing only)
    prof_tester = {
        "experiences": [
            {
                "title": "QA Automation",
                "bullets": [{"text": "Built API test automation covering 120 REST endpoints using pytest."}],
            }
        ]
    }
    st_test, _, _, _, _ = eval_responsibility(prof_tester, req_api)
    assert st_test == "PARTIAL"


def test_sales_leadership_not_equal_technical_leadership():
    req_lead = {"kind": "LEADERSHIP", "concepts": ["leadership:tech_lead"]}

    # Candidate 1: led sales team -> NOT_DEMONSTRATED
    prof_sales = {
        "experiences": [
            {
                "title": "Sales Manager",
                "bullets": [{"text": "Memimpin tim sales beranggotakan 10 orang mencapai target omzet."}],
            }
        ],
        "organizations": [],
        "projects": [],
    }
    st_sales, _, _, _, _ = eval_leadership(prof_sales, req_lead)
    assert st_sales == "NOT_DEMONSTRATED"

    # Candidate 2: led backend engineering team -> STRONG
    prof_tech = {
        "experiences": [
            {
                "title": "Lead Backend Engineer",
                "bullets": [{"text": "Memimpin tim 5 backend engineer dan melakukan code review."}],
            }
        ],
        "organizations": [],
        "projects": [],
    }
    st_tech, _, _, _, _ = eval_leadership(prof_tech, req_lead)
    assert st_tech == "STRONG"
