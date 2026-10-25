"""add_candidate_code_seq

Revision ID: 0006_candidate_code_seq
Revises: 0005_candidate_scores_coverage
Create Date: 2026-10-14 14:35:38.747739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_candidate_code_seq'
down_revision: Union[str, Sequence[str], None] = '0005_candidate_scores_coverage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("CREATE SEQUENCE IF NOT EXISTS candidate_code_seq;")
    conn.exec_driver_sql(
        """
        SELECT setval(
            'candidate_code_seq',
            COALESCE((SELECT MAX(substring(candidate_code from 3)::int) FROM candidates WHERE candidate_code ~ '^C-\\d+$'), 0) + 1,
            false
        );
        """
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DROP SEQUENCE IF EXISTS candidate_code_seq;")
