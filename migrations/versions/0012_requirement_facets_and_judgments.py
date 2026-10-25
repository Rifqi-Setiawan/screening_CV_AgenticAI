"""requirement_facets_and_judgments

Revision ID: 0012_requirement_facets_judgments
Revises: 0011_ontology_profiler_tables
Create Date: 2026-10-25 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_req_facets_judgments"
down_revision: str | Sequence[str] | None = "0011_ontology_profiler_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        -- 1. Extend requirements table with v2.1 fields
        ALTER TABLE requirements
            ADD COLUMN IF NOT EXISTS target_domains text[] NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS duration_policy jsonb NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS accepted_evidence text[] NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS depth_floor text NOT NULL DEFAULT 'L1';

        -- 2. Requirement facets table
        CREATE TABLE IF NOT EXISTS requirement_facets (
            requirement_uuid uuid NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
            facet_key        text NOT NULL,
            hypothesis       text NOT NULL,
            core             boolean NOT NULL DEFAULT true,
            concepts         text[] NOT NULL DEFAULT '{}',
            created_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (requirement_uuid, facet_key)
        );

        CREATE INDEX IF NOT EXISTS idx_requirement_facets_uuid
            ON requirement_facets (requirement_uuid);

        -- 3. Facet judgments table
        CREATE TABLE IF NOT EXISTS facet_judgments (
            run_id               uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id         uuid NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            requirement_id       text NOT NULL,
            facet_key            text NOT NULL,
            tenant_id            uuid NOT NULL,
            verdict              text NOT NULL,
            depth_level          text,
            support_atom_ids     uuid[] NOT NULL DEFAULT '{}',
            method               text NOT NULL,
            analysis             text,
            nli_p_entail         numeric,
            rationale_code       text,
            superseded_by_critic boolean NOT NULL DEFAULT false,
            created_at           timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, candidate_id, requirement_id, facet_key)
        );

        CREATE INDEX IF NOT EXISTS idx_facet_judgments_run_cand
            ON facet_judgments (run_id, candidate_id);
        CREATE INDEX IF NOT EXISTS idx_facet_judgments_tenant
            ON facet_judgments (tenant_id);

        -- 4. Domain durations table
        CREATE TABLE IF NOT EXISTS domain_durations (
            run_id       uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
            candidate_id uuid NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            domain       text NOT NULL,
            tenant_id    uuid NOT NULL,
            policy_hash  text NOT NULL,
            months_lo    numeric NOT NULL DEFAULT 0.0,
            months_hi    numeric NOT NULL DEFAULT 0.0,
            month_ledger jsonb NOT NULL DEFAULT '[]',
            created_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (run_id, candidate_id, domain)
        );

        CREATE INDEX IF NOT EXISTS idx_domain_durations_run_cand
            ON domain_durations (run_id, candidate_id);
        CREATE INDEX IF NOT EXISTS idx_domain_durations_tenant
            ON domain_durations (tenant_id);

        -- 5. Facet templates table (ontology integration)
        CREATE TABLE IF NOT EXISTS facet_templates (
            version      text NOT NULL REFERENCES ontology_versions(version) ON DELETE CASCADE,
            role_concept text NOT NULL,
            facet_key    text NOT NULL,
            hypothesis   text NOT NULL,
            core         boolean NOT NULL DEFAULT true,
            concepts     text[] NOT NULL DEFAULT '{}',
            created_at   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (version, role_concept, facet_key)
        );

        CREATE INDEX IF NOT EXISTS idx_facet_templates_role
            ON facet_templates (version, role_concept);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS facet_templates;
        DROP TABLE IF EXISTS domain_durations;
        DROP TABLE IF EXISTS facet_judgments;
        DROP TABLE IF EXISTS requirement_facets;

        ALTER TABLE requirements
            DROP COLUMN IF EXISTS depth_floor,
            DROP COLUMN IF EXISTS accepted_evidence,
            DROP COLUMN IF EXISTS duration_policy,
            DROP COLUMN IF EXISTS target_domains;
        """
    )
