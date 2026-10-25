"""Domain taxonomy loader and registry with Pydantic validation and regex verification (FX-31)."""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from src.infrastructure.config import settings
from src.infrastructure.logging import logger


class RoleFamilyEntry(BaseModel):
    titles: list[str] = Field(default_factory=list)
    domain_terms: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)


class SkillEntry(BaseModel):
    label: str
    type: str = "skill"
    aliases: list[str] = Field(default_factory=list)
    broader: str | None = None
    related: list[str] = Field(default_factory=list)
    category: str = "HARD_SKILLS"
    kind: str = "SKILL"
    default_importance: str = "STRONG_PREFERENCE"
    default_weight: float = 10.0
    jd_patterns: list[str] = Field(default_factory=list)


class Taxonomy(BaseModel):
    role_families: dict[str, RoleFamilyEntry]
    skills: dict[str, SkillEntry]
    certifications: dict[str, list[str]]
    leadership_verbs: list[str]
    leadership_titles: list[str]
    stopwords: list[str]

    compiled_role_titles: dict[str, list[re.Pattern]] = Field(default_factory=dict, exclude=True)
    compiled_leadership_verbs: list[re.Pattern] = Field(default_factory=list, exclude=True)
    compiled_leadership_titles: list[re.Pattern] = Field(default_factory=list, exclude=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data or {}


@functools.lru_cache(maxsize=1)
def get_taxonomy(tax_dir: str | None = None) -> Taxonomy:
    """Loads and compiles taxonomy from YAML configuration directory with fail-fast regex check."""
    root_path = Path(tax_dir or settings.TAXONOMY_DIR)
    if not root_path.is_absolute():
        root_path = Path("/srv/hermes-control/services/cv-screening") / root_path

    logger.info(f"Loading taxonomy from {root_path}...")

    # 1. Role families
    rf_raw = _load_yaml(root_path / "role_families.yaml")
    role_families: dict[str, RoleFamilyEntry] = {}
    for k, v in rf_raw.items():
        if isinstance(v, list):
            role_families[k] = RoleFamilyEntry(titles=v)
        elif isinstance(v, dict):
            role_families[k] = RoleFamilyEntry(**v)

    # 2. Skills
    sk_raw = _load_yaml(root_path / "skills.yaml")
    skills: dict[str, SkillEntry] = {}
    for k, v in sk_raw.items():
        if isinstance(v, dict):
            skills[k] = SkillEntry(**v)

    # 3. Certifications
    cert_raw = _load_yaml(root_path / "certifications.yaml")
    certifications: dict[str, list[str]] = {}
    for k, v in cert_raw.items():
        if isinstance(v, dict):
            certifications[k] = v.get("terms", [])
        elif isinstance(v, list):
            certifications[k] = v

    # 4. Leadership
    lead_raw = _load_yaml(root_path / "leadership.yaml")
    leadership_verbs = lead_raw.get("verbs", [])
    leadership_titles = lead_raw.get("titles", [])

    # 5. Stopwords
    sw_path = root_path / "stopwords.txt"
    stopwords = []
    if sw_path.exists():
        stopwords = [line.strip().lower() for line in sw_path.read_text().splitlines() if line.strip()]

    tax = Taxonomy(
        role_families=role_families,
        skills=skills,
        certifications=certifications,
        leadership_verbs=leadership_verbs,
        leadership_titles=leadership_titles,
        stopwords=stopwords,
    )

    # Compile regexes with fail-fast validation
    for rf_name, entry in tax.role_families.items():
        tax.compiled_role_titles[rf_name] = []
        for pat_str in entry.titles:
            try:
                tax.compiled_role_titles[rf_name].append(re.compile(rf"\b{re.escape(pat_str)}\b", re.I))
            except re.error as e:
                raise ValueError(f"Failed to compile regex in role_families.yaml [{rf_name}]: {pat_str} ({e})") from e

    for v_pat in tax.leadership_verbs:
        try:
            tax.compiled_leadership_verbs.append(re.compile(v_pat, re.I))
        except re.error as e:
            raise ValueError(f"Failed to compile regex in leadership.yaml [verbs]: {v_pat} ({e})") from e

    for t_pat in tax.leadership_titles:
        try:
            tax.compiled_leadership_titles.append(re.compile(t_pat, re.I))
        except re.error as e:
            raise ValueError(f"Failed to compile regex in leadership.yaml [titles]: {t_pat} ({e})") from e

    logger.info("Taxonomy successfully loaded and compiled.")
    return tax


def reset_taxonomy_cache() -> None:
    get_taxonomy.cache_clear()
