"""add_eligibility_gate_tables

Revision ID: 0004_eligibility_gate
Revises: 0003_jobs_queue_retry
Create Date: 2026-10-14 12:01:29.687295

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_eligibility_gate'
down_revision: Union[str, Sequence[str], None] = '0003_jobs_queue_retry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS eligibility_rules (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL,
            job_id        uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            category      text NOT NULL CHECK (category IN ('AGE', 'GENDER')),
            rule_type     text NOT NULL CHECK (rule_type IN ('MAX_AGE', 'MIN_AGE', 'AGE_RANGE', 'EXACT_GENDER')),
            parameters    jsonb NOT NULL,
            justification text NOT NULL,
            is_active     boolean NOT NULL DEFAULT false,
            approved_by   uuid REFERENCES users(id),
            approved_at   timestamptz,
            created_by    uuid NOT NULL REFERENCES users(id),
            created_at    timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS candidate_eligibility (
            run_id         uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id   uuid NOT NULL REFERENCES candidates(id),
            rule_id        uuid NOT NULL REFERENCES eligibility_rules(id) ON DELETE CASCADE,
            tenant_id      uuid NOT NULL,
            status         text NOT NULL CHECK (status IN ('ELIGIBLE', 'NOT_ELIGIBLE', 'UNKNOWN')),
            reason         text,
            reference_date date NOT NULL,
            PRIMARY KEY (run_id, candidate_id, rule_id)
        );
        CREATE INDEX IF NOT EXISTS idx_candidate_eligibility_run ON candidate_eligibility (run_id, candidate_id);
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DROP TABLE IF EXISTS candidate_eligibility CASCADE;")
    conn.exec_driver_sql("DROP TABLE IF EXISTS eligibility_rules CASCADE;")
