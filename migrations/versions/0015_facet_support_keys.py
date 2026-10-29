"""facet_support_keys

Keeps the link from a facet judgment to the evidence atoms that support it. The uuid[] column
`support_atom_ids` only accepted atom UUIDs, but the pipeline cites atoms by key (e.g. "E3.B4"), so every
supporting atom was silently dropped on save (0 of 95 judgments in the 19-CV run kept a link). The new
column stores the cited atom keys.

Revision ID: 0015_facet_support_keys
Revises: 0014_recruiter_assist
Create Date: 2026-10-30 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_facet_support_keys"
down_revision: str | Sequence[str] | None = "0014_recruiter_assist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE facet_judgments ADD COLUMN IF NOT EXISTS support_atom_keys text[] NOT NULL DEFAULT '{}';")


def downgrade() -> None:
    op.execute("ALTER TABLE facet_judgments DROP COLUMN IF EXISTS support_atom_keys;")
