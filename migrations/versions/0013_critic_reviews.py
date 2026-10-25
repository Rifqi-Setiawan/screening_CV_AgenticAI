"""critic_reviews

Revision ID: 0013_critic_reviews
Revises: 0012_req_facets_judgments
Create Date: 2026-10-25 19:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_critic_reviews"
down_revision: str | Sequence[str] | None = "0012_req_facets_judgments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS critic_reviews (
            run_id           uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id     uuid NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            facet_key        text NOT NULL,
            tenant_id        uuid NOT NULL,
            verdict_action   text NOT NULL,
            final_verdict    text NOT NULL,
            original_verdict text,
            depth_level      text,
            analysis         text NOT NULL,
            reasoning        text,
            support_atoms    text[] NOT NULL DEFAULT '{}',
            is_disagreement  boolean NOT NULL DEFAULT false,
            flags            text[] NOT NULL DEFAULT '{}',
            created_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, candidate_id, facet_key)
        );
        CREATE INDEX IF NOT EXISTS idx_critic_reviews_run_cand ON critic_reviews (run_id, candidate_id);
        CREATE INDEX IF NOT EXISTS idx_critic_reviews_tenant ON critic_reviews (tenant_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS critic_reviews;
        """
    )
