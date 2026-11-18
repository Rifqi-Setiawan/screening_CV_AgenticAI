import test from 'node:test'
import assert from 'node:assert/strict'
import { contributions, trackSegments, evidenceShare, rankOf, historySeries, lastChange } from '../.unit-build/scoreView.js'

const cat = (score, evidence) => ({ score, explanation: 'x', ...(evidence ? { evidence } : {}) })
const categories = { skills: cat(90), experience: cat(80), education: cat(70), preferences: cat(60) }
const weights = { skills: 40, experience: 35, education: 15, preferences: 10 }

test('contributions follow category order and weight * subscore / 100', () => {
  const items = contributions(categories, weights)
  assert.deepEqual(items.map(item => item.key), ['skills', 'experience', 'education', 'preferences'])
  assert.deepEqual(items.map(item => item.contribution), [36, 28, 10.5, 6])
  assert.equal(items.reduce((sum, item) => sum + item.contribution, 0), 80.5)
})

test('contributions is empty for old assessments without categories or without weights', () => {
  assert.deepEqual(contributions(undefined, weights), [])
  assert.deepEqual(contributions(categories, null), [])
  assert.deepEqual(contributions(categories, undefined), [])
})

test('contributions tolerates NaN, negative and out-of-range numbers', () => {
  const messy = { ...categories, skills: cat(Number.NaN), experience: cat(250), education: cat(-5) }
  const items = contributions(messy, { ...weights, preferences: -10 })
  for (const item of items) {
    assert.ok(Number.isFinite(item.contribution), item.key)
    assert.ok(item.score >= 0 && item.score <= 100, item.key)
    assert.ok(item.weight >= 0, item.key)
  }
  assert.equal(items[1].score, 100)
})

test('trackSegments never exceeds 100% even when weights add up to more than 100', () => {
  const heavy = contributions(
    { skills: cat(100), experience: cat(100), education: cat(100), preferences: cat(100) },
    { skills: 50, experience: 40, education: 30, preferences: 10 })
  const widths = trackSegments(heavy).map(segment => segment.width)
  const sum = widths.reduce((a, b) => a + b, 0)
  assert.ok(sum <= 100 + 1e-9 && sum >= 99.99, String(sum))
})

test('trackSegments gives zero widths (not NaN) when everything is zero', () => {
  const zero = contributions({ skills: cat(0), experience: cat(0), education: cat(0), preferences: cat(0) }, weights)
  assert.deepEqual(trackSegments(zero).map(segment => segment.width), [0, 0, 0, 0])
})

test('trackSegments keeps the real proportions when the total is at most 100', () => {
  const widths = trackSegments(contributions(categories, weights)).map(segment => segment.width)
  assert.deepEqual(widths, [36, 28, 10.5, 6])
})

test('evidenceShare counts statuses across categories and reports found percentage', () => {
  const share = evidenceShare({
    skills: cat(90, [{ quote: 'a', status: 'found' }, { quote: 'b', status: 'found' }]),
    experience: cat(80, [{ quote: 'c', status: 'partial' }]),
    education: cat(70, [{ quote: 'd', status: 'not_found' }]),
    preferences: cat(60),
  })
  assert.deepEqual(share, { found: 2, partial: 1, notFound: 1, total: 4, foundPct: 50 })
})

test('evidenceShare is all zero for assessments without quoted evidence', () => {
  assert.deepEqual(evidenceShare(undefined), { found: 0, partial: 0, notFound: 0, total: 0, foundPct: 0 })
  assert.deepEqual(evidenceShare(categories), { found: 0, partial: 0, notFound: 0, total: 0, foundPct: 0 })
})

test('rankOf uses competition ranking so ties share a rank, and ignores unscored rows', () => {
  const rows = [{ id: 'a', score: 90 }, { id: 'b', score: 80 }, { id: 'c', score: 80 }, { id: 'd', score: 70 }, { id: 'e', score: null }]
  assert.deepEqual(rankOf(rows, 'a'), { rank: 1, total: 4, average: 80 })
  assert.equal(rankOf(rows, 'b').rank, 2)
  assert.equal(rankOf(rows, 'c').rank, 2)
  assert.equal(rankOf(rows, 'd').rank, 4)
})

test('rankOf with a single scored application is #1 of 1 without dividing by zero', () => {
  assert.deepEqual(rankOf([{ id: 'only', score: 55 }], 'only'), { rank: 1, total: 1, average: 55 })
})

test('rankOf returns null when the target is unscored or missing', () => {
  assert.equal(rankOf([{ id: 'a', score: null }], 'a'), null)
  assert.equal(rankOf([{ id: 'a', score: 10 }], 'zzz'), null)
  assert.equal(rankOf([], 'a'), null)
})

test('historySeries is chronological, appends the current score and skips unusable entries', () => {
  const entry = (score, replaced_at) => ({ assessment: { score, summary: '' }, assessed_at: null, replaced_at, replaced_by: 'x' })
  const series = historySeries(
    [entry(70, '2026-11-02T00:00:00Z'), entry(60, '2026-11-01T00:00:00Z'), { ...entry(Number.NaN, '2026-11-03T00:00:00Z') }], 82)
  assert.deepEqual(series.map(point => point.score), [60, 70, 82])
  assert.deepEqual(series.map(point => point.current), [false, false, true])
})

test('historySeries without a current score only returns history, and caps long histories', () => {
  const many = Array.from({ length: 30 }, (_, i) => ({ assessment: { score: i, summary: '' }, assessed_at: null, replaced_at: '2026-11-01T00:00:' + String(i).padStart(2, '0') + 'Z', replaced_by: 'x' }))
  const series = historySeries(many, null)
  assert.equal(series.length, 12)
  assert.equal(series[series.length - 1].score, 29)
  assert.deepEqual(historySeries([], null), [])
})

test('lastChange needs two points and reports latest, previous and delta', () => {
  assert.equal(lastChange([{ score: 50, at: null, current: true }]), null)
  assert.deepEqual(lastChange([{ score: 60, at: null, current: false }, { score: 82, at: null, current: true }]), { latest: 82, previous: 60, delta: 22 })
})
