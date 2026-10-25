from datetime import date

from src.domain.eligibility import normalize_gender, parse_dob
from src.worker.redaction import extract_identity_and_redact, redact_text


def test_parse_dob_formats():
    # Indonesian format with place prefix
    res1 = parse_dob("Jakarta, 12 Maret 1999")
    assert res1["precision"] == "DAY"
    assert res1["value"] == date(1999, 3, 12)

    # Abbreviated Indonesian month
    res2 = parse_dob("12 Mar 1999")
    assert res2["precision"] == "DAY"
    assert res2["value"] == date(1999, 3, 12)

    # English textual date
    res3 = parse_dob("March 12, 1999")
    assert res3["precision"] == "DAY"
    assert res3["value"] == date(1999, 3, 12)

    # DD/MM/YYYY slash
    res4 = parse_dob("12/03/1999")
    assert res4["precision"] == "DAY"
    assert res4["value"] == date(1999, 3, 12)

    # ISO YYYY-MM-DD
    res5 = parse_dob("1999-03-12")
    assert res5["precision"] == "DAY"
    assert res5["value"] == date(1999, 3, 12)

    # Year only
    res6 = parse_dob("1999")
    assert res6["precision"] == "YEAR"
    assert res6["value"] == 1999

    # Place without date
    res7 = parse_dob("lahir di Bandung")
    assert res7["precision"] is None
    assert res7["value"] is None

    # Future date (implausible)
    res8 = parse_dob("12/03/2030")
    assert res8["precision"] is None
    assert "DOB_IMPLAUSIBLE" in res8["flags"]


def test_normalize_gender():
    assert normalize_gender("Laki-laki") == "M"
    assert normalize_gender("PRIA") == "M"
    assert normalize_gender("Male") == "M"
    assert normalize_gender("P") == "F"
    assert normalize_gender("Wanita") == "F"
    assert normalize_gender("-") is None
    assert normalize_gender("") is None
    assert normalize_gender(None) is None


def test_invariant_I2_full_text_redacted_and_chunks_zero_demographics():
    raw_cv = """Muhammad Rifqi
Email: rifqi@example.com
Phone: +628123456789
TTL: Jakarta, 12 Maret 1999
Jenis Kelamin: Perempuan
Tempat, tanggal lahir: Bandung, 1 Mei 2000
DOB: 1999-03-12

Ringkasan:
Backend Engineer dengan pengalaman 3 tahun di FastAPI dan PostgreSQL.
"""
    redacted = redact_text(raw_cv)
    assert "1999" not in redacted
    assert "2000" not in redacted
    assert "Maret" not in redacted
    assert "Mei" not in redacted
    assert "Perempuan" not in redacted
    assert "TTL" not in redacted
    assert "DOB" not in redacted
    assert "Tempat," not in redacted

    raw_profile = {
        "identity": {
            "full_name": "Muhammad Rifqi",
            "email": "rifqi@example.com",
            "phone": "+628123456789",
            "other_personal": {"dob": "1999-03-12", "gender": "Perempuan"},
        },
        "summary": "TTL: Jakarta, 12 Maret 1999. Pengalaman 3 tahun di Backend.",
        "skills": [{"name": "Python"}, {"name": "FastAPI"}],
        "experiences": [
            {
                "title": "Backend Developer",
                "org": "PT Tech",
                "bullets": [{"text": "TTL: Jakarta, 12 Maret 1999. Membangun API."}],
            }
        ],
        "educations": [],
    }

    identity_rec, matching_profile, chunks = extract_identity_and_redact(raw_profile)
    # Check matching_profile
    matching_str = str(matching_profile)
    assert "1999" not in matching_str
    assert "Perempuan" not in matching_str
    assert "TTL" not in matching_str

    # Check chunks
    for ch in chunks:
        ch_str = str(ch)
        assert "1999" not in ch_str
        assert "Perempuan" not in ch_str
        assert "TTL" not in ch_str


def test_invariant_I5_no_gender_guessing_from_name():
    raw_profile = {
        "identity": {
            "full_name": "Siti Aminah",
            "email": "siti@example.com",
            "phone": "+628123456789",
        },
        "summary": "Software Engineer berpengalaman.",
        "skills": [],
        "experiences": [],
        "educations": [],
    }
    identity_rec, _, _ = extract_identity_and_redact(raw_profile)
    assert normalize_gender(identity_rec.get("other_personal", {}).get("gender")) is None
