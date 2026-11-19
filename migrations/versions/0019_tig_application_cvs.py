"""Keep the applicant's original CV file (encrypted with pgcrypto) so recruiters can open it from the applicant detail page."""

from alembic import op

revision = "0019_tig_application_cvs"
down_revision = "0018_recruiter_only_staff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tig_application_cvs (
            application_id uuid PRIMARY KEY REFERENCES tig_applications(id) ON DELETE CASCADE,
            filename text NOT NULL,
            content_type text NOT NULL,
            size_bytes integer NOT NULL CHECK (size_bytes > 0),
            content bytea NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE tig_application_cvs")
