import { describeDetail } from './requestErrors.ts'
export type Degree = 'SMA/SMK' | 'D3' | 'D4' | 'S1' | 'S2' | 'S3'
export type WorkMode = 'WFO' | 'Hybrid' | 'Remote'
export type Stage = 'Seleksi' | 'Asesmen' | 'Interview' | 'SPK' | 'Ditolak'
export type Category = 'skills' | 'experience' | 'education' | 'preferences'
export const degrees: Degree[] = ['SMA/SMK', 'D3', 'D4', 'S1', 'S2', 'S3']
export const modes: WorkMode[] = ['WFO', 'Hybrid', 'Remote']
export const stages: Stage[] = ['Seleksi', 'Asesmen', 'Interview', 'SPK', 'Ditolak']
export const categories: Record<Category, string> = {
  skills: 'Keahlian dan kompetensi',
  experience: 'Pengalaman kerja',
  education: 'Pendidikan dan IPK',
  preferences: 'Preferensi dan kondisi kerja',
}

export type Education = { level: Degree | null; campus: string; major: string; gpa: number | null }
export type Experience = { title: string; organization: string; start: string; end: string; description: string }
export type Application = {
  full_name: string
  email: string
  phone: string
  education: Education[]
  experiences: Experience[]
  projects: string[]
  skills: string[]
  languages: string[]
  certifications: string[]
  preferences: { expected_salary: number | null; domicile: string; work_modes: WorkMode[]; open_to_placement: boolean | null }
  priority: string[]
  links: string[]
  available_from: string
  /** Set by the server when the application is submitted; older applications have none. */
  consent_at?: string
}

export type PositionSummary = {
  education_minimum: Degree | null; gpa_minimum: number | null; majors: string[]; skills: string[]; qualifications: string
}
export type Regular = PositionSummary & {
  experience: string
  work_mode: WorkMode | null
  location: string
  salary_minimum: number | null
  salary_maximum: number | null
  campus_tiers: { campus: string; tier: 1 | 2 | 3; aliases: string[] }[]
  weights: Record<Category, number>
}
export type Config = { published: boolean; regular: Regular | null; program: (PositionSummary & { title: string })[] }
export const emptyPosition: PositionSummary = { education_minimum: null, gpa_minimum: null, majors: [], skills: [], qualifications: '' }
export const emptyRegular: Regular = {
  ...emptyPosition, experience: '', work_mode: null, location: '', salary_minimum: null, salary_maximum: null, campus_tiers: [],
  weights: { skills: 40, experience: 35, education: 15, preferences: 10 },
}
export const emptyApplication: Application = {
  full_name: '', email: '', phone: '', education: [], experiences: [], projects: [], skills: [], languages: [],
  certifications: [], preferences: { expected_salary: null, domicile: '', work_modes: [], open_to_placement: null }, priority: [],
  links: [], available_from: '',
}

export type EvidenceStatus = 'found' | 'partial' | 'not_found'
export type Evidence = { quote: string; status: EvidenceStatus }
export type CategoryResult = { score: number; explanation: string; evidence?: Evidence[] }
export type Assessment = {
  score: number; summary: string; strengths?: string[]; gaps?: string[]
  categories?: Record<Category, CategoryResult>
  score_reasoning?: string
  weighted_reference?: number
  weighted_difference?: number
  estimated?: boolean
}
export type Trace = {
  model: string
  prompt_version: string
  mode: 'regular' | 'program'
  weights: Record<Category, number> | null
  input: Record<string, unknown>
  excluded: string[]
  sanitization: { hidden: { field: string; reasons: string[] }[]; attributes: string[]; links: number }
}
export type AssessmentResult = Assessment & {
  primary?: string; priorities?: string[]; options?: Record<string, Assessment>; trace?: Trace
}
export type HistoryEntry = { assessment: AssessmentResult; assessed_at: string | null; replaced_at: string; replaced_by: string }

export class RequestError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function tigRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const result = await fetch(url, { ...options, cache: 'no-store' })
  if (!result.ok) {
    const data = await result.json().catch(() => null)
    const message = typeof data?.detail === 'string' ? data.detail
      : Array.isArray(data?.detail) ? describeDetail(data.detail)
        : 'Permintaan gagal (' + result.status + ').'
    throw new RequestError(message, result.status)
  }
  return result.json()
}

export const jsonOptions = (method: string, body: unknown, headers?: Record<string, string>): RequestInit => ({
  method, body: JSON.stringify(body), headers: { ...headers, 'Content-Type': 'application/json' },
})
