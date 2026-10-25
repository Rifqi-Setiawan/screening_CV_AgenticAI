"""requirements_embedding

Revision ID: 0009_requirements_embedding
Revises: 0008_screening_runs_progress
Create Date: 2026-10-14 16:12:02.391650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_requirements_embedding"
down_revision: Union[str, Sequence[str], None] = "0008_screening_runs_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE requirements
        ADD COLUMN IF NOT EXISTS embedding vector(640);
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE requirements DROP COLUMN IF EXISTS embedding;")
