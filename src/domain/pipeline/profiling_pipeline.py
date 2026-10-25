"""Graph A: Autonomous CV Ingestion and Profiling Pipeline (v2.1).

Implements Section C2 (Graph A) and C10 of Blueprint v2.1:
1. Visibility Gate: Filters micro-font (<4pt), white-on-white text, and out-of-bounds spans.
2. Evidence Atomizer: Builds deterministically addressed, fine-grained evidence atoms and OffsetMap.
3. Profiler Agent: Tags atoms with capability ontology concepts and allocates experience domains.
4. Database Persistence: Stores offset maps, evidence atoms, and profiler results into PostgreSQL.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.agents.profiler import ProfilerOutput, run_profiler_agent, save_profiler_results
from src.domain.atoms import (
    EvidenceAtom,
    OffsetMap,
    atomize_candidate_profile,
    create_offset_map,
)
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger
from src.worker.visibility import SpanVisibility, VisibilityFilterResult, filter_visible_spans


@dataclass
class ProfilingResult:
    """Output artifact of Graph A (Profiling Pipeline)."""

    profile_id: uuid.UUID
    atoms: list[EvidenceAtom] = field(default_factory=list)
    profiler_output: ProfilerOutput = field(default_factory=ProfilerOutput)
    offset_map: OffsetMap | None = None
    visibility_result: VisibilityFilterResult | None = None
    flags: list[str] = field(default_factory=list)
    raw_text: str = ""
    redacted_text: str = ""
    document_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None

    @property
    def has_hidden_text(self) -> bool:
        return "HIDDEN_TEXT" in self.flags or (
            self.visibility_result is not None and self.visibility_result.has_hidden_text
        )

    @property
    def atom_map(self) -> dict[str, EvidenceAtom]:
        return {a.atom_key: a for a in self.atoms}

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "atoms_count": len(self.atoms),
            "flags": self.flags,
            "has_hidden_text": self.has_hidden_text,
            "experiences_count": len(self.profiler_output.experiences),
            "atom_tags_count": len(self.profiler_output.atom_tags),
        }


def _parse_raw_text_into_profile(raw_text: str) -> dict[str, Any]:
    """Lightweight deterministic text splitter converting raw CV text into section dict.

    Used when candidate_profile dictionary is not pre-parsed.
    """
    profile: dict[str, Any] = {
        "experiences": [],
        "skills": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "summary": "",
    }

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    current_sec = "summary"
    sec_lines: dict[str, list[str]] = {
        "summary": [],
        "experience": [],
        "skills": [],
        "projects": [],
        "education": [],
        "certifications": [],
    }

    for line in lines:
        lower = line.lower()
        if any(h in lower for h in ("pengalaman", "experience", "riwayat kerja")):
            current_sec = "experience"
            continue
        if any(h in lower for h in ("keahlian", "skills", "kemampuan", "teknologi")):
            current_sec = "skills"
            continue
        if any(h in lower for h in ("proyek", "projects", "portofolio")):
            current_sec = "projects"
            continue
        if any(h in lower for h in ("pendidikan", "education", "akademik")):
            current_sec = "education"
            continue
        if any(h in lower for h in ("sertifikasi", "certification", "licenses")):
            current_sec = "certifications"
            continue
        if any(h in lower for h in ("ringkasan", "summary", "tentang saya", "about")):
            current_sec = "summary"
            continue

        sec_lines[current_sec].append(line)

    profile["summary"] = " ".join(sec_lines["summary"])

    # Experiences
    exp_bullets: list[str] = []
    current_title = "Software Engineer"
    for el in sec_lines["experience"]:
        if el.startswith(("-", "*", "•")):
            bullet_clean = re.sub(r"^[-*•]\s*", "", el).strip()
            if bullet_clean:
                exp_bullets.append(bullet_clean)
        else:
            if exp_bullets:
                profile["experiences"].append(
                    {
                        "entry_id": f"exp_{len(profile['experiences']) + 1}",
                        "title": current_title,
                        "organization": "Company",
                        "bullets": exp_bullets,
                    }
                )
                exp_bullets = []
            current_title = el
    if current_title or exp_bullets:
        profile["experiences"].append(
            {
                "entry_id": f"exp_{len(profile['experiences']) + 1}",
                "title": current_title or "Engineer",
                "organization": "Company",
                "bullets": exp_bullets,
            }
        )

    # Skills
    for sl in sec_lines["skills"]:
        cleaned = re.sub(r"^[-*•]\s*", "", sl).strip()
        parts = re.split(r"[,;|]\s*", cleaned)
        for p in parts:
            if p.strip():
                profile["skills"].append({"name": p.strip()})

    # Projects
    for pl in sec_lines["projects"]:
        p_clean = re.sub(r"^[-*•]\s*", "", pl).strip()
        if p_clean:
            profile["projects"].append({"title": p_clean, "text": p_clean})

    # Education
    for ed in sec_lines["education"]:
        e_clean = re.sub(r"^[-*•]\s*", "", ed).strip()
        if e_clean:
            profile["education"].append({"institution": e_clean, "text": e_clean})

    # Certifications
    for cert in sec_lines["certifications"]:
        c_clean = re.sub(r"^[-*•]\s*", "", cert).strip()
        if c_clean:
            profile["certifications"].append({"name": c_clean})

    return profile


class ProfilingPipeline:
    """Graph A: Document Ingestion, Visibility Verification, Atomization, and Profiling."""

    def __init__(
        self,
        client: Any = None,
        ontology: OntologyGraph | None = None,
    ) -> None:
        self.client = client
        self.ontology = ontology or get_ontology_graph()

    async def run(
        self,
        profile_id: uuid.UUID | str,
        raw_text: str = "",
        pdf_spans: list[dict[str, Any]] | Any = None,
        candidate_profile: dict[str, Any] | None = None,
        pii_spans: list[tuple[int, int, str]] | None = None,
        document_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        raw_title: str | None = None,
        save_to_db: bool = False,
        conn: Any = None,
    ) -> ProfilingResult:
        """Executes full Graph A profiling pipeline.

        Args:
            profile_id: Candidate profile UUID.
            raw_text: Raw unredacted CV text.
            pdf_spans: Optional PyMuPDF spans or Document object for visibility checking.
            candidate_profile: Optional pre-parsed profile dictionary.
            pii_spans: Optional list of (char_start, char_end, replacement) for OffsetMap.
            document_id: Optional document UUID.
            tenant_id: Optional tenant identifier.
            raw_title: Optional raw job title context.
            save_to_db: Whether to persist atoms and profiler results to PostgreSQL.
            conn: Optional database connection (if None and save_to_db=True, creates one).

        Returns:
            ProfilingResult containing generated evidence atoms and profiler outputs.
        """
        prof_uuid = uuid.UUID(str(profile_id))
        doc_uuid = uuid.UUID(str(document_id)) if document_id else None
        ten_uuid = uuid.UUID(str(tenant_id)) if tenant_id else uuid.uuid4()
        pipeline_flags: list[str] = []

        # ------------------------------------------------------------------
        # Step 1: Visibility Gate (N0b)
        # ------------------------------------------------------------------
        vis_result: VisibilityFilterResult | None = None
        hidden_texts: set[str] = set()

        if pdf_spans is not None:
            vis_result = filter_visible_spans(pdf_spans, include_suspect=True)
            if vis_result.has_hidden_text:
                pipeline_flags.append("HIDDEN_TEXT")
                for hs in vis_result.hidden_spans:
                    htext = hs.get("text", "").strip()
                    if htext:
                        hidden_texts.add(htext)
            logger.info(
                f"Visibility Gate: {len(vis_result.visible_spans)} visible spans, "
                f"{len(vis_result.hidden_spans)} hidden spans (flags: {vis_result.flags})"
            )

        # ------------------------------------------------------------------
        # Step 2: Prepare Candidate Profile Structure
        # ------------------------------------------------------------------
        if candidate_profile is not None:
            profile_dict = json.loads(json.dumps(candidate_profile))
        else:
            profile_dict = _parse_raw_text_into_profile(raw_text)

        # Mark any items matching hidden texts as HIDDEN so atomizer drops them
        if hidden_texts:
            for exp in profile_dict.get("experiences", []):
                for b in exp.get("bullets", []):
                    b_txt = b.get("text", "") if isinstance(b, dict) else str(b)
                    if any(ht in b_txt for ht in hidden_texts) and isinstance(b, dict):
                        b["visibility"] = SpanVisibility.HIDDEN.value
            for sk in profile_dict.get("skills", []):
                s_name = sk.get("name", "") if isinstance(sk, dict) else str(sk)
                if any(ht in s_name for ht in hidden_texts) and isinstance(sk, dict):
                    sk["visibility"] = SpanVisibility.HIDDEN.value

        # ------------------------------------------------------------------
        # Step 3: Redaction OffsetMap and Evidence Atomizer (N1, N2)
        # ------------------------------------------------------------------
        pii_list = pii_spans or []
        redacted_text, offset_map = create_offset_map(
            raw_text=raw_text,
            pii_spans=pii_list,
            document_id=str(doc_uuid) if doc_uuid else None,
            tenant_id=str(ten_uuid),
        )

        atoms = atomize_candidate_profile(
            profile=profile_dict,
            raw_text=raw_text,
            redacted_text=redacted_text,
            offset_map=offset_map,
        )

        # Enforce that no atom is HIDDEN (guarantee Grounding by Construction)
        atoms = [a for a in atoms if a.visibility != SpanVisibility.HIDDEN.value]
        for a in atoms:
            if not getattr(a, "id", None):
                a.id = uuid.uuid4()

        logger.info(f"Evidence Atomizer produced {len(atoms)} visible evidence atoms for profile {prof_uuid}")

        # ------------------------------------------------------------------
        # Step 4: Profiler Agent (A1, V1)
        # ------------------------------------------------------------------
        atoms_payload: list[EvidenceAtom | dict[str, Any]] = list(atoms)
        profiler_output = await run_profiler_agent(
            profile_id=prof_uuid,
            atoms=atoms_payload,
            client=self.client,
            tenant_id=ten_uuid,
            raw_title=raw_title,
            ontology=self.ontology,
        )
        if profiler_output.flags:
            pipeline_flags.extend(profiler_output.flags)

        # ------------------------------------------------------------------
        # Step 5: Database Persistence (optional)
        # ------------------------------------------------------------------
        if save_to_db:
            if conn is not None:
                await self._persist_profiling_artifacts(
                    conn=conn,
                    tenant_id=ten_uuid,
                    profile_id=prof_uuid,
                    document_id=doc_uuid,
                    offset_map=offset_map,
                    atoms=atoms,
                    profiler_output=profiler_output,
                )
            else:
                async with get_connection() as managed_conn:
                    await self._persist_profiling_artifacts(
                        conn=managed_conn,
                        tenant_id=ten_uuid,
                        profile_id=prof_uuid,
                        document_id=doc_uuid,
                        offset_map=offset_map,
                        atoms=atoms,
                        profiler_output=profiler_output,
                    )

        combined_flags = sorted(list(set(pipeline_flags)))
        return ProfilingResult(
            profile_id=prof_uuid,
            atoms=atoms,
            profiler_output=profiler_output,
            offset_map=offset_map,
            visibility_result=vis_result,
            flags=combined_flags,
            raw_text=raw_text,
            redacted_text=redacted_text,
            document_id=doc_uuid,
            tenant_id=ten_uuid,
        )

    async def _persist_profiling_artifacts(
        self,
        conn: Any,
        tenant_id: uuid.UUID,
        profile_id: uuid.UUID,
        document_id: uuid.UUID | None,
        offset_map: OffsetMap,
        atoms: list[EvidenceAtom],
        profiler_output: ProfilerOutput,
    ) -> None:
        """Persists offset map, evidence atoms, and profiler results in Postgres."""
        async with conn.cursor() as cur:
            # 1. Save redaction_offset_maps
            if document_id:
                seg_json = json.dumps(offset_map.to_json())
                await cur.execute(
                    """
                    INSERT INTO redaction_offset_maps (document_id, tenant_id, segments)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        segments = EXCLUDED.segments,
                        tenant_id = EXCLUDED.tenant_id;
                    """,
                    (document_id, tenant_id, seg_json),
                )

            # 2. Save evidence_atoms
            for atom in atoms:
                aid = getattr(atom, "id", None) or uuid.uuid4()
                bbox_json = json.dumps(atom.bbox) if atom.bbox else None
                await cur.execute(
                    """
                    INSERT INTO evidence_atoms (
                        id, tenant_id, profile_id, atom_key, kind, visibility, entry_ref,
                        page, char_start, char_end, red_start, red_end, bbox, text_redacted
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (profile_id, atom_key) DO UPDATE SET
                        kind = EXCLUDED.kind,
                        visibility = EXCLUDED.visibility,
                        entry_ref = EXCLUDED.entry_ref,
                        page = EXCLUDED.page,
                        char_start = EXCLUDED.char_start,
                        char_end = EXCLUDED.char_end,
                        red_start = EXCLUDED.red_start,
                        red_end = EXCLUDED.red_end,
                        bbox = EXCLUDED.bbox,
                        text_redacted = EXCLUDED.text_redacted
                    RETURNING id;
                    """,
                    (
                        aid,
                        tenant_id,
                        profile_id,
                        atom.atom_key,
                        atom.kind,
                        atom.visibility,
                        atom.entry_ref,
                        atom.page,
                        atom.char_start,
                        atom.char_end,
                        atom.red_start,
                        atom.red_end,
                        bbox_json,
                        atom.text_redacted,
                    ),
                )
                row = await cur.fetchone()
                if row and "id" in row:
                    atom.id = row["id"]

            await conn.commit()

        # 3. Save profiler output (experiences, allocations, atom_tags)
        atoms_to_save: list[EvidenceAtom | dict[str, Any]] = list(atoms)
        await save_profiler_results(
            conn=conn,
            profile_id=profile_id,
            output=profiler_output,
            atoms=atoms_to_save,
            ontology_version=self.ontology.version,
        )
        await conn.commit()


async def run_profiling_pipeline(
    profile_id: uuid.UUID | str,
    raw_text: str = "",
    pdf_spans: list[dict[str, Any]] | Any = None,
    candidate_profile: dict[str, Any] | None = None,
    pii_spans: list[tuple[int, int, str]] | None = None,
    document_id: uuid.UUID | str | None = None,
    tenant_id: uuid.UUID | str | None = None,
    raw_title: str | None = None,
    client: Any = None,
    ontology: OntologyGraph | None = None,
    save_to_db: bool = False,
    conn: Any = None,
) -> ProfilingResult:
    """Convenience helper function to invoke Graph A ProfilingPipeline."""
    pipeline = ProfilingPipeline(client=client, ontology=ontology)
    return await pipeline.run(
        profile_id=profile_id,
        raw_text=raw_text,
        pdf_spans=pdf_spans,
        candidate_profile=candidate_profile,
        pii_spans=pii_spans,
        document_id=document_id,
        tenant_id=tenant_id,
        raw_title=raw_title,
        save_to_db=save_to_db,
        conn=conn,
    )
