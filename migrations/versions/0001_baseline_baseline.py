"""baseline

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-10-14 11:31:06.405332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASELINE_SQL = """
-- ---------------------------------------------------------------- akses
CREATE TABLE IF NOT EXISTS users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  email         text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role          text NOT NULL CHECK (role IN ('admin','recruiter','hiring_manager')),
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- lowongan & kriteria
CREATE TABLE IF NOT EXISTS jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  external_ref    text,
  title           text NOT NULL,
  location        text,
  employment_type text,
  jd_text         text NOT NULL,
  status          text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','OPEN','CLOSED')),
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requirement_sets (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL,
  job_id                 uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  version                int  NOT NULL,
  status                 text NOT NULL CHECK (status IN ('DRAFT','APPROVED')),
  category_weights       jsonb NOT NULL,
  compiled_by_model_call uuid,
  approved_by            uuid REFERENCES users(id),
  approved_at            timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (job_id, version)
);

CREATE TABLE IF NOT EXISTS requirements (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  requirement_set_id uuid NOT NULL REFERENCES requirement_sets(id) ON DELETE CASCADE,
  requirement_id     text NOT NULL,
  description        text NOT NULL,
  category           text NOT NULL,
  kind               text NOT NULL,
  importance         text NOT NULL CHECK (importance IN ('MUST_HAVE','STRONG_PREFERENCE','NICE_TO_HAVE')),
  weight             numeric NOT NULL CHECK (weight >= 0),
  concepts           text[] NOT NULL DEFAULT '{}',
  params             jsonb NOT NULL DEFAULT '{}',
  hard_filter        boolean NOT NULL DEFAULT false,
  source_text        text,
  lint_flags         text[] NOT NULL DEFAULT '{}',
  UNIQUE (requirement_set_id, requirement_id)
);

-- ---------------------------------------------------------------- kandidat & dokumen
CREATE TABLE IF NOT EXISTS candidates (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  candidate_code text NOT NULL,
  status         text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','MANUAL_ONLY','DELETED')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz,
  UNIQUE (tenant_id, candidate_code)
);

CREATE TABLE IF NOT EXISTS candidate_identities (
  candidate_id   uuid PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
  tenant_id      uuid NOT NULL,
  full_name      text,
  email          text,
  phone          text,
  email_hash     text,
  phone_hash     text,
  location_raw   text,
  other_personal bytea
);

CREATE TABLE IF NOT EXISTS documents (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  job_id            uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  candidate_id      uuid REFERENCES candidates(id) ON DELETE CASCADE,
  original_filename text NOT NULL,
  mime              text,
  size_bytes        bigint,
  pages             int,
  sha256            text NOT NULL,
  storage_key       text,
  status            text NOT NULL CHECK (status IN ('RECEIVED','PROCESSING','READY','NEEDS_REVIEW','REJECTED','DUPLICATE')),
  reasons           text[] NOT NULL DEFAULT '{}',
  flags             text[] NOT NULL DEFAULT '{}',
  duplicate_of      uuid REFERENCES documents(id),
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_job_status ON documents (job_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS documents_job_sha ON documents (job_id, sha256) WHERE status <> 'DUPLICATE';

CREATE TABLE IF NOT EXISTS candidate_profiles (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  document_id       uuid NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
  profile           jsonb NOT NULL,
  matching_profile  jsonb NOT NULL,
  extractor_version text NOT NULL,
  quality           jsonb NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skill_mentions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  profile_id   uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  concept_id   text,
  surface_text text NOT NULL,
  context      text NOT NULL,
  entry_ref    text,
  source       jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skill_mentions_concept ON skill_mentions (concept_id);
CREATE INDEX IF NOT EXISTS idx_skill_mentions_profile ON skill_mentions (profile_id);

CREATE TABLE IF NOT EXISTS profile_chunks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  profile_id      uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  kind            text NOT NULL,
  entry_ref       text,
  text_redacted   text NOT NULL,
  chunk_hash      text NOT NULL,
  embedding       vector(640),
  embedding_model text,
  fts             tsvector GENERATED ALWAYS AS (to_tsvector('simple', text_redacted)) STORED
);
CREATE INDEX IF NOT EXISTS idx_profile_chunks_embedding ON profile_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_profile_chunks_fts ON profile_chunks USING gin (fts);

-- ---------------------------------------------------------------- screening
CREATE TABLE IF NOT EXISTS screening_runs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  job_id             uuid NOT NULL REFERENCES jobs(id),
  requirement_set_id uuid NOT NULL REFERENCES requirement_sets(id),
  as_of              date NOT NULL,
  status             text NOT NULL CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED')),
  versions           jsonb NOT NULL,
  params             jsonb NOT NULL DEFAULT '{}',
  parent_run_id      uuid REFERENCES screening_runs(id),
  created_by         uuid REFERENCES users(id),
  started_at         timestamptz,
  finished_at        timestamptz
);

CREATE TABLE IF NOT EXISTS candidate_scores (
  run_id          uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
  candidate_id    uuid NOT NULL REFERENCES candidates(id),
  tenant_id       uuid NOT NULL,
  document_id     uuid NOT NULL REFERENCES documents(id),
  rank            int,
  band            text CHECK (band IN ('A','B','C','R')),
  raw_score       numeric,
  final_score     numeric,
  capped          boolean NOT NULL DEFAULT false,
  recommendation  text CHECK (recommendation IN ('SHORTLIST','REVIEW','LOW_PRIORITY','MANUAL_CHECK')),
  category_scores jsonb NOT NULL DEFAULT '{}',
  flags           text[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (run_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS requirement_scores (
  run_id         uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
  candidate_id   uuid NOT NULL REFERENCES candidates(id),
  requirement_id text NOT NULL,
  tenant_id      uuid NOT NULL,
  state          text NOT NULL CHECK (state IN ('STRONG','PARTIAL','NOT_DEMONSTRATED','UNKNOWN')),
  confidence     numeric NOT NULL,
  method         text NOT NULL CHECK (method IN ('rule','verifier','manual')),
  metrics        jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (run_id, candidate_id, requirement_id)
);

CREATE TABLE IF NOT EXISTS evidence (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id         uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
  candidate_id   uuid NOT NULL REFERENCES candidates(id),
  requirement_id text NOT NULL,
  tenant_id      uuid NOT NULL,
  quote          text NOT NULL,
  page           int,
  char_start     int,
  char_end       int,
  bbox           numeric[],
  context        text,
  verified       boolean NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_run_candidate ON evidence (run_id, candidate_id);

CREATE TABLE IF NOT EXISTS reviews (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  run_id       uuid NOT NULL REFERENCES screening_runs(id),
  candidate_id uuid NOT NULL REFERENCES candidates(id),
  reviewer_id  uuid NOT NULL REFERENCES users(id),
  decision     text NOT NULL CHECK (decision IN ('SHORTLIST','HOLD','NOT_PROCEED')),
  reason       text,
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (decision <> 'NOT_PROCEED' OR reason IS NOT NULL)
);

-- ---------------------------------------------------------------- model, cache, antrian, audit
CREATE TABLE IF NOT EXISTS model_calls (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid,
  task           text NOT NULL,
  provider       text NOT NULL,
  model          text NOT NULL,
  prompt_version text NOT NULL,
  input_hash     text NOT NULL,
  output_hash    text,
  tokens_in      int,
  tokens_out     int,
  cost_usd       numeric,
  latency_ms     int,
  status         text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_cache (
  key        text PRIMARY KEY,
  task       text NOT NULL,
  output     jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs_queue (
  id         bigserial PRIMARY KEY,
  type       text NOT NULL,
  payload    jsonb NOT NULL,
  status     text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','DONE','FAILED')),
  attempts   int NOT NULL DEFAULT 0,
  run_after  timestamptz NOT NULL DEFAULT now(),
  locked_at  timestamptz,
  error      text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jobs_queue_status ON jobs_queue (status, run_after);

CREATE TABLE IF NOT EXISTS audit_logs (
  id          bigserial PRIMARY KEY,
  tenant_id   uuid,
  actor_id    uuid,
  action      text NOT NULL,
  target_type text,
  target_id   text,
  metadata    jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(BASELINE_SQL)


def downgrade() -> None:
    tables = [
        "audit_logs", "jobs_queue", "llm_cache", "model_calls", "reviews", "evidence",
        "requirement_scores", "candidate_scores", "screening_runs", "profile_chunks",
        "skill_mentions", "candidate_profiles", "documents", "candidate_identities",
        "candidates", "requirements", "requirement_sets", "jobs", "users"
    ]
    conn = op.get_bind()
    for table in tables:
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE;")
