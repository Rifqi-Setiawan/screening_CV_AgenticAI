"""ontology_and_profiler_tables

Revision ID: 0011_ontology_and_profiler_tables
Revises: 0010_evidence_atoms_offset_maps
Create Date: 2026-10-25 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_ontology_profiler_tables"
down_revision: str | Sequence[str] | None = "0010_evidence_atoms_offset_maps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        -- 1. Experience entries table
        CREATE TABLE IF NOT EXISTS experience_entries (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_id       uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
            entry_ref        text NOT NULL,
            header_atom_id   uuid REFERENCES evidence_atoms(id) ON DELETE SET NULL,
            title_raw        text,
            employment_type  text,
            date_text_start  text,
            date_text_end    text,
            start_lo         int,
            start_hi         int,
            end_lo           int,
            end_hi           int,
            is_current       boolean NOT NULL DEFAULT false,
            date_flags       text[] NOT NULL DEFAULT '{}',
            created_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (profile_id, entry_ref)
        );

        CREATE INDEX IF NOT EXISTS idx_experience_entries_profile
            ON experience_entries (profile_id);
        CREATE INDEX IF NOT EXISTS idx_experience_entries_header_atom
            ON experience_entries (header_atom_id);

        -- 2. Ontology versions table
        CREATE TABLE IF NOT EXISTS ontology_versions (
            version    text PRIMARY KEY,
            sha256     text NOT NULL,
            loaded_at  timestamptz NOT NULL DEFAULT now()
        );

        -- 3. Concepts table
        CREATE TABLE IF NOT EXISTS concepts (
            version  text NOT NULL REFERENCES ontology_versions(version) ON DELETE CASCADE,
            id       text NOT NULL,
            label    text NOT NULL,
            kind     text NOT NULL,
            aliases  text[] NOT NULL DEFAULT '{}',
            PRIMARY KEY (version, id)
        );

        CREATE INDEX IF NOT EXISTS idx_concepts_version
            ON concepts (version);

        -- 4. Concept edges table
        CREATE TABLE IF NOT EXISTS concept_edges (
            version   text NOT NULL REFERENCES ontology_versions(version) ON DELETE CASCADE,
            src       text NOT NULL,
            dst       text NOT NULL,
            relation  text NOT NULL CHECK (relation IN ('IMPLIES', 'PART_OF', 'SUBSUMES', 'PARTIAL_OF')),
            weight    double precision NOT NULL DEFAULT 1.0,
            PRIMARY KEY (version, src, dst, relation)
        );

        CREATE INDEX IF NOT EXISTS idx_concept_edges_src
            ON concept_edges (version, src);
        CREATE INDEX IF NOT EXISTS idx_concept_edges_dst
            ON concept_edges (version, dst);
        CREATE INDEX IF NOT EXISTS idx_concept_edges_relation
            ON concept_edges (version, relation);

        -- 5. Atom tags table
        CREATE TABLE IF NOT EXISTS atom_tags (
            atom_id            uuid PRIMARY KEY REFERENCES evidence_atoms(id) ON DELETE CASCADE,
            domains            text[] NOT NULL DEFAULT '{}',
            activities         text[] NOT NULL DEFAULT '{}',
            concepts           text[] NOT NULL DEFAULT '{}',
            evidence_type      text NOT NULL CHECK (evidence_type IN ('USAGE', 'OWNERSHIP', 'LEADERSHIP', 'MENTION_ONLY')),
            impact_quantified  boolean NOT NULL DEFAULT false,
            impact_kind        text,
            model_call_id      uuid REFERENCES model_calls(id) ON DELETE SET NULL,
            ontology_version   text REFERENCES ontology_versions(version) ON DELETE SET NULL,
            created_at         timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_atom_tags_ontology
            ON atom_tags (ontology_version);

        -- 6. Experience domain allocations table
        CREATE TABLE IF NOT EXISTS experience_domain_allocations (
            experience_id    uuid NOT NULL REFERENCES experience_entries(id) ON DELETE CASCADE,
            domain           text NOT NULL,
            level            text NOT NULL CHECK (level IN ('PRIMARY', 'SECONDARY', 'INCIDENTAL')),
            support_atom_ids uuid[] NOT NULL DEFAULT '{}',
            code_atom_ratio  double precision NOT NULL DEFAULT 0.0,
            flags            text[] NOT NULL DEFAULT '{}',
            model_call_id    uuid REFERENCES model_calls(id) ON DELETE SET NULL,
            PRIMARY KEY (experience_id, domain)
        );

        CREATE INDEX IF NOT EXISTS idx_exp_domain_alloc_exp
            ON experience_domain_allocations (experience_id);
        CREATE INDEX IF NOT EXISTS idx_exp_domain_alloc_domain
            ON experience_domain_allocations (domain);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS experience_domain_allocations;
        DROP TABLE IF EXISTS atom_tags;
        DROP TABLE IF EXISTS concept_edges;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS ontology_versions;
        DROP TABLE IF EXISTS experience_entries;
        """
    )
