import { blankEducation, blankExperience } from './intakeRules.ts'
import type { Application, Education, Experience } from './tigTypes.ts'

// Headline facts for the recruiter's profile card, derived from the applicant's own form rows.

const rank: Record<string, number> = { 'SMA/SMK': 0, D3: 1, D4: 2, S1: 3, S2: 4, S3: 5 }
const isCurrent = (end: string) => /^(present|sekarang|saat ini|kini)$/i.test(end.trim())

/** Highest degree listed (the first one wins a tie); a row with only a campus still counts when no level is known. */
export function highestEducation(rows: Education[]): Education | null {
  let best: Education | null = null
  for (const row of rows) {
    if (blankEducation(row)) continue
    if (!best || (rank[row.level ?? ''] ?? -1) > (rank[best.level ?? ''] ?? -1)) best = row
  }
  return best
}

/** The current job if any, otherwise the one that ended last (YYYY and YYYY-MM sort as text), otherwise the first listed. */
export function latestExperience(rows: Experience[]): Experience | null {
  const listed = rows.filter(row => !blankExperience(row))
  if (!listed.length) return null
  const current = listed.find(row => isCurrent(row.end))
  if (current) return current
  let best = listed[0]
  for (const row of listed) if (row.end.trim() > best.end.trim()) best = row
  return best
}

export type SummaryList = { label: string; items: string[]; layout: 'bullets' | 'inline' }

/** Lists shown under the applicant's form. Entries that are sentences (projects, certificates) get a bullet each, because a comma
 *  between two long entries that themselves contain commas cannot be read. */
export function summaryLists(form: Pick<Application, 'projects' | 'skills' | 'languages' | 'certifications' | 'priority'>): SummaryList[] {
  const lists: [keyof typeof form, string, SummaryList['layout']][] = [
    ['projects', 'Proyek', 'bullets'], ['skills', 'Keahlian', 'inline'], ['languages', 'Bahasa', 'inline'],
    ['certifications', 'Sertifikasi', 'bullets'], ['priority', 'Pilihan pelamar', 'inline'],
  ]
  return lists.filter(([key]) => form[key].length > 0).map(([key, label, layout]) => ({ label, items: form[key], layout }))
}
