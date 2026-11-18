import type { Application, AssessmentResult, Category, EvidenceStatus, HistoryEntry, Stage } from './tigTypes'

export const evidenceStyle: Record<EvidenceStatus, [string, string]> = {
  found: ['bg-emerald-100 text-emerald-900', 'Ada di formulir'],
  partial: ['bg-amber-100 text-amber-900', 'Sebagian cocok'],
  not_found: ['bg-rose-100 text-rose-900', 'Tidak ditemukan di formulir'],
}

export const categoryColor: Record<Category, string> = {
  skills: 'var(--cat-skills)', experience: 'var(--cat-experience)',
  education: 'var(--cat-education)', preferences: 'var(--cat-preferences)',
}

export type Row = {
  id: string; stage: Stage; created_at: string; assessed_at: string | null; score: number | null
  category: 'Belum dinilai' | 'Rendah' | 'Sedang' | 'Tinggi'; assessment_status: 'PENDING' | 'RUNNING' | 'FAILED' | 'DONE'
}
export type ListResponse = { applications: Row[]; can_edit: boolean }
export type Detail = Row & { form: Application; assessment: AssessmentResult | null; assessment_history: HistoryEntry[] }

export function scoreLabel(row: Row) {
  if (row.score !== null) return row.score + ' · ' + row.category
  if (row.assessment_status === 'FAILED') return 'Gagal dinilai'
  if (row.assessment_status === 'RUNNING') return 'Sedang dinilai'
  if (row.assessment_status === 'PENDING') return 'Menunggu penilaian'
  return 'Belum dinilai'
}

export const scoreStyles: Record<Row['category'], string> = {
  Tinggi: 'bg-emerald-100 text-emerald-900', Sedang: 'bg-amber-100 text-amber-900',
  Rendah: 'bg-rose-100 text-rose-900', 'Belum dinilai': 'bg-slate-100 text-slate-700',
}

/** Identity of what the server last said about a row; the detail is refetched only when this changes. */
export function rowVersion(row: Pick<Row, 'stage' | 'assessment_status' | 'assessed_at'>) {
  return [row.stage, row.assessment_status, row.assessed_at].join('|')
}
