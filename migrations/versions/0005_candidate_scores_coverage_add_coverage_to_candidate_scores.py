"""add_coverage_to_candidate_scores

Revision ID: 0005_candidate_scores_coverage
Revises: 0004_eligibility_gate
Create Date: 2026-10-14 12:07:46.750793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_candidate_scores_coverage'
down_revision: Union[str, Sequence[str], None] = '0004_eligibility_gate'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE candidate_scores ADD COLUMN IF NOT EXISTS coverage numeric DEFAULT 1.0;")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE candidate_scores DROP COLUMN IF EXISTS coverage;")
