"""add_max_attempts_to_jobs_queue

Revision ID: 0003_jobs_queue_retry
Revises: 0002_full_text_redacted
Create Date: 2026-10-14 11:39:34.159206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_jobs_queue_retry'
down_revision: Union[str, Sequence[str], None] = '0002_full_text_redacted'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE jobs_queue ADD COLUMN IF NOT EXISTS max_attempts int NOT NULL DEFAULT 3;")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE jobs_queue DROP COLUMN IF EXISTS max_attempts;")
