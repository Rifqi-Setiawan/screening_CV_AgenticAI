"""Evidence Atomizer and Redaction OffsetMap module (v2.1).

Implements Grounding by Construction:
- Maps character positions between raw document text and redacted text.
- Atomizes candidate profiles into fine-grained, deterministically addressed evidence atoms.
- Rejects candidate atoms overlapping PII redactions or flagged as HIDDEN.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AtomKind(str, Enum):
    EXP_HEADER = "exp_header"
    EXP_BULLET = "exp_bullet"
    PROJECT_BULLET = "project_bullet"
    SUMMARY_SENTENCE = "summary_sentence"
    SKILL_LIST_ITEM = "skill_list_item"
    EDUCATION = "education"
    CERT = "cert"
    SELF_CLAIM = "self_claim"


@dataclass
class OffsetSegment:
    orig_start: int
    orig_end: int
    red_start: int
    red_end: int
    is_pii: bool = False
    replacement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "orig_start": self.orig_start,
            "orig_end": self.orig_end,
            "red_start": self.red_start,
            "red_end": self.red_end,
            "is_pii": self.is_pii,
            "replacement": self.replacement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OffsetSegment:
        return cls(
            orig_start=int(data["orig_start"]),
            orig_end=int(data["orig_end"]),
            red_start=int(data["red_start"]),
            red_end=int(data["red_end"]),
            is_pii=bool(data.get("is_pii", False)),
            replacement=str(data.get("replacement", "")),
        )


@dataclass
class OffsetMap:
    document_id: str | None = None
    tenant_id: str | None = None
    segments: list[OffsetSegment] = field(default_factory=list)

    def add_segment(
        self,
        orig_start: int,
        orig_end: int,
        red_start: int,
        red_end: int,
        is_pii: bool = False,
        replacement: str = "",
    ) -> None:
        self.segments.append(
            OffsetSegment(
                orig_start=orig_start,
                orig_end=orig_end,
                red_start=red_start,
                red_end=red_end,
                is_pii=is_pii,
                replacement=replacement,
            )
        )

    def orig_to_red(self, orig_pos: int) -> int:
        if not self.segments:
            return orig_pos
        if orig_pos <= self.segments[0].orig_start:
            return self.segments[0].red_start
        if orig_pos >= self.segments[-1].orig_end:
            diff = orig_pos - self.segments[-1].orig_end
            return self.segments[-1].red_end + diff

        for i, seg in enumerate(self.segments):
            if seg.orig_start <= orig_pos < seg.orig_end:
                if seg.is_pii:
                    return seg.red_start
                delta = orig_pos - seg.orig_start
                return min(seg.red_start + delta, seg.red_end)
            if orig_pos == seg.orig_end and i == len(self.segments) - 1:
                return seg.red_end
        return orig_pos

    def red_to_orig(self, red_pos: int) -> int:
        if not self.segments:
            return red_pos
        if red_pos <= self.segments[0].red_start:
            return self.segments[0].orig_start
        if red_pos >= self.segments[-1].red_end:
            diff = red_pos - self.segments[-1].red_end
            return self.segments[-1].orig_end + diff

        for i, seg in enumerate(self.segments):
            if seg.red_start <= red_pos < seg.red_end:
                if seg.is_pii:
                    return seg.orig_start
                delta = red_pos - seg.red_start
                return min(seg.orig_start + delta, seg.orig_end)
            if red_pos == seg.red_end and i == len(self.segments) - 1:
                return seg.orig_end
        return red_pos

    def orig_range_to_red(self, orig_start: int, orig_end: int) -> tuple[int, int]:
        return self.orig_to_red(orig_start), self.orig_to_red(orig_end)

    def red_range_to_orig(self, red_start: int, red_end: int) -> tuple[int, int]:
        return self.red_to_orig(red_start), self.red_to_orig(red_end)

    def overlaps_pii(self, orig_start: int, orig_end: int) -> bool:
        for seg in self.segments:
            if seg.is_pii and max(orig_start, seg.orig_start) < min(orig_end, seg.orig_end):
                return True
        return False

    def to_json(self) -> list[dict[str, Any]]:
        return [s.to_dict() if isinstance(s, OffsetSegment) else s for s in self.segments]

    @classmethod
    def from_json(
        cls,
        segments_data: list[dict[str, Any]],
        document_id: str | None = None,
        tenant_id: str | None = None,
    ) -> OffsetMap:
        segments = [OffsetSegment.from_dict(s) if isinstance(s, dict) else s for s in segments_data]
        return cls(document_id=document_id, tenant_id=tenant_id, segments=segments)


def create_offset_map(
    raw_text: str,
    pii_spans: list[tuple[int, int, str]],
    document_id: str | None = None,
    tenant_id: str | None = None,
) -> tuple[str, OffsetMap]:
    """Builds redacted text and contiguous OffsetMap from raw text and PII spans.

    Args:
        raw_text: Original CV text.
        pii_spans: List of (orig_start, orig_end, replacement).
        document_id: Optional UUID/str of document.
        tenant_id: Optional UUID/str of tenant.

    Returns:
        tuple of (redacted_text, OffsetMap).
    """
    redacted_parts: list[str] = []
    segments: list[OffsetSegment] = []
    curr_orig = 0
    curr_red = 0

    sorted_spans = sorted(pii_spans, key=lambda x: (x[0], x[1]))

    for orig_start, orig_end, replacement in sorted_spans:
        if orig_start > curr_orig:
            chunk = raw_text[curr_orig:orig_start]
            redacted_parts.append(chunk)
            chunk_len = len(chunk)
            segments.append(
                OffsetSegment(
                    orig_start=curr_orig,
                    orig_end=orig_start,
                    red_start=curr_red,
                    red_end=curr_red + chunk_len,
                    is_pii=False,
                    replacement="",
                )
            )
            curr_red += chunk_len
            curr_orig = orig_start

        redacted_parts.append(replacement)
        rep_len = len(replacement)
        segments.append(
            OffsetSegment(
                orig_start=orig_start,
                orig_end=orig_end,
                red_start=curr_red,
                red_end=curr_red + rep_len,
                is_pii=True,
                replacement=replacement,
            )
        )
        curr_red += rep_len
        curr_orig = orig_end

    if curr_orig < len(raw_text):
        chunk = raw_text[curr_orig:]
        redacted_parts.append(chunk)
        chunk_len = len(chunk)
        segments.append(
            OffsetSegment(
                orig_start=curr_orig,
                orig_end=len(raw_text),
                red_start=curr_red,
                red_end=curr_red + chunk_len,
                is_pii=False,
                replacement="",
            )
        )

    redacted_text = "".join(redacted_parts)
    return redacted_text, OffsetMap(document_id=document_id, tenant_id=tenant_id, segments=segments)


@dataclass
class EvidenceAtom:
    atom_key: str
    kind: str
    entry_ref: str | None
    page: int
    char_start: int
    char_end: int
    red_start: int
    red_end: int
    text_redacted: str
    visibility: str = "VISIBLE"
    bbox: list[float] | None = None
    id: uuid.UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_key": self.atom_key,
            "kind": self.kind,
            "entry_ref": self.entry_ref,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "red_start": self.red_start,
            "red_end": self.red_end,
            "text_redacted": self.text_redacted,
            "visibility": self.visibility,
            "bbox": self.bbox,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceAtom:
        return cls(
            atom_key=str(data["atom_key"]),
            kind=str(data["kind"]),
            entry_ref=data.get("entry_ref"),
            page=int(data.get("page", 1)),
            char_start=int(data.get("char_start", 0)),
            char_end=int(data.get("char_end", 0)),
            red_start=int(data.get("red_start", 0)),
            red_end=int(data.get("red_end", 0)),
            text_redacted=str(data.get("text_redacted", "")),
            visibility=str(data.get("visibility", "VISIBLE")),
            bbox=data.get("bbox"),
        )


def _resolve_atom(
    atom_key: str,
    kind: str,
    entry_ref: str | None,
    item_text: str,
    source: dict[str, Any],
    raw_text: str,
    redacted_text: str,
    offset_map: OffsetMap | None,
    item_visibility: str | None = None,
) -> EvidenceAtom | None:
    """Validates and builds an EvidenceAtom. Returns None if invalid (PII overlap or HIDDEN)."""
    # 1. Check visibility
    visibility = item_visibility or source.get("visibility", "VISIBLE")
    if visibility == "HIDDEN":
        return None

    # 2. Extract or locate character offsets
    orig_start = source.get("char_start")
    orig_end = source.get("char_end")

    clean_text = item_text.strip()
    if (orig_start is None or orig_end is None or orig_end <= orig_start) and clean_text:
        # Search in raw_text first
        pos = raw_text.find(clean_text)
        if pos >= 0:
            orig_start = pos
            orig_end = pos + len(clean_text)
        elif redacted_text:
            # Search in redacted text and map back to raw_text
            pos_red = redacted_text.find(clean_text)
            if pos_red >= 0:
                red_len = len(clean_text)
                if offset_map:
                    orig_start = offset_map.red_to_orig(pos_red)
                    orig_end = offset_map.red_to_orig(pos_red + red_len)
                else:
                    orig_start = pos_red
                    orig_end = pos_red + red_len
            else:
                orig_start = 0
                orig_end = 0
        else:
            orig_start = 0
            orig_end = 0
    orig_start_val = int(orig_start) if orig_start is not None else 0
    orig_end_val = int(orig_end) if orig_end is not None else 0

    # 3. Reject if overlaps with PII
    if offset_map and orig_end_val > orig_start_val and offset_map.overlaps_pii(orig_start_val, orig_end_val):
        return None

    # 4. Compute redacted start and end
    if offset_map and orig_end_val > orig_start_val:
        red_start = offset_map.orig_to_red(orig_start_val)
        red_end = offset_map.orig_to_red(orig_end_val)
    elif orig_end_val > orig_start_val:
        red_start = orig_start_val
        red_end = orig_end_val
    else:
        red_start = 0
        red_end = 0

    # 5. Determine text_redacted
    if redacted_text and 0 <= red_start < red_end <= len(redacted_text):
        text_red = redacted_text[red_start:red_end].strip()
    else:
        text_red = clean_text

    page = int(source.get("page", 1))
    bbox = source.get("bbox")

    return EvidenceAtom(
        atom_key=atom_key,
        kind=kind,
        entry_ref=entry_ref,
        page=page,
        char_start=orig_start_val,
        char_end=orig_end_val,
        red_start=red_start,
        red_end=red_end,
        text_redacted=text_red,
        visibility=visibility,
        bbox=bbox,
    )


def atomize_candidate_profile(
    profile: dict[str, Any],
    raw_text: str = "",
    redacted_text: str = "",
    offset_map: OffsetMap | None = None,
) -> list[EvidenceAtom]:
    """Atomizes candidate profile into fine-grained EvidenceAtom objects.

    Rules:
    - Atom keys follow deterministic numbering:
      - Experience headers: E{idx}.HDR
      - Experience bullets: E{idx}.B{b_idx}
      - Project bullets: P{idx}.B{b_idx}
      - Summary sentences: SM{s_idx}
      - Skill list items: SK{s_idx}
      - Education entries: ED{e_idx}
      - Certifications: CR{c_idx}
    - Rejects atoms overlapping PII segments recorded in offset_map.
    - Rejects atoms where visibility is HIDDEN.
    - Guarantees uniqueness of all atom_keys.
    """
    atoms: list[EvidenceAtom] = []
    seen_keys: set[str] = set()

    def _register_atom(atom: EvidenceAtom | None) -> None:
        if atom is None:
            return
        key = atom.atom_key
        if key in seen_keys:
            # Disambiguate key if duplicate
            c = 2
            while f"{key}_{c}" in seen_keys:
                c += 1
            key = f"{key}_{c}"
            atom.atom_key = key
        seen_keys.add(key)
        atoms.append(atom)

    # 1. Experiences
    for exp_idx, exp in enumerate(profile.get("experiences", []), start=1):
        entry_ref = exp.get("entry_id") or f"exp_{exp_idx}"
        exp_vis = exp.get("visibility")

        # 1a. Experience Header
        title = exp.get("title", "").strip()
        org = exp.get("organization", "").strip()
        header_text = f"{title} di {org}".strip() if title and org else (title or org)
        if header_text:
            hdr_source = exp.get("source", {})
            atom = _resolve_atom(
                atom_key=f"E{exp_idx}.HDR",
                kind=AtomKind.EXP_HEADER.value,
                entry_ref=entry_ref,
                item_text=header_text,
                source=hdr_source,
                raw_text=raw_text,
                redacted_text=redacted_text,
                offset_map=offset_map,
                item_visibility=exp_vis,
            )
            _register_atom(atom)

        # 1b. Experience Bullets
        bullets = exp.get("bullets", [])
        for b_idx, b in enumerate(bullets, start=1):
            if isinstance(b, dict):
                b_text = b.get("text", "").strip()
                b_source = b.get("source", {})
                b_vis = b.get("visibility", exp_vis)
            else:
                b_text = str(b).strip()
                b_source = {}
                b_vis = exp_vis

            if not b_text:
                continue

            atom = _resolve_atom(
                atom_key=f"E{exp_idx}.B{b_idx}",
                kind=AtomKind.EXP_BULLET.value,
                entry_ref=entry_ref,
                item_text=b_text,
                source=b_source,
                raw_text=raw_text,
                redacted_text=redacted_text,
                offset_map=offset_map,
                item_visibility=b_vis,
            )
            _register_atom(atom)

    # 2. Projects
    for prj_idx, prj in enumerate(profile.get("projects", []), start=1):
        entry_ref = prj.get("entry_id") or f"prj_{prj_idx}"
        prj_vis = prj.get("visibility")
        prj_bullets = prj.get("bullets", [])

        if prj_bullets:
            for b_idx, b in enumerate(prj_bullets, start=1):
                if isinstance(b, dict):
                    b_text = b.get("text", "").strip()
                    b_source = b.get("source", {})
                    b_vis = b.get("visibility", prj_vis)
                else:
                    b_text = str(b).strip()
                    b_source = {}
                    b_vis = prj_vis

                if not b_text:
                    continue

                atom = _resolve_atom(
                    atom_key=f"P{prj_idx}.B{b_idx}",
                    kind=AtomKind.PROJECT_BULLET.value,
                    entry_ref=entry_ref,
                    item_text=b_text,
                    source=b_source,
                    raw_text=raw_text,
                    redacted_text=redacted_text,
                    offset_map=offset_map,
                    item_visibility=b_vis,
                )
                _register_atom(atom)
        else:
            prj_text = prj.get("text") or prj.get("title") or ""
            lines = [l.strip() for l in prj_text.splitlines() if l.strip()]
            if not lines and prj_text.strip():
                lines = [prj_text.strip()]

            for b_idx, line in enumerate(lines, start=1):
                atom = _resolve_atom(
                    atom_key=f"P{prj_idx}.B{b_idx}",
                    kind=AtomKind.PROJECT_BULLET.value,
                    entry_ref=entry_ref,
                    item_text=line,
                    source=prj.get("source", {}),
                    raw_text=raw_text,
                    redacted_text=redacted_text,
                    offset_map=offset_map,
                    item_visibility=prj_vis,
                )
                _register_atom(atom)

    # 3. Summary sentences
    summary_text = (profile.get("summary") or "").strip()
    if summary_text:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", summary_text) if s.strip()]
        for s_idx, sentence in enumerate(sentences, start=1):
            atom = _resolve_atom(
                atom_key=f"SM{s_idx}",
                kind=AtomKind.SUMMARY_SENTENCE.value,
                entry_ref="summary",
                item_text=sentence,
                source=profile.get("summary_source", {}),
                raw_text=raw_text,
                redacted_text=redacted_text,
                offset_map=offset_map,
                item_visibility=profile.get("summary_visibility"),
            )
            _register_atom(atom)

    # 4. Skills
    skills_list = profile.get("skills", [])
    for sk_idx, sk in enumerate(skills_list, start=1):
        if isinstance(sk, dict):
            sk_name = sk.get("name", "").strip()
            sk_source = sk.get("source", {})
            sk_vis = sk.get("visibility")
        else:
            sk_name = str(sk).strip()
            sk_source = {}
            sk_vis = None

        if not sk_name:
            continue

        atom = _resolve_atom(
            atom_key=f"SK{sk_idx}",
            kind=AtomKind.SKILL_LIST_ITEM.value,
            entry_ref="skills",
            item_text=sk_name,
            source=sk_source,
            raw_text=raw_text,
            redacted_text=redacted_text,
            offset_map=offset_map,
            item_visibility=sk_vis,
        )
        _register_atom(atom)

    # 5. Education
    for edu_idx, edu in enumerate(profile.get("education", []), start=1):
        entry_ref = edu.get("entry_id") or f"edu_{edu_idx}"
        edu_vis = edu.get("visibility")
        if isinstance(edu, dict):
            edu_text = f"{edu.get('level', '')} {edu.get('degree_raw', '')} {edu.get('institution', '')}".strip()
            if not edu_text:
                edu_text = edu.get("institution", "") or edu.get("text", "")
            edu_source = edu.get("source", {})
        else:
            edu_text = str(edu).strip()
            edu_source = {}

        if not edu_text:
            continue

        atom = _resolve_atom(
            atom_key=f"ED{edu_idx}",
            kind=AtomKind.EDUCATION.value,
            entry_ref=entry_ref,
            item_text=edu_text,
            source=edu_source,
            raw_text=raw_text,
            redacted_text=redacted_text,
            offset_map=offset_map,
            item_visibility=edu_vis,
        )
        _register_atom(atom)

    # 6. Certifications
    for cert_idx, cert in enumerate(profile.get("certifications", []), start=1):
        entry_ref = f"cert_{cert_idx}"
        if isinstance(cert, dict):
            cert_text = cert.get("name", "").strip()
            cert_source = cert.get("source", {})
            cert_vis = cert.get("visibility")
        else:
            cert_text = str(cert).strip()
            cert_source = {}
            cert_vis = None

        if not cert_text:
            continue

        atom = _resolve_atom(
            atom_key=f"CR{cert_idx}",
            kind=AtomKind.CERT.value,
            entry_ref=entry_ref,
            item_text=cert_text,
            source=cert_source,
            raw_text=raw_text,
            redacted_text=redacted_text,
            offset_map=offset_map,
            item_visibility=cert_vis,
        )
        _register_atom(atom)

    return atoms
