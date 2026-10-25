import pytest

from src.domain.jd_compiler import compile_job_requirements


@pytest.mark.asyncio
async def test_jd_compilation_with_hr_contacts_succeeds():
    jd_with_contacts = """
    # Lowongan Backend Engineer
    Kualifikasi:
    - Minimal 3 tahun pengalaman dengan Python dan PostgreSQL
    - Menguasai Docker dan REST API
    
    Kirimkan CV dan portofolio Anda ke hr@perusahaan.com atau hubungi WA HR: 081234567890.
    """
    res = await compile_job_requirements(jd_with_contacts)
    assert res is not None
    assert "requirements" in res
    assert len(res["requirements"]) > 0
    # Prohibited flags should not complain about HR contact
    assert not any("PROHIBITED" in f for f in res.get("prohibited_flags", []))
