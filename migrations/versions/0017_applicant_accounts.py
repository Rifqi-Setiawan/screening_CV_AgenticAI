"""Applicant accounts, one application per applicant and job, and assessment history for rescoring."""

from alembic import op

revision = "0017_applicant_accounts"
down_revision = "0016_tig_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE applicants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text NOT NULL,
            password_hash text NOT NULL,
            full_name text NOT NULL,
            consent_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE UNIQUE INDEX applicants_email_uniq ON applicants (lower(email))")
    op.execute("ALTER TABLE tig_applications ADD COLUMN applicant_id uuid REFERENCES applicants(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE tig_applications ADD COLUMN assessment_history jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("""
        CREATE UNIQUE INDEX tig_applications_job_applicant_uniq
        ON tig_applications (job_id, applicant_id) WHERE applicant_id IS NOT NULL
    """)
    op.execute("CREATE INDEX tig_applications_applicant_idx ON tig_applications (applicant_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX tig_applications_applicant_idx")
    op.execute("DROP INDEX tig_applications_job_applicant_uniq")
    op.execute("ALTER TABLE tig_applications DROP COLUMN assessment_history")
    op.execute("ALTER TABLE tig_applications DROP COLUMN applicant_id")
    op.execute("DROP TABLE applicants")
