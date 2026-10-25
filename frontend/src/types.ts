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
  full_text?: string
}
