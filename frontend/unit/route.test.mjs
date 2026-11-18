import test from 'node:test'
import assert from 'node:assert/strict'
import { parseRoute, detailHash } from '../.unit-build/route.js'

test('empty and unknown hashes open the job view', () => {
  for (const hash of ['', '#', '#lowongan', '#entah', 'lamaran']) {
    assert.deepEqual(parseRoute(hash), { view: 'lowongan' }, JSON.stringify(hash))
  }
})

test('#lamaran opens the application list', () => {
  assert.deepEqual(parseRoute('#lamaran'), { view: 'lamaran' })
})

test('a detail route carries both ids', () => {
  assert.deepEqual(parseRoute('#lamaran/job-1/app_2'), { view: 'detail', jobId: 'job-1', applicationId: 'app_2' })
  assert.deepEqual(
    parseRoute('#lamaran/3f2c9a10-1111-4222-8333-444455556666/aaaaaaaa-bbbb-4ccc-8ddd-eeeeffff0000'),
    { view: 'detail', jobId: '3f2c9a10-1111-4222-8333-444455556666', applicationId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeffff0000' },
  )
})

test('malformed or incomplete detail routes fall back to the list, never to a broken page', () => {
  const bad = ['#lamaran/job-1', '#lamaran/job-1/', '#lamaran//app', '#lamaran/../app', '#lamaran/a/b/c',
    '#lamaran/a b/c', '#lamaran/a/<script>', '#lamaran/' + 'x'.repeat(65) + '/y', '#lamaran/a/%2e%2e']
  for (const hash of bad) assert.deepEqual(parseRoute(hash), { view: 'lamaran' }, hash)
})

test('detailHash round-trips through parseRoute', () => {
  const hash = detailHash('11111111-aaaa', '22222222-bbbb')
  assert.equal(hash, '#lamaran/11111111-aaaa/22222222-bbbb')
  assert.deepEqual(parseRoute(hash), { view: 'detail', jobId: '11111111-aaaa', applicationId: '22222222-bbbb' })
})

test('detailHash refuses ids that could not be parsed back and returns the list hash', () => {
  assert.equal(detailHash('a b', 'c'), '#lamaran')
  assert.equal(detailHash('', 'c'), '#lamaran')
})
