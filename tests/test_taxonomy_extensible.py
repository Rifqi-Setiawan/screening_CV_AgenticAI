import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from src.domain.kind_rules import eval_experience_duration
from src.domain.taxonomy import reset_taxonomy_cache
from src.infrastructure.config import settings


@pytest.fixture
def custom_taxonomy_dir():
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)
    # Copy existing taxonomy
    src_path = Path("config/taxonomy")
    for f in src_path.glob("*"):
        shutil.copy(f, temp_path / f.name)

    # Add new role family: custom_specialist
    rf_file = temp_path / "role_families.yaml"
    rf_data = yaml.safe_load(rf_file.read_text()) or {}
    rf_data["custom_specialist"] = {
        "titles": ["custom specialist", "spesialis kustom", "lead custom specialist"],
        "domain_terms": ["kustom", "custom", "bespoke"],
        "related": [],
    }
    rf_file.write_text(yaml.dump(rf_data))

    old_dir = settings.TAXONOMY_DIR
    settings.TAXONOMY_DIR = str(temp_path)
    reset_taxonomy_cache()

    yield str(temp_path)

    settings.TAXONOMY_DIR = old_dir
    reset_taxonomy_cache()
    shutil.rmtree(temp_dir)


def test_extensible_role_via_yaml_only(custom_taxonomy_dir):
    profile = {
        "experiences": [
            {
                "title": "Lead Custom Specialist",
                "organization": "PT Bespoke Solutions",
                "start": "2020-01",
                "end": "2024-01",
                "bullets": [{"text": "Mengembangkan solusi bespoke kustom"}],
            }
        ]
    }
    req = {
        "requirement_id": "R1",
        "description": "Minimal 3 tahun pengalaman sebagai custom specialist",
        "kind": "EXPERIENCE_DURATION",
        "params": {"min_months": 36},
    }

    state, conf, metrics, evs, flags = eval_experience_duration(profile, req, as_of="2026-10-14")
    assert state == "STRONG"
    assert any("Lead Custom Specialist" in e["quote"] for e in evs)
