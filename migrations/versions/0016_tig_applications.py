"""Store applicant-submitted forms and queue-backed TIG assessments."""

from alembic import op

revision = "0016_tig_applications"
down_revision = "0015_facet_support_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
        CREATE TABLE tig_configs (
            job_id uuid PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            config jsonb NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE tig_applications (
            id uuid PRIMARY KEY,
            job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            form bytea NOT NULL,
            stage text NOT NULL DEFAULT 'Seleksi'
                CHECK (stage IN ('Seleksi', 'Asesmen', 'Interview', 'SPK', 'Ditolak')),
            assessment_config jsonb NOT NULL,
            queue_id bigint NOT NULL REFERENCES jobs_queue(id),
            assessment jsonb,
            assessed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX tig_applications_job_id_idx ON tig_applications (job_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE tig_applications")
    op.execute("DROP TABLE tig_configs")
