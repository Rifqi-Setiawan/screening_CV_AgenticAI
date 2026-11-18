import { categories } from './tigTypes.ts'
import type { Category, CategoryResult, HistoryEntry } from './tigTypes.ts'

// Pure derivations for the score detail page. Every function tolerates old or partial assessments
// (missing categories, missing weights, NaN) because stored assessments predate the current shape.

const order = Object.keys(categories) as Category[]
const clamp = (value: number, low: number, high: number) => Number.isFinite(value) ? Math.min(high, Math.max(low, value)) : low
const round1 = (value: number) => Math.round(value * 10) / 10

export type Contribution = { key: Category; score: number; weight: number; contribution: number }

/** Per-category subscore, weight (%) and contribution (weight * subscore / 100), in display order. */
export function contributions(
  results: Record<Category, CategoryResult> | undefined, weights: Record<Category, number> | null | undefined,
): Contribution[] {
  if (!results || !weights) return []
  return order.filter(key => results[key]).map(key => {
    const score = clamp(results[key].score, 0, 100)
    const weight = clamp(weights[key], 0, 100)
    return { key, score, weight, contribution: weight * score / 100 }
  })
}

/** Segment widths (% of a 100-wide track). Scaled down only when contributions add up to more than 100. */
export function trackSegments(items: Contribution[]): { key: Category; width: number }[] {
  const total = items.reduce((sum, item) => sum + item.contribution, 0)
  const scale = total > 100 ? 100 / total : 1
  return items.map(item => ({ key: item.key, width: item.contribution * scale }))
}

export type EvidenceShare = { found: number; partial: number; notFound: number; total: number; foundPct: number }

export function evidenceShare(results: Record<Category, CategoryResult> | undefined): EvidenceShare {
  const share = { found: 0, partial: 0, notFound: 0, total: 0, foundPct: 0 }
  for (const key of order) {
    for (const item of results?.[key]?.evidence ?? []) {
      if (item.status === 'found') share.found++
      else if (item.status === 'partial') share.partial++
      else share.notFound++
      share.total++
    }
  }
  share.foundPct = share.total ? Math.round(share.found * 100 / share.total) : 0
  return share
}

/** Competition ranking (ties share a rank) among scored applications of one job. */
export function rankOf(rows: { id: string; score: number | null }[], id: string): { rank: number; total: number; average: number } | null {
  const scored = rows.filter((row): row is { id: string; score: number } => row.score !== null && Number.isFinite(row.score))
  const target = scored.find(row => row.id === id)
  if (!target) return null
  const higher = scored.filter(row => row.score > target.score).length
  return { rank: higher + 1, total: scored.length, average: round1(scored.reduce((sum, row) => sum + row.score, 0) / scored.length) }
}

export type SeriesPoint = { score: number; at: string | null; current: boolean }

/** Chronological score history (oldest first) ending with the current score; at most the last 12 points. */
export function historySeries(history: HistoryEntry[], currentScore: number | null): SeriesPoint[] {
  const points: SeriesPoint[] = history
    .filter(entry => Number.isFinite(entry.assessment?.score))
    .sort((a, b) => a.replaced_at.localeCompare(b.replaced_at))
    .map(entry => ({ score: entry.assessment.score, at: entry.replaced_at, current: false }))
  if (currentScore !== null && Number.isFinite(currentScore)) points.push({ score: currentScore, at: null, current: true })
  return points.slice(-12)
}

export function lastChange(series: SeriesPoint[]): { latest: number; previous: number; delta: number } | null {
  if (series.length < 2) return null
  const latest = series[series.length - 1].score
  const previous = series[series.length - 2].score
  return { latest, previous, delta: latest - previous }
}
