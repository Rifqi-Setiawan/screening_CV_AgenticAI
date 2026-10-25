"""evidence_atoms_and_offset_maps

Revision ID: 0010_evidence_atoms_and_offset_maps
Revises: 0009_requirements_embedding
Create Date: 2026-10-25 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_evidence_atoms_offset_maps"
down_revision: str | Sequence[str] | None = "0009_requirements_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS redaction_offset_maps (
            document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
            tenant_id   uuid NOT NULL,
            segments    jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at  timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_redaction_offset_maps_tenant
            ON redaction_offset_maps (tenant_id);

        CREATE TABLE IF NOT EXISTS evidence_atoms (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL,
            profile_id    uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
            atom_key      text NOT NULL,
            kind          text NOT NULL,
            visibility    text NOT NULL DEFAULT 'VISIBLE' CHECK (visibility IN ('VISIBLE', 'HIDDEN', 'SUSPECT')),
            entry_ref     text,
            page          int NOT NULL DEFAULT 1,
            char_start    int NOT NULL DEFAULT 0,
            char_end      int NOT NULL DEFAULT 0,
            red_start     int NOT NULL DEFAULT 0,
            red_end       int NOT NULL DEFAULT 0,
            bbox          jsonb,
            text_redacted text NOT NULL,
            embedding     vector(640),
            fts           tsvector GENERATED ALWAYS AS (to_tsvector('simple', text_redacted)) STORED,
            created_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (profile_id, atom_key)
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_atoms_profile
            ON evidence_atoms (profile_id);

        CREATE INDEX IF NOT EXISTS idx_evidence_atoms_tenant
            ON evidence_atoms (tenant_id);

        CREATE INDEX IF NOT EXISTS idx_evidence_atoms_embedding
            ON evidence_atoms USING hnsw (embedding vector_cosine_ops);

        CREATE INDEX IF NOT EXISTS idx_evidence_atoms_fts
            ON evidence_atoms USING gin (fts);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS evidence_atoms;
        DROP TABLE IF EXISTS redaction_offset_maps;
        """
    )
