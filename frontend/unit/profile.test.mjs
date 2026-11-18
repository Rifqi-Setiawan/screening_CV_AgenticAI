import test from 'node:test'
import assert from 'node:assert/strict'
import { highestEducation, latestExperience } from '../.unit-build/profile.js'

const edu = (level, campus = 'Kampus', major = 'Jurusan', gpa = null) => ({ level, campus, major, gpa })
const exp = (title, start, end, organization = 'PT Contoh') => ({ title, organization, start, end, description: '' })

test('highestEducation picks the highest degree regardless of order and ignores blank rows', () => {
  assert.equal(highestEducation([edu('SMA/SMK'), edu('S2'), edu('S1')]).level, 'S2')
  assert.equal(highestEducation([edu(null, '', ''), edu('D3')]).level, 'D3')
  assert.equal(highestEducation([edu('S1', 'A'), edu('S1', 'B')]).campus, 'A')
  assert.equal(highestEducation([]), null)
  assert.equal(highestEducation([edu(null, '', '')]), null)
})

test('highestEducation keeps a row that has only a campus when no level is known', () => {
  assert.equal(highestEducation([edu(null, 'UB Malang', '')]).campus, 'UB Malang')
})

test('latestExperience prefers a current job, then the latest end, then the first listed', () => {
  assert.equal(latestExperience([exp('A', '2020', '2022'), exp('B', '2023-01', 'present')]).title, 'B')
  assert.equal(latestExperience([exp('A', '2018', '2020'), exp('B', '2020', '2023')]).title, 'B')
  assert.equal(latestExperience([exp('A', '', ''), exp('B', '', '')]).title, 'A')
  assert.equal(latestExperience([exp('X', '2024', 'Sekarang'), exp('Y', '2025-02', '2025-12')]).title, 'X')
  assert.equal(latestExperience([]), null)
  assert.equal(latestExperience([{ title: '', organization: '', start: '', end: '', description: '' }]), null)
})
