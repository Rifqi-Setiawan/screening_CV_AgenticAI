import os
import subprocess
from urllib.parse import urlparse

import psycopg


def test_reset_dev_db_script_refuses_without_confirm():
    res = subprocess.run(
        ["bash", "scripts/reset_dev_db.sh"],
        capture_output=True,
        text=True,
        env={**os.environ, "CONFIRM_RESET": "no"},
    )
    assert res.returncode == 1
    assert "Ditolak: script ini MENGHAPUS database" in res.stdout or "Ditolak" in res.stderr


def test_alembic_upgrade_downgrade_cycle_on_isolated_db():
    base_test_url = os.environ.get("TEST_DATABASE_URL")
    if not base_test_url:
        base_test_url = "postgresql://cv_screening_user:password@127.0.0.1:5432/cv_screening_test"

    parsed = urlparse(base_test_url)
    m_url = parsed._replace(path="/postgres").geturl()

    temp_db_name = "cv_screening_mig_cycle_test"
    temp_db_url = parsed._replace(path=f"/{temp_db_name}").geturl()

    # 1. Create a clean isolated database
    with psycopg.connect(m_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {temp_db_name}")
        cur.execute(f"CREATE DATABASE {temp_db_name} OWNER {parsed.username}")

    try:
        env = {**os.environ, "DATABASE_URL": temp_db_url, "APP_ENV": "test"}

        # 2. Upgrade head
        res_up1 = subprocess.run(
            [".venv/bin/alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_up1.returncode == 0, f"Alembic upgrade 1 failed:\n{res_up1.stderr}"

        # Verify candidate_code_seq exists and nextval works (R-04)
        with psycopg.connect(temp_db_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT nextval('candidate_code_seq')")
            seq_val = cur.fetchone()[0]
            assert seq_val >= 1

        # 3. Downgrade base (R-04)
        res_down = subprocess.run(
            [".venv/bin/alembic", "downgrade", "base"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_down.returncode == 0, f"Alembic downgrade failed:\n{res_down.stderr}"

        # 4. Upgrade head again (R-04)
        res_up2 = subprocess.run(
            [".venv/bin/alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_up2.returncode == 0, f"Alembic upgrade 2 failed:\n{res_up2.stderr}"

        # Verify tables exist
        with psycopg.connect(temp_db_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = {r[0] for r in cur.fetchall()}
            assert "jobs" in tables
            assert "candidates" in tables
            assert "requirement_sets" in tables
            assert "requirements" in tables
            assert "alembic_version" in tables

    finally:
        # Cleanup isolated test DB
        with psycopg.connect(m_url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {temp_db_name}")
