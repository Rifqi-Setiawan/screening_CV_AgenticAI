"""screening_runs_progress

Revision ID: 0008_screening_runs_progress
Revises: 0007_eligibility_v2
Create Date: 2026-10-14 15:59:15.019933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_screening_runs_progress"
down_revision: Union[str, Sequence[str], None] = "0007_eligibility_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE screening_runs
        ADD COLUMN IF NOT EXISTS progress jsonb NOT NULL DEFAULT '{"done": 0, "total": 0}'::jsonb;
        ALTER TABLE screening_runs DROP CONSTRAINT IF EXISTS screening_runs_status_check;
        ALTER TABLE screening_runs ADD CONSTRAINT screening_runs_status_check CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'COMPLETED', 'FAILED'));
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE screening_runs DROP COLUMN IF EXISTS progress;")
