-- Skema awal PostgreSQL 16+ untuk MVP CV screening.
-- Jalankan lewat migrasi (Alembic). Butuh ekstensi pgvector >= 0.8.2 dan pgcrypto.
-- Dimensi vektor 1024 cocok untuk harrier-oss-v1-0.6b / Qwen3-Embedding-0.6B. Sesuaikan kalau model lain.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- akses
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  email         text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role          text NOT NULL CHECK (role IN ('admin','recruiter','hiring_manager')),
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- lowongan & kriteria
CREATE TABLE jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  external_ref    text,                       -- mis. 'JD-01' untuk golden dataset
  title           text NOT NULL,
  location        text,
  employment_type text,
  jd_text         text NOT NULL,
  status          text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','OPEN','CLOSED')),
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE requirement_sets (
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

CREATE TABLE requirements (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  requirement_set_id uuid NOT NULL REFERENCES requirement_sets(id) ON DELETE CASCADE,
  requirement_id     text NOT NULL,            -- 'R1', 'R2', ...
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
CREATE TABLE candidates (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  candidate_code text NOT NULL,                -- 'C-0001', tampil di blind mode
  status         text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','MANUAL_ONLY','DELETED')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz,
  UNIQUE (tenant_id, candidate_code)
);

-- Identitas dipisah. Akses hanya lewat endpoint reveal-identity (tercatat di audit_logs).
CREATE TABLE candidate_identities (
  candidate_id   uuid PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
  tenant_id      uuid NOT NULL,
  full_name      text,
  email          text,
  phone          text,
  email_hash     text,                         -- untuk deteksi orang yang sama
  phone_hash     text,
  location_raw   text,
  other_personal bytea                         -- JSON terenkripsi (pgp_sym_encrypt), mis. tanggal lahir
);

CREATE TABLE documents (
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
CREATE INDEX ON documents (job_id, status);
CREATE UNIQUE INDEX documents_job_sha ON documents (job_id, sha256) WHERE status <> 'DUPLICATE';

CREATE TABLE candidate_profiles (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL,
  document_id       uuid NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
  profile           jsonb NOT NULL,            -- CandidateProfile tanpa blok identity
  matching_profile  jsonb NOT NULL,            -- versi teredaksi untuk penilaian
  extractor_version text NOT NULL,
  quality           jsonb NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE skill_mentions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  profile_id   uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  concept_id   text,                           -- NULL = belum terpetakan
  surface_text text NOT NULL,
  context      text NOT NULL,
  entry_ref    text,
  source       jsonb NOT NULL
);
CREATE INDEX ON skill_mentions (concept_id);
CREATE INDEX ON skill_mentions (profile_id);

CREATE TABLE profile_chunks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL,
  profile_id      uuid NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
  kind            text NOT NULL,               -- experience, project, education, skills, summary
  entry_ref       text,
  text_redacted   text NOT NULL,
  chunk_hash      text NOT NULL,
  embedding       vector(640),
  embedding_model text,
  fts             tsvector GENERATED ALWAYS AS (to_tsvector('simple', text_redacted)) STORED
);
CREATE INDEX ON profile_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON profile_chunks USING gin (fts);

-- ---------------------------------------------------------------- screening (event immutable)
CREATE TABLE screening_runs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL,
  job_id             uuid NOT NULL REFERENCES jobs(id),
  requirement_set_id uuid NOT NULL REFERENCES requirement_sets(id),
  as_of              date NOT NULL,
  status             text NOT NULL CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED')),
  versions           jsonb NOT NULL,           -- extractor, taxonomy, embedding, verifier+prompt, scoring_version
  params             jsonb NOT NULL DEFAULT '{}',
  parent_run_id      uuid REFERENCES screening_runs(id),
  created_by         uuid REFERENCES users(id),
  started_at         timestamptz,
  finished_at        timestamptz
);

CREATE TABLE candidate_scores (
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

CREATE TABLE requirement_scores (
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

CREATE TABLE evidence (
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
CREATE INDEX ON evidence (run_id, candidate_id);

CREATE TABLE reviews (
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
CREATE TABLE model_calls (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid,
  task           text NOT NULL,                -- compile_requirements, extract_block, verify_requirement
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

CREATE TABLE llm_cache (
  key        text PRIMARY KEY,                 -- sha256(task|model|prompt_version|input)
  task       text NOT NULL,
  output     jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs_queue (
  id         bigserial PRIMARY KEY,
  type       text NOT NULL,                    -- ingest_document, compile_requirements, run_screening
  payload    jsonb NOT NULL,
  status     text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','DONE','FAILED')),
  attempts   int NOT NULL DEFAULT 0,
  run_after  timestamptz NOT NULL DEFAULT now(),
  locked_at  timestamptz,
  error      text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON jobs_queue (status, run_after);

CREATE TABLE audit_logs (
  id          bigserial PRIMARY KEY,
  tenant_id   uuid,
  actor_id    uuid,
  action      text NOT NULL,                   -- UPLOAD, APPROVE_REQUIREMENTS, RUN_SCREENING, REVEAL_IDENTITY, REVIEW, EXPORT, DELETE_CANDIDATE
  target_type text,
  target_id   text,
  metadata    jsonb NOT NULL DEFAULT '{}',     -- tanpa PII
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- Append-only: cabut UPDATE/DELETE dari role aplikasi.
-- REVOKE UPDATE, DELETE ON audit_logs FROM app_user;
