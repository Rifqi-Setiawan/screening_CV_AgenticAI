"""recruiter_assist

Interview answers (rated by the recruiter, stored as interview atoms) and the Copilot HR query audit trail.

Revision ID: 0014_recruiter_assist
Revises: 0013_critic_reviews
Create Date: 2026-10-30 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_recruiter_assist"
down_revision: str | Sequence[str] | None = "0013_critic_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_answers (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL,
            run_id        uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id  uuid NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            facet_key     text NOT NULL,
            probe_id      text,
            rating        text NOT NULL CHECK (rating IN ('STRONG', 'ADEQUATE', 'WEAK')),
            depth_level   text,
            answer_text   text NOT NULL DEFAULT '',
            recorded_by   uuid,
            created_at    timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_interview_answers_run_cand ON interview_answers (run_id, candidate_id);

        CREATE TABLE IF NOT EXISTS copilot_audit_log (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL,
            user_id     uuid,
            run_id      uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            tool        text NOT NULL,
            args        jsonb NOT NULL DEFAULT '{}',
            allowed     boolean NOT NULL,
            reason      text,
            created_at  timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_copilot_audit_run ON copilot_audit_log (run_id, created_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS copilot_audit_log;
        DROP TABLE IF EXISTS interview_answers;
        """
    )
