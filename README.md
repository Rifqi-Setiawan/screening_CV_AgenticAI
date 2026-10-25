# High-Precision Agentic AI CV Screening & Candidate Ranking Platform (v2.1)

A next-generation CV screening and candidate ranking engine designed to evaluate candidate qualifications through context-aware asymmetric reasoning, temporal calendar union, and multi-agent verification.

## Core Advancements (over v1.0)

1. **Contextual & Directional Entailment (Title-vs-Context):**
   - Breaks job requirements down into discrete evaluable facets.
   - Evaluates whether candidate work activities logically entail target qualifications rather than relying on rigid title string matching.
2. **Deterministic Temporal Engine (Fragmented Duration Accumulator):**
   - Implements sweep-line Weighted Calendar Union per domain to accurately accumulate concurrent, part-time, and fragmented career tenures without double-counting.
3. **Evidence Atomization & Zero-Hallucination Grounding:**
   - Deconstructs resumes into immutable evidence atoms with exact original character offsets and page coordinates.
   - Eliminates citation hallucinations by construction.
4. **Adversarial Multi-Agent Verification:**
   - Profiler and Matcher agents extract and match evidence against taxonomy facets.
   - Critic agent (employing an independent model family) scrutinizes borderline scores, keyword-stuffing anomalies, and contradictions.
5. **Human-in-the-Loop & PDP Compliance (UU No. 27/2022):**
   - Strictly zero auto-rejections; automated workflows provide auditable recommendations while preserving final decision authority for human recruiters.

## Architecture

- **Backend:** Python 3.12, FastAPI, PostgreSQL 16 with pgvector 0.8.7 (Harrier-270m 640d)
- **AI Gateway:** 9Router OpenAI-compatible endpoint (`http://127.0.0.1:20128/v1`)
  - Profiler & Matcher: `ag/gemini-3.8-flash-high`
  - Critic / Verifier: `cc/claude-sonnet-5-5`
- **Frontend:** React SPA (Vite, TypeScript, Tailwind CSS)
- **Specification:** See `docs/BLUEPRINT_v2.1_AGENTIC_CV_SCREENING.md`

## Getting Started

### 1. Environment Setup
```bash
# Initialize virtualenv
uv venv .venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.lock
uv pip install alembic torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu sentence-transformers transformers
```

### 2. Configuration & Migrations
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials and 9Router gateway key

# Run database migrations
.venv/bin/alembic upgrade head
```

### 3. Run Tests
```bash
.venv/bin/pytest tests/
```
