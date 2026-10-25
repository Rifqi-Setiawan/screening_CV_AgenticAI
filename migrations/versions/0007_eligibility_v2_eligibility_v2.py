"""eligibility_v2

Revision ID: 0007_eligibility_v2
Revises: 0006_candidate_code_seq
Create Date: 2026-10-14 14:55:40.794975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_eligibility_v2"
down_revision: Union[str, Sequence[str], None] = "0006_candidate_code_seq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing eligibility tables if present to reconstruct to spec
    op.execute("DROP TABLE IF EXISTS candidate_eligibility CASCADE;")
    op.execute("DROP TABLE IF EXISTS eligibility_rules CASCADE;")

    # 2. Create eligibility_rules with exact spec
    op.execute(
        """
        CREATE TABLE eligibility_rules (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        uuid NOT NULL,
            job_id           uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            rule_type        text NOT NULL CHECK (rule_type IN ('AGE_MAX','AGE_MIN','GENDER')),
            value            jsonb NOT NULL,
            basis_category   text NOT NULL CHECK (basis_category IN (
                               'KARAKTERISTIK_JABATAN',
                               'REGULASI_SEKTOR',
                               'PROGRAM_KHUSUS',
                               'LAINNYA')),
            justification    text NOT NULL CHECK (char_length(justification) >= 30),
            reference_date   date NOT NULL,
            status           text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','REVOKED')),
            created_by       uuid NOT NULL REFERENCES users(id),
            created_at       timestamptz NOT NULL DEFAULT now(),
            approved_by      uuid REFERENCES users(id),
            approved_at      timestamptz,
            revoked_by       uuid REFERENCES users(id),
            revoked_at       timestamptz,
            revoke_reason    text,
            CHECK (status <> 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
            CHECK (status <> 'REVOKED'  OR (revoked_by  IS NOT NULL AND revoke_reason IS NOT NULL))
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX eligibility_rules_one_active
            ON eligibility_rules (job_id, rule_type) WHERE status IN ('DRAFT','APPROVED');
        CREATE INDEX idx_eligibility_rules_tenant_job ON eligibility_rules (tenant_id, job_id);
        """
    )

    # 3. Create candidate_eligibility with exact spec
    op.execute(
        """
        CREATE TABLE candidate_eligibility (
            run_id          uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id    uuid NOT NULL REFERENCES candidates(id),
            tenant_id       uuid NOT NULL,
            document_id     uuid NOT NULL REFERENCES documents(id),
            overall_status  text NOT NULL CHECK (overall_status IN ('ELIGIBLE','NOT_ELIGIBLE','UNKNOWN','NOT_APPLICABLE')),
            details         jsonb NOT NULL DEFAULT '[]',
            evaluated_at    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, candidate_id)
        );
        CREATE INDEX idx_candidate_eligibility_tenant_run ON candidate_eligibility (tenant_id, run_id, overall_status);
        """
    )

    # 4. Add eligibility_snapshot to screening_runs
    op.execute(
        """
        ALTER TABLE screening_runs ADD COLUMN IF NOT EXISTS eligibility_snapshot jsonb NOT NULL DEFAULT '[]';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS candidate_eligibility CASCADE;")
    op.execute("DROP TABLE IF EXISTS eligibility_rules CASCADE;")
    op.execute("ALTER TABLE screening_runs DROP COLUMN IF EXISTS eligibility_snapshot;")
