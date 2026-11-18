import test from 'node:test'
import assert from 'node:assert/strict'
import { mergePrefill } from '../.unit-build/prefillMerge.js'

const blankForm = () => ({
  full_name: 'Pelamar Uji', email: 'uji@example.com', phone: '',
  education: [{ level: null, campus: '', major: '', gpa: null }], experiences: [],
  projects: [], skills: [], languages: [], certifications: [], links: [],
  preferences: { expected_salary: null, domicile: '', work_modes: [], open_to_placement: null },
  priority: [], available_from: '',
})

const fromCv = () => ({
  full_name: 'Nama Dari CV', email: 'cv@example.com', phone: '0812 3456 7890',
  preferences: { domicile: 'Bandung, Indonesia' },
  education: [{ level: 'D4', campus: 'Politeknik Contoh', major: 'Teknik Informatika', gpa: 3.7 }],
  experiences: [{ title: 'Backend Developer', organization: 'PT Contoh', start: '2024-04', end: 'present', description: 'API' }],
  skills: ['PHP', 'Go'], languages: [], certifications: [], projects: ['Sistem Kasir — kasir restoran'],
  links: ['https://github.com/contoh', 'https://linkedin.com/in/contoh'],
})

test('professional links read from the CV fill the empty links field and are reported to the applicant', () => {
  const { next, changes } = mergePrefill(blankForm(), fromCv())
  assert.deepEqual(next.links, ['https://github.com/contoh', 'https://linkedin.com/in/contoh'])
  assert.ok(changes.includes('tautan (2)'), changes.join(', '))
})

test('links the applicant already typed are never replaced by the CV', () => {
  const form = { ...blankForm(), links: ['https://contoh.dev'] }
  assert.deepEqual(mergePrefill(form, fromCv()).next.links, ['https://contoh.dev'])
})

test('name and email the applicant already has are kept; phone, domicile, education and jobs come from the CV', () => {
  const { next, changes } = mergePrefill(blankForm(), fromCv())
  assert.equal(next.full_name, 'Pelamar Uji')
  assert.equal(next.email, 'uji@example.com')
  assert.equal(next.phone, '0812 3456 7890')
  assert.equal(next.preferences.domicile, 'Bandung, Indonesia')
  assert.equal(next.education[0].campus, 'Politeknik Contoh')
  assert.equal(next.experiences[0].end, 'Sekarang')
  assert.deepEqual(changes, ['telepon', 'pendidikan (1)', 'pengalaman (1)', 'proyek (1)', 'keahlian (2)', 'tautan (2)', 'domisili'])
})

test('a CV without education leaves one blank education row for the applicant to fill', () => {
  const { next } = mergePrefill(blankForm(), { skills: ['SQL'] })
  assert.equal(next.education.length, 1)
  assert.deepEqual(next.skills, ['SQL'])
})
