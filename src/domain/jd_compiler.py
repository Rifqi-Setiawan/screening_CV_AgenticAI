"""Job description compiler parsing JD text into structured requirements with concept mapping."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.domain.pii import sanitize_contact_pii
from src.domain.policy_linter import lint_text
from src.infrastructure.gateway import gateway
from src.infrastructure.logging import logger

VALID_IMPORTANCE = {"MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"}
VALID_CATEGORIES = {"EXPERIENCE", "HARD_SKILLS", "EDUCATION_CERT", "ACHIEVEMENT"}
MUST_HAVE_KEYWORDS = {"wajib", "harus", "must", "required", "minimum", "minimal", "essential"}
NICE_TO_HAVE_KEYWORDS = {"nilai tambah", "plus", "preferred", "nice to have", "diutamakan", "keuntungan"}

HEADER_MUST_HAVE = re.compile(
    r"(?:kualifikasi\s+wajib|persyaratan\s+wajib|\brequirements\b|\bwajib\b|\bmust\b|\bminimum\b)",
    re.IGNORECASE,
)
HEADER_NICE_TO_HAVE = re.compile(
    r"(?:nilai\s+tambah|diutamakan|\bpreferred\b|nice\s+to\s+have|\bplus\b|\bkeuntungan\b)",
    re.IGNORECASE,
)


class CompiledRequirement(BaseModel):
    requirement_id: str
    description: str
    category: str = "HARD_SKILLS"
    kind: str = "SKILL"
    importance: Literal["MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"]
    weight: float = Field(default=10.0, ge=1.0, le=30.0)
    concepts: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    source_text: str = ""


def determine_importance(line: str, default: str = "STRONG_PREFERENCE") -> str:
    lower = line.lower()
    if re.search(r"\b(?:wajib|harus|must|required|minimum|minimal|essential)\b", lower):
        return "MUST_HAVE"
    if re.search(r"\b(?:nilai\s+tambah|nice\s+to\s+have|plus|diutamakan|preferred|keuntungan)\b", lower):
        return "NICE_TO_HAVE"
    return default


DEFAULT_CATEGORY_WEIGHTS = {
    "EXPERIENCE": 40,
    "HARD_SKILLS": 30,
    "EDUCATION_CERT": 15,
    "ACHIEVEMENT": 15,
}

CONCEPT_RULES = [
    (
        r"\b(?:backend\s+engineer|backend\s+developer)\b",
        ["role_family:backend"],
        "EXPERIENCE",
        "EXPERIENCE_DURATION",
        "MUST_HAVE",
        25,
    ),
    (
        r"\b(?:rest\s+api|microservices)\b",
        ["skill:rest_api", "skill:microservices"],
        "EXPERIENCE",
        "RESPONSIBILITY",
        "STRONG_PREFERENCE",
        15,
    ),
    (
        r"\b(?:python|fastapi|django|flask)\b",
        ["skill:python"],
        "HARD_SKILLS",
        "SKILL",
        "MUST_HAVE",
        10,
    ),
    (
        r"\b(?:postgresql|postgres)\b",
        ["skill:postgresql"],
        "HARD_SKILLS",
        "SKILL",
        "MUST_HAVE",
        8,
    ),
    (
        r"\bdocker\b",
        ["skill:docker"],
        "HARD_SKILLS",
        "SKILL",
        "STRONG_PREFERENCE",
        6,
    ),
    (
        r"(?:cloud\s*\((?:aws|gcp|azure)\)|\b(?:kubernetes|k8s)\b)",
        ["skill:kubernetes", "skill:cloud"],
        "HARD_SKILLS",
        "SKILL",
        "NICE_TO_HAVE",
        6,
    ),
    (
        r"\b(?:memimpin|membimbing|mentoring)\b",
        ["skill:mentoring"],
        "EXPERIENCE",
        "RESPONSIBILITY",
        "NICE_TO_HAVE",
        5,
    ),
    (
        r"\b(?:sertifikasi\s+cloud|certified)\b",
        ["cert:cloud"],
        "EDUCATION_CERT",
        "CERTIFICATION",
        "NICE_TO_HAVE",
        5,
    ),
    (
        r"\b(?:pencapaian\s+terukur|skala|efisiensi)\b",
        ["achievement:quantified_backend"],
        "ACHIEVEMENT",
        "ACHIEVEMENT",
        "NICE_TO_HAVE",
        10,
    ),
    (
        r"\b(?:s1\s+teknik\s+informatika|ilmu\s+komputer|sistem\s+informasi)\b",
        ["field:computing"],
        "EDUCATION_CERT",
        "EDUCATION",
        "STRONG_PREFERENCE",
        10,
    ),
]


def extract_demographic_suggestions(jd_text: str) -> tuple[str, list[dict[str, Any]]]:
    """Strips demographic criteria from JD text and converts them to eligibility suggestions.

    Demographic criteria (age, gender) are NEVER sent to LLM or scoring rubric.
    """
    suggestions: list[dict[str, Any]] = []
    cleaned_lines: list[str] = []

    for raw_line in jd_text.splitlines():
        line_clean = raw_line.strip()
        if not line_clean:
            cleaned_lines.append(raw_line)
            continue

        l_res = lint_text(line_clean)
        admin_flags = l_res.get("admin_flags", [])

        if "ADMIN_ONLY_AGE" in admin_flags:
            val_age: dict[str, Any] | None = None
            m_max = re.search(
                r"(?:maksimal|maks|max|maximum)\.?\s*(\d+)\s*(?:tahun|years|thn)?",
                line_clean,
                re.I,
            )
            m_min = re.search(
                r"(?:minimal|min|minimum)\.?\s*(\d+)\s*(?:tahun|years|thn)?",
                line_clean,
                re.I,
            )
            if m_max:
                rule_t = "AGE_MAX"
                val_age = {"years": int(m_max.group(1))}
            elif m_min:
                rule_t = "AGE_MIN"
                val_age = {"years": int(m_min.group(1))}
            else:
                rule_t = "AGE_MAX"
                m_num = re.search(r"\b(\d{2})\s*(?:tahun|thn|years)\b", line_clean, re.I)
                if m_num:
                    val_age = {"years": int(m_num.group(1))}

            suggestions.append(
                {
                    "rule_type": rule_t,
                    "value": val_age,
                    "source_text": line_clean.lstrip("-*• 0123456789.)").strip(),
                }
            )
        elif "ADMIN_ONLY_GENDER" in admin_flags:
            allowed: list[str] = []
            if re.search(r"\b(?:wanita|perempuan|female)\b", line_clean, re.I):
                allowed.append("F")
            elif re.search(r"\b(?:pria|laki[\s-]laki|male)\b", line_clean, re.I):
                allowed.append("M")

            val_gender: dict[str, Any] | None = {"allowed": allowed} if allowed else None
            suggestions.append(
                {
                    "rule_type": "GENDER",
                    "value": val_gender,
                    "source_text": line_clean.lstrip("-*• 0123456789.)").strip(),
                }
            )
        else:
            cleaned_lines.append(raw_line)

    return "\n".join(cleaned_lines), suggestions


def compile_jd_rule_based(jd_text: str) -> list[dict[str, Any]]:
    """Deterministic fallback parser mapping bullet points and requirements to concept taxonomy."""
    requirements = []
    raw_lines = [line.strip() for line in jd_text.splitlines() if line.strip()]

    matched_concepts: set[str] = set()
    req_idx = 1
    current_section = "STRONG_PREFERENCE"

    for orig_line in raw_lines:
        clean = orig_line.strip()
        # Detect section header
        if (
            clean.endswith(":")
            or clean.startswith("#")
            or not clean.startswith(("-", "*", "•", "1", "2", "3", "4", "5", "6", "7", "8", "9"))
        ):
            if HEADER_MUST_HAVE.search(clean):
                current_section = "MUST_HAVE"
                continue
            elif HEADER_NICE_TO_HAVE.search(clean):
                current_section = "NICE_TO_HAVE"
                continue
            elif clean.endswith(":"):
                current_section = "STRONG_PREFERENCE"
                continue

        line = orig_line.lstrip("-*• 0123456789.)").strip()
        if len(line) < 5 or line.startswith("#"):
            continue

        matched = False
        for pat, concepts, category, kind, _default_importance, default_weight in CONCEPT_RULES:
            if re.search(pat, line, re.IGNORECASE):
                c_key = concepts[0]
                if c_key in matched_concepts:
                    matched = True
                    break
                matched_concepts.add(c_key)

                importance = determine_importance(line, current_section)
                lint_res = lint_text(line)

                requirements.append(
                    {
                        "requirement_id": f"R{req_idx}",
                        "description": line,
                        "category": category,
                        "kind": kind,
                        "importance": importance,
                        "weight": default_weight,
                        "concepts": concepts,
                        "params": {},
                        "source_text": line,
                        "lint_flags": lint_res["prohibited_flags"]
                        + lint_res["risky_flags"]
                        + lint_res.get("admin_flags", []),
                    }
                )
                req_idx += 1
                matched = True
                break

        if not matched and (orig_line.startswith(("-", "*", "•")) or re.match(r"^\d+[\.\)]", orig_line)):
            lower = line.lower()
            is_exp = "tahun" in lower or "pengalaman" in lower or "experience" in lower
            is_edu = any(
                k in lower for k in ["s1", "s2", "d3", "gelar", "pendidikan", "degree", "sertifikasi", "certified"]
            )
            cat = "EXPERIENCE" if is_exp else ("EDUCATION_CERT" if is_edu else "HARD_SKILLS")
            knd = "EXPERIENCE_DURATION" if is_exp else ("EDUCATION" if is_edu else "SKILL")
            imp = determine_importance(line, current_section)
            lint_res = lint_text(line)
            requirements.append(
                {
                    "requirement_id": f"R{req_idx}",
                    "description": line,
                    "category": cat,
                    "kind": knd,
                    "importance": imp,
                    "weight": 10.0,
                    "concepts": [],
                    "params": {},
                    "source_text": line,
                    "lint_flags": lint_res["prohibited_flags"]
                    + lint_res["risky_flags"]
                    + lint_res.get("admin_flags", []),
                }
            )
            req_idx += 1

    return requirements


async def compile_job_requirements(jd_text: str, tenant_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Compiles Job Description into structured requirement set with demographic filtering."""
    # 1. Overall lint
    overall_lint = lint_text(jd_text)

    # 2. Extract demographic criteria into administrative suggestions and strip from prompt
    clean_no_demographics, eligibility_suggestions = extract_demographic_suggestions(jd_text)

    # 3. Sanitize recruiter contact details
    clean_jd_text = sanitize_contact_pii(clean_no_demographics)

    # 4. Attempt LLM compilation via 9Router
    prompt = (
        "Kamu adalah compiler Job Description menjadi kriteria screening terstruktur.\n"
        "Analisis teks lowongan ini dan hasilkan JSON array 'requirements' dengan field:\n"
        "- requirement_id (R1, R2, ...)\n"
        "- description (teks deskripsi)\n"
        "- category (EXPERIENCE, HARD_SKILLS, EDUCATION_CERT, ACHIEVEMENT)\n"
        "- kind (EXPERIENCE_DURATION, RESPONSIBILITY, SKILL, EDUCATION, CERTIFICATION, ACHIEVEMENT)\n"
        "- importance (MUST_HAVE, STRONG_PREFERENCE, NICE_TO_HAVE)\n"
        "- weight (angka 1-30)\n"
        "- concepts (array concept_id seperti role_family:backend, skill:python, skill:postgresql, skill:docker)\n"
        "- source_text (kalimat asli dari JD)\n\n"
        f"Teks Job Description:\n{clean_jd_text}"
    )

    try:
        llm_res = await gateway.call_chat(
            messages=[{"role": "user", "content": prompt}],
            task="jd_compilation",
            tenant_id=tenant_id,
            json_mode=True,
        )
    except Exception as e:
        logger.warning(f"LLM compilation failed, falling back to rule-based: {e}")
        llm_res = None

    req_list = []
    if isinstance(llm_res, list):
        req_list = llm_res
    elif isinstance(llm_res, dict) and isinstance(llm_res.get("requirements"), list):
        req_list = llm_res["requirements"]

    validated_reqs = []
    if req_list:
        try:
            for idx, item in enumerate(req_list, 1):
                raw_imp = str(item.get("importance", "")).upper()
                if raw_imp not in VALID_IMPORTANCE:
                    raw_imp = determine_importance(item.get("description", "") or item.get("source_text", ""))

                raw_wt = float(item.get("weight") or 10.0)
                raw_wt = max(1.0, min(30.0, raw_wt))

                desc = item.get("description", "")
                r_lint = lint_text(desc)
                if any(f.startswith("ADMIN_ONLY_") for f in r_lint["admin_flags"]):
                    continue

                item_cat = item.get("category") if item.get("category") in VALID_CATEGORIES else "HARD_SKILLS"
                concepts = list(item.get("concepts", []))

                # Concept augmentation only if rule category matches requirement category
                for pat, c_list, r_cat, _knd, _imp, _wt in CONCEPT_RULES:
                    if r_cat == item_cat and (
                        re.search(pat, desc, re.IGNORECASE)
                        or re.search(pat, item.get("source_text", ""), re.IGNORECASE)
                    ):
                        for c in c_list:
                            if c not in concepts:
                                concepts.append(c)

                model = CompiledRequirement(
                    requirement_id=f"R{idx}",
                    description=desc,
                    category=item_cat,
                    kind=item.get("kind") or "SKILL",
                    importance=raw_imp,  # type: ignore[arg-type]
                    weight=raw_wt,
                    concepts=concepts,
                    params=item.get("params") or {},
                    source_text=item.get("source_text") or desc,
                )
                req_dict = model.model_dump()
                req_dict["lint_flags"] = (
                    r_lint["prohibited_flags"] + r_lint["risky_flags"] + r_lint.get("admin_flags", [])
                )
                validated_reqs.append(req_dict)
        except Exception as e:
            logger.warning(f"Validation failed for LLM requirements output: {e}, falling back to rule-based.")
            validated_reqs = []

    requirements = validated_reqs or compile_jd_rule_based(clean_no_demographics)

    # Filter out any lingering demographic requirements
    clean_reqs = []
    for r in requirements:
        r_lint = lint_text(r["description"] + " " + r.get("source_text", ""))
        if any(f.startswith("ADMIN_ONLY_") for f in r_lint["admin_flags"]):
            continue
        clean_reqs.append(r)
    requirements = clean_reqs

    # Compile warnings
    compile_warnings = []
    must_have_count = sum(1 for r in requirements if r["importance"] == "MUST_HAVE")
    if must_have_count > 5:
        compile_warnings.append("TOO_MANY_MUST_HAVE")

    # Overall prohibited flags
    all_prohibited = list(overall_lint["prohibited_flags"])
    for r in requirements:
        all_prohibited.extend([f for f in r.get("lint_flags", []) if f.startswith("PROHIBITED_")])
    all_prohibited = sorted(list(set(all_prohibited)))

    return {
        "status": "DRAFT",
        "category_weights": DEFAULT_CATEGORY_WEIGHTS,
        "requirements": requirements,
        "eligibility_suggestions": eligibility_suggestions,
        "is_valid": len(all_prohibited) == 0,
        "prohibited_flags": all_prohibited,
        "risky_flags": overall_lint["risky_flags"],
        "admin_flags": overall_lint.get("admin_flags", []),
        "compile_warnings": compile_warnings,
    }
