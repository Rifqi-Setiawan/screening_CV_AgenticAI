"""Unit tests for Evidence Atomizer and OffsetMap (C2 N1, N2).

Tests:
- OffsetMap character mapping (orig <-> red)
- OffsetMap JSON roundtrip serialization
- PII overlap detection
- atomize_candidate_profile parsing across all profile sections
- atom_key naming convention and uniqueness
- Rejection of atoms overlapping PII
- Rejection of atoms flagged as HIDDEN
"""

from __future__ import annotations

from src.domain.atoms import (
    AtomKind,
    EvidenceAtom,
    OffsetMap,
    OffsetSegment,
    atomize_candidate_profile,
    create_offset_map,
)


def test_evidence_atom_dict_roundtrip():
    atom = EvidenceAtom(
        atom_key="E1.B1",
        kind=AtomKind.EXP_BULLET.value,
        entry_ref="exp_1",
        page=1,
        char_start=10,
        char_end=50,
        red_start=10,
        red_end=50,
        text_redacted="Developed backend API",
        visibility="VISIBLE",
        bbox=[50.0, 100.0, 300.0, 120.0],
    )
    d = atom.to_dict()
    assert d["atom_key"] == "E1.B1"
    assert d["kind"] == "exp_bullet"
    assert d["bbox"] == [50.0, 100.0, 300.0, 120.0]

    restored = EvidenceAtom.from_dict(d)
    assert restored.atom_key == atom.atom_key
    assert restored.text_redacted == atom.text_redacted


def test_offset_map_basic_mapping():
    # raw_text: "Nama: Budi Santoso. Email: budi@gmail.com. Skill: Python, FastAPI."
    # PII spans:
    # 1. "Budi Santoso" at [6, 18) -> replaced with "[NAMA]" (len 6)
    # 2. "budi@gmail.com" at [27, 41) -> replaced with "[EMAIL]" (len 7)
    raw_text = "Nama: Budi Santoso. Email: budi@gmail.com. Skill: Python, FastAPI."
    pii_spans = [
        (6, 18, "[NAMA]"),
        (27, 41, "[EMAIL]"),
    ]
    red_text, omap = create_offset_map(raw_text, pii_spans, document_id="doc-123", tenant_id="tenant-456")

    assert red_text == "Nama: [NAMA]. Email: [EMAIL]. Skill: Python, FastAPI."
    assert omap.document_id == "doc-123"
    assert omap.tenant_id == "tenant-456"

    # Before first PII: "Nama: "
    assert omap.orig_to_red(0) == 0
    assert omap.orig_to_red(5) == 5
    assert omap.red_to_orig(0) == 0
    assert omap.red_to_orig(5) == 5

    # During first PII:
    assert omap.orig_to_red(6) == 6
    assert omap.orig_to_red(18) == 12  # "[NAMA]" ends at 6+6=12

    # After first PII, before second PII: ". Email: "
    # raw_text index 18 ('.') -> red_text index 12 ('.')
    assert omap.orig_to_red(18) == 12
    assert omap.red_to_orig(12) == 18

    # Skill section: "Skill: Python, FastAPI."
    # Starts at raw index 43 -> red index 30
    skill_raw_start = raw_text.find("Skill:")
    skill_red_start = red_text.find("Skill:")
    assert omap.orig_to_red(skill_raw_start) == skill_red_start
    assert omap.red_to_orig(skill_red_start) == skill_raw_start

    # Check PII overlap detection
    assert omap.overlaps_pii(6, 18) is True  # Exactly Budi Santoso
    assert omap.overlaps_pii(0, 10) is True  # Overlaps start of name
    assert omap.overlaps_pii(15, 20) is True  # Overlaps end of name
    assert omap.overlaps_pii(0, 6) is False  # "Nama: " strictly before
    assert omap.overlaps_pii(18, 27) is False  # ". Email: " between
    assert omap.overlaps_pii(skill_raw_start, len(raw_text)) is False  # Non-PII tail


def test_offset_map_json_roundtrip():
    omap = OffsetMap(
        document_id="doc-1",
        tenant_id="tenant-1",
        segments=[
            OffsetSegment(orig_start=0, orig_end=10, red_start=0, red_end=10, is_pii=False),
            OffsetSegment(orig_start=10, orig_end=25, red_start=10, red_end=16, is_pii=True, replacement="[NAMA]"),
            OffsetSegment(orig_start=25, orig_end=50, red_start=16, red_end=41, is_pii=False),
        ],
    )
    json_data = omap.to_json()
    assert len(json_data) == 3
    assert json_data[1]["is_pii"] is True
    assert json_data[1]["replacement"] == "[NAMA]"

    restored = OffsetMap.from_json(json_data, document_id="doc-1", tenant_id="tenant-1")
    assert restored.document_id == "doc-1"
    assert len(restored.segments) == 3
    assert restored.segments[1].orig_end == 25
    assert restored.segments[1].red_end == 16
    assert restored.segments[1].is_pii is True


def test_atomize_candidate_profile_full():
    raw_text = (
        "John Doe\n"
        "Ringkasan: Backend Engineer berpengalaman dengan arsitektur microservices.\n"
        "Pengalaman:\n"
        "Senior Backend Engineer di PT Maju Mundur\n"
        "- Membangun sistem transaksi berkecepatan tinggi dengan FastAPI.\n"
        "- Mengoptimalkan query PostgreSQL hingga 40% lebih cepat.\n"
        "Backend Developer di Startup XYZ\n"
        "- Mengembangkan integrasi payment gateway.\n"
        "Proyek:\n"
        "E-Commerce Payment Gateway\n"
        "- Desain event-driven architecture dengan Kafka.\n"
        "Keahlian: Python, PostgreSQL, Redis, Docker\n"
        "Pendidikan: S1 Teknik Informatika Universitas Indonesia\n"
        "Sertifikasi: AWS Certified Solutions Architect\n"
    )

    pii_spans = [(0, 8, "[NAMA]")]  # "John Doe" is PII
    redacted_text, omap = create_offset_map(raw_text, pii_spans)

    profile = {
        "summary": "Backend Engineer berpengalaman dengan arsitektur microservices.",
        "experiences": [
            {
                "entry_id": "exp_1",
                "title": "Senior Backend Engineer",
                "organization": "PT Maju Mundur",
                "bullets": [
                    {"text": "Membangun sistem transaksi berkecepatan tinggi dengan FastAPI."},
                    {"text": "Mengoptimalkan query PostgreSQL hingga 40% lebih cepat."},
                ],
            },
            {
                "entry_id": "exp_2",
                "title": "Backend Developer",
                "organization": "Startup XYZ",
                "bullets": [
                    {"text": "Mengembangkan integrasi payment gateway."},
                ],
            },
        ],
        "projects": [
            {
                "entry_id": "prj_1",
                "title": "E-Commerce Payment Gateway",
                "bullets": [
                    {"text": "Desain event-driven architecture dengan Kafka."},
                ],
            }
        ],
        "skills": ["Python", "PostgreSQL", "Redis", "Docker"],
        "education": [
            {
                "entry_id": "edu_1",
                "level": "S1",
                "degree_raw": "Teknik Informatika",
                "institution": "Universitas Indonesia",
            }
        ],
        "certifications": [{"name": "AWS Certified Solutions Architect"}],
    }

    atoms = atomize_candidate_profile(profile, raw_text=raw_text, redacted_text=redacted_text, offset_map=omap)
    atom_keys = [a.atom_key for a in atoms]

    # Verify atom key naming conventions
    assert "E1.HDR" in atom_keys
    assert "E1.B1" in atom_keys
    assert "E1.B2" in atom_keys
    assert "E2.HDR" in atom_keys
    assert "E2.B1" in atom_keys
    assert "P1.B1" in atom_keys
    assert "SM1" in atom_keys
    assert "SK1" in atom_keys
    assert "SK2" in atom_keys
    assert "SK3" in atom_keys
    assert "SK4" in atom_keys
    assert "ED1" in atom_keys
    assert "CR1" in atom_keys

    # Verify uniqueness of all atom keys
    assert len(atom_keys) == len(set(atom_keys))

    # Verify atom kinds
    kind_map = {a.atom_key: a.kind for a in atoms}
    assert kind_map["E1.HDR"] == AtomKind.EXP_HEADER.value
    assert kind_map["E1.B1"] == AtomKind.EXP_BULLET.value
    assert kind_map["P1.B1"] == AtomKind.PROJECT_BULLET.value
    assert kind_map["SM1"] == AtomKind.SUMMARY_SENTENCE.value
    assert kind_map["SK1"] == AtomKind.SKILL_LIST_ITEM.value
    assert kind_map["ED1"] == AtomKind.EDUCATION.value
    assert kind_map["CR1"] == AtomKind.CERT.value

    # Verify character offsets for a matched bullet
    e1_b1 = next(a for a in atoms if a.atom_key == "E1.B1")
    assert e1_b1.char_start > 0
    assert e1_b1.char_end > e1_b1.char_start
    assert (
        raw_text[e1_b1.char_start : e1_b1.char_end] == "Membangun sistem transaksi berkecepatan tinggi dengan FastAPI."
    )
    assert (
        redacted_text[e1_b1.red_start : e1_b1.red_end]
        == "Membangun sistem transaksi berkecepatan tinggi dengan FastAPI."
    )
    assert e1_b1.visibility == "VISIBLE"


def test_atomize_rejects_pii_overlapping_atom():
    raw_text = "John Doe is a Senior Architect."
    # Mark "John Doe" as PII
    pii_spans = [(0, 8, "[NAMA]")]
    redacted_text, omap = create_offset_map(raw_text, pii_spans)

    profile = {
        "experiences": [
            {
                "entry_id": "exp_1",
                # Title overlaps with PII span [0, 8)
                "title": "John Doe",
                "organization": "",
                "source": {"char_start": 0, "char_end": 8},
                "bullets": [],
            },
            {
                "entry_id": "exp_2",
                # Valid non-PII title
                "title": "Senior Architect",
                "organization": "",
                "source": {"char_start": 14, "char_end": 30},
                "bullets": [],
            },
        ]
    }

    atoms = atomize_candidate_profile(profile, raw_text=raw_text, redacted_text=redacted_text, offset_map=omap)
    atom_keys = [a.atom_key for a in atoms]

    # Atom for exp_1 (John Doe) must be rejected because it overlaps PII
    assert "E1.HDR" not in atom_keys
    # Atom for exp_2 (Senior Architect) must be accepted
    assert "E2.HDR" in atom_keys


def test_atomize_rejects_hidden_text_atom():
    raw_text = "Experience:\n- Normal visible bullet\n- Hidden keyword stuffing"
    profile = {
        "experiences": [
            {
                "entry_id": "exp_1",
                "title": "Developer",
                "organization": "Company",
                "bullets": [
                    {
                        "text": "Normal visible bullet",
                        "visibility": "VISIBLE",
                    },
                    {
                        "text": "Hidden keyword stuffing",
                        "visibility": "HIDDEN",  # Flagged by Visibility Gate
                    },
                    {
                        "text": "Borderline font bullet",
                        "visibility": "SUSPECT",  # Suspect is allowed with suspect tag
                    },
                ],
            }
        ]
    }

    atoms = atomize_candidate_profile(profile, raw_text=raw_text, redacted_text=raw_text)
    texts = [a.text_redacted for a in atoms]

    # Normal visible bullet must be present
    assert any("Normal visible bullet" in t for t in texts)
    # Hidden keyword stuffing must be strictly rejected
    assert not any("Hidden keyword stuffing" in t for t in texts)
    # Suspect bullet is included with visibility="SUSPECT"
    suspect_atom = next(a for a in atoms if "Borderline font bullet" in a.text_redacted)
    assert suspect_atom.visibility == "SUSPECT"
