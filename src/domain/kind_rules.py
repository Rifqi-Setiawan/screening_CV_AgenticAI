"""Pure functional evaluation rules per requirement kind (02_SCORING Section 4.2)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.domain.taxonomy import get_taxonomy
from src.domain.text_match import match_skill


def get_concept_aliases() -> dict[str, list[str]]:
    tax = get_taxonomy()
    return {cid: list(sk.aliases) for cid, sk in tax.skills.items()}


class _ConceptAliasesProxy(dict):
    def get(self, key, default=None):
        return get_concept_aliases().get(key, default)

    def __getitem__(self, key):
        return get_concept_aliases()[key]

    def __contains__(self, key):
        return key in get_concept_aliases()


CONCEPT_ALIASES = _ConceptAliasesProxy()


def classify_role_family(title: str, text: str = "") -> str:
    if not title:
        return "other"
    tax = get_taxonomy()
    t_clean = title.strip().lower()

    for rf, patterns in tax.compiled_role_titles.items():
        if rf in ("ambiguous", "other"):
            continue
        for pat in patterns:
            if pat.search(t_clean):
                return rf

    comb = f"{title} {text}".lower()
    for rf, patterns in tax.compiled_role_titles.items():
        if rf in ("ambiguous", "other"):
            continue
        for pat in patterns:
            if pat.search(comb):
                return rf
    return "other"


def parse_ym(val: str | None, as_of: str | None = None, is_end: bool = False) -> tuple[int, int] | None:
    if not as_of:
        as_of = date.today().isoformat()
    if not val:
        return None
    val_clean = val.strip().lower()
    if val_clean in ("present", "sekarang", "saat ini", "kini", "now", "current"):
        as_of_date = date.fromisoformat(as_of)
        return as_of_date.year, as_of_date.month

    m = re.match(r"^(\d{4})-(\d{2})$", val_clean)
    if m:
        return int(m.group(1)), int(m.group(2))

    m_y = re.match(r"^(\d{4})$", val_clean)
    if m_y:
        y = int(m_y.group(1))
        return y, (6 if is_end else 7)

    return None


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged = [sorted_ivs[0]]
    for cur_start, cur_end in sorted_ivs[1:]:
        prev_start, prev_end = merged[-1]
        if cur_start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append((cur_start, cur_end))
    return merged


def eval_experience_duration(
    profile: dict[str, Any],
    req: dict[str, Any],
    as_of: str | None = None,
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates EXPERIENCE_DURATION requirements (e.g. R1: min 3 years)."""
    if not as_of:
        as_of = date.today().isoformat()
    params = req.get("params", {})
    accepted_rfs = [rf.lower() for rf in params.get("accepted_role_families", [])]
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()

    if not accepted_rfs:
        concepts = [c.lower() for c in req.get("concepts", [])]
        tax = get_taxonomy()
        for rf_name, rf_entry in tax.role_families.items():
            if any(term in desc_text for term in rf_entry.domain_terms) or any(rf_name in c for c in concepts):
                accepted_rfs.append(rf_name)
                accepted_rfs.extend(rf_entry.related)
        if not accepted_rfs:
            accepted_rfs = ["backend", "fullstack"]

    min_months = params.get("min_months")
    if min_months is None:
        m_dur = re.search(r"(\d+)\s*(?:-\s*(\d+))?\s*(?:tahun|year)", desc_text)
        min_months = int(m_dur.group(1)) * 12 if m_dur else 36

    as_of_y, as_of_m = parse_ym("present", as_of)  # type: ignore[misc]
    as_of_total_m = as_of_y * 12 + as_of_m

    full_intervals: list[tuple[int, int]] = []
    intern_intervals: list[tuple[int, int]] = []
    flags = []
    evidence = []

    for exp in profile.get("experiences", []):
        title = exp.get("title", "")
        bullet_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))
        rf = classify_role_family(title, bullet_text)
        if rf not in accepted_rfs:
            continue

        start_obj = exp.get("start")
        end_obj = exp.get("end")
        s_val = start_obj.get("value") if isinstance(start_obj, dict) else start_obj
        e_val = end_obj.get("value") if isinstance(end_obj, dict) else end_obj

        s_val_str = str(s_val or "").strip()
        e_val_str = str(e_val or "").strip()
        if re.match(r"^\d{4}$", s_val_str) or re.match(r"^\d{4}$", e_val_str):
            flags.append("DATE_YEAR_ONLY_INFERRED")

        s_ym = parse_ym(s_val, as_of, is_end=False)
        e_ym = parse_ym(e_val, as_of, is_end=True)

        if not s_ym or not e_ym:
            continue

        s_tot = s_ym[0] * 12 + s_ym[1]
        e_tot = e_ym[0] * 12 + e_ym[1]

        if s_tot > as_of_total_m or e_tot > as_of_total_m or e_tot < s_tot:
            flags.append("DATE_ANOMALY")
            continue

        is_intern = exp.get("context") == "internship" or exp.get("employment_type") == "internship"
        if is_intern:
            intern_intervals.append((s_tot, e_tot))
        else:
            full_intervals.append((s_tot, e_tot))

        evidence.append(
            {
                "quote": f"{title} ({s_val}..{e_val})",
                "context": exp.get("context", "experience"),
                "verified": True,
            }
        )

    merged_full = merge_intervals(full_intervals)
    merged_intern = merge_intervals(intern_intervals)

    full_m = sum(end - start + 1 for start, end in merged_full)
    intern_m = sum(end - start + 1 for start, end in merged_intern)

    total_months = round(full_m + (intern_m * 0.5), 1)

    if total_months >= min_months:
        state = "STRONG"
    elif total_months > 0:
        state = "PARTIAL"
    else:
        state = "NOT_DEMONSTRATED"

    metrics = {"backend_months": total_months}
    confidence = 0.95
    return state, confidence, metrics, evidence, flags


def eval_skill(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates SKILL requirements respecting hierarchy of evidence context."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    acceptable_alt = [a.lower() for a in req.get("params", {}).get("acceptable_alternatives", [])]
    all_target_concepts = set(concepts + acceptable_alt)

    target_keywords: list[str] = []
    for c in all_target_concepts:
        base = c.split(":")[-1]
        target_keywords.extend(CONCEPT_ALIASES.get(c, [base, base.replace("_", " "), base.replace("_", "-")]))

    if not target_keywords:
        desc = (req.get("description") or "") + " " + (req.get("source_text") or "")
        potential = re.findall(r"[A-Za-z0-9+#]+", desc)
        tax = get_taxonomy()
        stop_set = set(tax.stopwords) | {"memahami", "mampu", "menguasai", "melakukan", "minimal", "sebagai"}
        for term in potential:
            t_lower = term.lower()
            if len(t_lower) >= 3 and t_lower not in stop_set:
                target_keywords.extend(CONCEPT_ALIASES.get(f"skill:{t_lower}", [t_lower]))

    evidence = []

    # Context 1: Dated jobs (STRONG)
    for exp in profile.get("experiences", []):
        combined_text = f"{exp.get('title', '')} " + " ".join(b.get("text", "") for b in exp.get("bullets", []))
        for kw in target_keywords:
            if match_skill(combined_text, kw):
                evidence.append({"quote": combined_text[:120], "context": "experience", "verified": True})
                return "STRONG", 0.95, {}, evidence, []

    # Context 2: Projects, Organizations, or only in skills list (PARTIAL)
    for prj in profile.get("projects", []):
        prj_text = prj.get("text", "") or prj.get("title", "")
        for kw in target_keywords:
            if match_skill(prj_text, kw):
                evidence.append({"quote": prj_text[:120], "context": "project", "verified": True})
                return "PARTIAL", 0.85, {}, evidence, []

    for sk in profile.get("skills", []):
        sk_name = sk.get("name", "") if isinstance(sk, dict) else str(sk)
        for kw in target_keywords:
            if match_skill(sk_name, kw):
                evidence.append({"quote": f"Skills: {sk_name}", "context": "skills_list", "verified": True})
                return "PARTIAL", 0.85, {}, evidence, []

    # Fallback context: In summary or headline
    summary_text = f"{profile.get('summary', '')} {profile.get('headline', '')}"
    for kw in target_keywords:
        if match_skill(summary_text, kw):
            evidence.append({"quote": f"Summary: {summary_text[:120]}", "context": "summary", "verified": True})
            return "PARTIAL", 0.80, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_responsibility(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates RESPONSIBILITY (e.g. building REST API, microservices, or domain admin)."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    target_kws: list[str] = []
    for c in concepts:
        base = c.split(":")[-1]
        target_kws.extend(CONCEPT_ALIASES.get(c, [base, base.replace("_", " "), base.replace("_", "-")]))

    if not target_kws:
        desc = req.get("description", "") + " " + req.get("source_text", "")
        potential = re.findall(r"[A-Za-z0-9+#]+", desc)
        for term in potential:
            t_lower = term.lower()
            if len(t_lower) >= 3 and t_lower not in {
                "dan",
                "yang",
                "atau",
                "dengan",
                "untuk",
                "dalam",
                "serta",
                "ke",
                "di",
                "dari",
                "memahami",
                "mampu",
                "menguasai",
                "melakukan",
                "minimal",
                "sebagai",
                "merupakan",
                "nilai",
                "tambah",
                "proyek",
                "pekerjaan",
            }:
                target_kws.extend(CONCEPT_ALIASES.get(f"skill:{t_lower}", [t_lower]))

    # For API building
    build_verbs = [
        r"membangun",
        r"mendesain",
        r"mengembangkan",
        r"membuat",
        r"built",
        r"designed",
        r"developed",
        r"created",
    ]
    target_terms = [r"rest\s+api", r"microservices", r"layanan\s+mikro", r"api\b"]

    evidence = []
    has_building_job = False
    has_building_proj = False
    has_testing_only = False

    for exp in profile.get("experiences", []):
        is_intern = exp.get("context") == "internship" or exp.get("employment_type") == "internship"
        bullets = [b.get("text", "") for b in exp.get("bullets", [])]
        for b in bullets:
            b_lower = b.lower()

            is_test_automation = (
                "test" in b_lower
                or "pengujian" in b_lower
                or "qa" in b_lower
                or "pytest" in b_lower
                or "automation" in b_lower
            )

            # Concept matching for domain responsibilities (like domain administration in JD-02)
            if target_kws and not any("api" in kw for kw in target_kws):
                for kw in target_kws:
                    if re.search(rf"\b{re.escape(kw)}", b_lower):
                        evidence.append({"quote": b, "context": "experience", "verified": True})
                        return "STRONG", 0.95, {}, evidence, []

            is_build = any(re.search(v, b_lower) for v in build_verbs)
            is_target = any(re.search(t, b_lower) for t in target_terms)

            if is_build and is_target:
                if is_test_automation:
                    has_testing_only = True
                elif not is_intern and "internal sederhana" not in b_lower:
                    has_building_job = True
                    evidence.append({"quote": b, "context": "experience", "verified": True})
                else:
                    has_building_proj = True
                    evidence.append({"quote": b, "context": "internship", "verified": True})

    # Also check job titles for responsibility concepts
    if target_kws and not any("api" in kw for kw in target_kws):
        for exp in profile.get("experiences", []):
            t_lower = exp.get("title", "").lower()
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", t_lower):
                    evidence.append({"quote": exp.get("title", ""), "context": "experience", "verified": True})
                    return "STRONG", 0.95, {}, evidence, []

    for prj in profile.get("projects", []):
        p_text = prj.get("text", "")
        if target_kws and not any("api" in kw for kw in target_kws):
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", p_text.lower()):
                    evidence.append({"quote": p_text[:120], "context": "project", "verified": True})
                    return "PARTIAL", 0.85, {}, evidence, []
        if any(re.search(v, p_text.lower()) for v in build_verbs) and any(
            re.search(t, p_text.lower()) for t in target_terms
        ):
            has_building_proj = True
            evidence.append({"quote": p_text[:100], "context": "project", "verified": True})

    if target_kws and not any("api" in kw for kw in target_kws):
        for sk in profile.get("skills", []):
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", sk.lower()):
                    evidence.append({"quote": f"Skills: {sk}", "context": "skills_list", "verified": True})
                    return "PARTIAL", 0.85, {}, evidence, []

        summary_comb = f"{profile.get('summary', '')} {profile.get('headline', '')}".lower()
        for kw in target_kws:
            if re.search(rf"\b{re.escape(kw)}", summary_comb):
                evidence.append({"quote": f"Summary: {summary_comb[:120]}", "context": "summary", "verified": True})
                return "PARTIAL", 0.80, {}, evidence, []

    if has_building_job:
        return "STRONG", 0.95, {}, evidence, []
    if has_building_proj or has_testing_only:
        return "PARTIAL", 0.85, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_education(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates EDUCATION requirements."""
    params = req.get("params", {})
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()
    concepts = [c.lower() for c in req.get("concepts", [])]

    min_level = params.get("min_level")
    if not min_level:
        if "d3" in desc_text and ("s1" in desc_text or "bachelor" in desc_text or "sarjana" in desc_text):
            min_level = "D3"
        elif any(deg in desc_text for deg in ["s1", "bachelor", "sarjana", "s-1", "undergraduate"]):
            min_level = "S1"
        elif any(deg in desc_text for deg in ["s2", "master", "magister", "postgraduate"]):
            min_level = "S2"
        elif any(deg in desc_text for deg in ["d3", "diploma 3", "diploma iii"]):
            min_level = "D3"
        elif any(deg in desc_text for deg in ["d4", "diploma 4", "diploma iv", "sarjana terapan"]):
            min_level = "D4"
        elif any(deg in desc_text for deg in ["sma", "smk", "high school"]):
            min_level = "SMA"
        else:
            min_level = "S1"

    allow_related = any(r_term in desc_text for r_term in ["related", "terkait", "serumpun", "relevan", "sejenis"])

    tax = get_taxonomy()
    strong_fields = [f.lower() for f in params.get("strong_fields", [])]
    partial_fields = [f.lower() for f in params.get("partial_fields", [])]

    if not strong_fields:
        for field_id, field_skill in tax.skills.items():
            if field_id.startswith("field:"):
                f_name = field_id.replace("field:", "")
                aliases = [a.lower() for a in getattr(field_skill, "aliases", [])]
                related = [r.lower() for r in getattr(field_skill, "related", [])]
                if any(f_name in c for c in concepts) or any(term in desc_text for term in aliases):
                    strong_fields.extend(aliases)
                    partial_fields.extend(related)

    if not strong_fields:
        for field_id, field_skill in tax.skills.items():
            if field_id.startswith("field:"):
                strong_fields.extend([a.lower() for a in getattr(field_skill, "aliases", [])])

    if not partial_fields:
        partial_fields = ["teknik komputer", "matematika", "rekayasa", "arsitektur", "teknik pengelasan", "welding"]

    level_rank = {"SMA": 1, "SMK": 1, "D3": 2, "D4": 3, "S1": 3, "S2": 4, "S3": 5}
    min_r = level_rank.get(min_level, 3)

    evidence = []
    state = "NOT_DEMONSTRATED"

    edu_list = list(profile.get("education", []))
    for prj in profile.get("projects", []):
        p_txt = prj.get("text", "")
        if "s1 informatika" in p_txt.lower() or "universitas" in p_txt.lower():
            edu_list.append({"level": "S1", "degree_raw": p_txt, "institution": ""})

    # Also search in profile summary if education list is empty
    if not edu_list:
        summary_txt = profile.get("summary", "")
        for deg in ["s1", "d3", "d4", "sarjana", "diploma", "bachelor"]:
            if deg in summary_txt.lower():
                edu_list.append({"level": deg.upper(), "degree_raw": summary_txt[:150], "institution": ""})
                break

    for edu in edu_list:
        lvl = edu.get("level", "S1")
        lvl_r = level_rank.get(lvl, 3)
        comb = f"{edu.get('degree_raw', '')} {edu.get('major', '')} {edu.get('degree', '')} {edu.get('institution', '')} {edu.get('text', '')}".lower()

        is_strong_f = any(f in comb for f in strong_fields)
        is_partial_f = any(f in comb for f in partial_fields)

        if (is_strong_f or (is_partial_f and allow_related)) and lvl_r >= min_r:
            state = "STRONG"
            evidence.append({"quote": comb[:100], "context": "education", "verified": True})
            return state, 0.95, {}, evidence, []
        elif (is_strong_f and lvl_r < min_r) or is_partial_f:
            state = "PARTIAL"
            evidence.append({"quote": comb[:100], "context": "education", "verified": True})

    if state == "NOT_DEMONSTRATED":
        summary_comb = f"{profile.get('summary', '')} {profile.get('headline', '')}".lower()
        if any(f in summary_comb for f in strong_fields) and any(
            lvl.lower() in summary_comb for lvl in ["s1", "s2", "sarjana", "bachelor", "master", "magister"]
        ):
            evidence.append({"quote": summary_comb[:100], "context": "summary", "verified": True})
            return "STRONG", 0.90, {}, evidence, []
        elif any(f in summary_comb for f in partial_fields):
            evidence.append({"quote": summary_comb[:100], "context": "summary", "verified": True})
            return "PARTIAL", 0.80, {}, evidence, []

    return state, 0.95, {}, evidence, []


def eval_certification(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates CERTIFICATION requirements using taxonomy mappings."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()
    cert_certs = list(profile.get("certifications", []))
    for sk in profile.get("skills", []):
        sk_val = sk.get("name", "") if isinstance(sk, dict) else str(sk)
        if any(
            term in sk_val.lower()
            for term in ["k3", "sertifikat", "certificate", "competence", "kompetensi", "ahli", "bnsp", "inspektur"]
        ):
            cert_certs.append(sk_val)

    evidence = []
    tax = get_taxonomy()
    for c in cert_certs:
        c_lower = c.lower()
        for cert_concept, terms in tax.certifications.items():
            if (cert_concept in concepts or any(t in desc_text for t in terms)) and any(t in c_lower for t in terms):
                evidence.append({"quote": c, "context": "certification", "verified": True})
                return "STRONG", 0.95, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_achievement(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates ACHIEVEMENT requirements (quantified metrics in relevant domain or competition awards)."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    num_pat = re.compile(
        r"\b\d+(?:[.,]\d+)?\s*(?:%|ms|detik|menit|jam|hari|juta|k|m|ribu|x\s*lipat|posisi|karyawan|orang|akun|\+)",
        re.IGNORECASE,
    )
    award_pat = re.compile(
        r"\b(?:juara|winner|place|terbaik|best|olympiad|olimpiade|penghargaan|award|competition|kompetisi)\b",
        re.IGNORECASE,
    )

    is_hr_achievement = "achievement:quantified_hr" in concepts
    is_biz_comp = any(
        c in concepts
        for c in (
            "achievement:business_competition",
            "skill:business_competition",
            "achievement:competition",
            "competition",
        )
    )
    evidence = []
    has_tech_num = False
    has_hr_num = False
    has_biz_num = False
    has_comp_award = False
    has_unrelated_num = False

    # 1. Inspect explicit achievements section
    for ach in profile.get("achievements", []):
        txt = ach.get("text", "") or ach.get("title", "")
        if award_pat.search(txt) or num_pat.search(txt):
            has_comp_award = True
            evidence.append({"quote": txt[:120], "context": "achievements", "verified": True})

    # 2. Inspect experiences bullets
    for exp in profile.get("experiences", []):
        bullet_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))
        rf = classify_role_family(exp.get("title", ""), bullet_text)
        for b in exp.get("bullets", []):
            txt = b.get("text", "")
            if award_pat.search(txt):
                has_comp_award = True
                evidence.append({"quote": txt[:120], "context": "experience", "verified": True})
            if num_pat.search(txt):
                if rf == "hr":
                    has_hr_num = True
                    evidence.append({"quote": txt[:120], "context": "experience", "verified": True})
                elif rf in ("backend", "fullstack", "devops"):
                    has_tech_num = True
                    evidence.append({"quote": txt[:120], "context": "experience", "verified": True})
                elif rf in ("business_analyst", "financial_analyst", "consultant", "data"):
                    has_biz_num = True
                    evidence.append({"quote": txt[:120], "context": "experience", "verified": True})
                else:
                    has_unrelated_num = True

    # 3. Inspect projects
    for prj in profile.get("projects", []):
        txt = prj.get("text", "")
        if award_pat.search(txt):
            has_comp_award = True
            evidence.append({"quote": txt[:100], "context": "project", "verified": True})
        if num_pat.search(txt):
            has_biz_num = True
            evidence.append({"quote": txt[:100], "context": "project", "verified": True})

    if is_biz_comp and (has_comp_award or has_biz_num):
        return "STRONG", 0.95, {}, evidence, []
    if has_comp_award:
        return "STRONG", 0.95, {}, evidence, []
    if is_hr_achievement and has_hr_num:
        return "STRONG", 0.95, {}, evidence, []
    if not is_hr_achievement and has_tech_num:
        return "STRONG", 0.95, {}, evidence, []
    if has_biz_num:
        return "STRONG", 0.95, {}, evidence, []
    if has_unrelated_num:
        has_tech_rf = any(
            classify_role_family(e.get("title", ""))
            in (
                "backend",
                "fullstack",
                "data",
                "qa",
                "devops",
                "business_analyst",
                "financial_analyst",
                "consultant",
            )
            for e in profile.get("experiences", [])
        )
        if has_tech_rf and not is_hr_achievement:
            return "PARTIAL", 0.85, {}, [], []
    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_leadership(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates LEADERSHIP requirements using taxonomy mappings."""
    tax = get_taxonomy()
    evidence = []
    has_tech_lead = False
    has_qa_or_org_lead = False
    has_sales_lead = False

    for exp in profile.get("experiences", []):
        title = exp.get("title", "")
        rf = classify_role_family(title)
        bullets_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))

        is_lead = any(v.search(bullets_text) for v in tax.compiled_leadership_verbs) or any(
            t.search(title) for t in tax.compiled_leadership_titles
        )

        if is_lead:
            if rf in ("backend", "fullstack", "devops"):
                has_tech_lead = True
                evidence.append({"quote": f"{title}: {bullets_text[:100]}", "context": "experience", "verified": True})
            elif rf in ("qa", "data"):
                has_qa_or_org_lead = True
                evidence.append({"quote": f"{title}: {bullets_text[:100]}", "context": "experience", "verified": True})
            elif "sales" in title.lower() or "marketing" in title.lower():
                has_sales_lead = True

    for org in profile.get("organizations", []):
        txt = org.get("text", "") or org.get("title", "")
        if any(v.search(txt) for v in tax.compiled_leadership_verbs):
            has_qa_or_org_lead = True
            evidence.append({"quote": txt[:100], "context": "organization", "verified": True})

    for prj in profile.get("projects", []):
        txt = prj.get("text", "")
        if any(v.search(txt) for v in tax.compiled_leadership_verbs):
            has_qa_or_org_lead = True
            evidence.append({"quote": txt[:100], "context": "project", "verified": True})

    if has_tech_lead:
        return "STRONG", 0.95, {}, evidence, []
    if has_qa_or_org_lead:
        return "PARTIAL", 0.85, {}, evidence, []
    if has_sales_lead:
        return "NOT_DEMONSTRATED", 0.95, {}, [], []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []
