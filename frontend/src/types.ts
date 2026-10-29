export interface Requirement {
  requirement_id: string
  description: string
  category: 'EXPERIENCE' | 'HARD_SKILLS' | 'EDUCATION_CERTIFICATION' | 'EDUCATION_CERT' | 'ACHIEVEMENT_LEADERSHIP' | 'ACHIEVEMENT' | string
  kind: 'EXPERIENCE_DURATION' | 'SKILL' | 'RESPONSIBILITY' | 'EDUCATION' | 'CERTIFICATION' | 'ACHIEVEMENT' | 'LEADERSHIP' | string
  importance: 'MUST_HAVE' | 'STRONG_PREFERENCE' | 'NICE_TO_HAVE' | string
  weight: number
  concepts: string[]
  params?: Record<string, any>
  source_text?: string
  lint_flags?: string[]
}

export interface CandidateScore {
  rank: number
  cv_id: string
  file_name: string
  blind_id: string
  real_name: string
  revealed: boolean
  final_score: number
  raw_score: number
  band: 'A' | 'B' | 'C' | 'R'
  recommendation: 'SHORTLIST' | 'REVIEW' | 'LOW_PRIORITY' | 'MANUAL_CHECK' | 'REJECTED_NOT_A_CV'
  category_breakdown: Record<string, number>
  metrics: Record<string, any>
  flags: string[]
  document_reasons?: string[]
  decision?: 'SHORTLIST' | 'HOLD' | 'TIDAK_LANJUT' | 'NONE'
  decision_notes?: string
  quality_status?: string
  eligibility_status?: 'ELIGIBLE' | 'NOT_ELIGIBLE' | 'UNKNOWN'
  eligibility_reasons?: string[]
}

/** One piece of CV evidence behind a verdict: a verbatim sentence and where it sits in the CV. */
export interface TraceEvidence {
  atom_key: string
  kind: string
  tier: 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | string
  tier_label: string
  is_evidence: boolean
  page: number | null
  quote: string
  source_found: boolean
  span: [number, number] | null
  context_before: string
  context_after: string
}

export interface TraceFacet {
  facet_key: string
  hypothesis: string
  core: boolean
  verdict: string
  verdict_label: string
  depth: string
  analysis: string
  rationale_code: string | null
  method: string | null
  evidence: TraceEvidence[]
  evidence_tracked: boolean
  critic: {
    action: string
    final_verdict: string
    original_verdict: string | null
    reasoning: string
    disagreement: boolean
  } | null
}

export interface TraceRequirement {
  requirement_id: string
  description: string
  kind: string
  category: string
  importance: string
  weight: number
  weight_share: number
  state: string
  state_label: string
  state_value: number | null
  counted: boolean
  points: number | null
  max_points: number
  why: string
  facets: TraceFacet[]
  duration: {
    domain: string
    months_lo: number
    months_hi: number
    min_months: number
    periods: Array<{ entry: string | null; weight: number; start: string; end: string; months: number }>
  } | null
}

export interface ScoreTrace {
  summary: {
    final_score: number
    raw_score: number
    band: string
    recommendation: string
    coverage: number | null
    score_interval: [number, number]
    capped: boolean
    band_reason: string
    recommendation_reason: string
    counted_weight: number
    total_weight: number
  }
  formula: string
  categories: Array<{ category: string; score: number; weight: number | null }>
  requirements: TraceRequirement[]
  flags: Array<{ flag: string; meaning: string }>
  consistency: {
    consistent: boolean
    stored_final: number
    recomputed_final: number
    stored_band: string
    recomputed_band: string
    note: string
  }
  cited_atoms: string[]
  source_available: boolean
}

export interface SourceHighlight {
  atom_key: string
  start: number
  end: number
}

export interface CandidateDetail extends CandidateScore {
  requirement_states: Record<string, 'STRONG' | 'PARTIAL' | 'NOT_DEMONSTRATED'>
  evidence: Record<string, Array<{ quote: string; context: string; verified: boolean }>>
  explanation: {
    band: string
    recommendation: string
    final_score: number
    strengths: Array<{ requirement_id: string; description: string; weight: number; quote: string }>
    unproven: Array<{ requirement_id: string; description: string; state: string; weight: number; note: string }>
    interview_questions: Array<{ requirement_id: string; focus: string; question: string }>
  }
  full_text?: string | null
  score_trace?: ScoreTrace | null
  source_highlights?: SourceHighlight[]
}
