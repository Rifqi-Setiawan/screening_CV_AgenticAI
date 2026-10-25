"""add_full_text_redacted_to_candidate_profiles

Revision ID: 0002_full_text_redacted
Revises: 0001_baseline
Create Date: 2026-10-14 11:35:48.626990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_full_text_redacted'
down_revision: Union[str, Sequence[str], None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE candidate_profiles ADD COLUMN IF NOT EXISTS full_text_redacted text;")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE candidate_profiles DROP COLUMN IF EXISTS full_text_redacted;")
