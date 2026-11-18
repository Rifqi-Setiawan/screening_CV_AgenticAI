import test from 'node:test'
import assert from 'node:assert/strict'
import { blankEducation, blankExperience, intakeProblems } from '../.unit-build/intakeRules.js'

// Mirrors tests/test_tig_intake_rules.py on the server: the form must catch the same problems before submit.
const valid = () => ({
  full_name: 'Budi Contoh', email: 'budi.contoh@example.test', phone: '0812 3456 7890',
  education: [{ level: 'S1', campus: 'Universitas Contoh', major: 'Statistika', gpa: 3.5 }],
  experiences: [{ title: 'Data Analyst', organization: 'PT Contoh Maju', start: '2023-01', end: '', description: '' }],
  projects: [], skills: ['SQL'], languages: [], certifications: [],
  preferences: { expected_salary: 9000000, domicile: 'Jakarta', work_modes: [], open_to_placement: null },
  priority: [], links: [], available_from: '',
})
const flags = { consent: true, freshGraduate: false }
const text = (form, f = flags) => intakeProblems(form, f).join(' ').toLowerCase()

test('a complete form has no problems', () => {
  assert.deepEqual(intakeProblems(valid(), flags), [])
})

test('each required field is reported in Indonesian', () => {
  const cases = [
    [f => { f.full_name = ' ' }, 'nama lengkap'], [f => { f.email = '' }, 'email wajib'], [f => { f.email = 'bukan-email' }, 'format email'],
    [f => { f.phone = '' }, 'nomor telepon wajib'], [f => { f.phone = 'abc' }, 'format nomor telepon'],
    [f => { f.preferences.domicile = '' }, 'domisili'], [f => { f.education = [] }, 'pendidikan terakhir'],
    [f => { f.skills = ['  ', ''] }, 'keahlian'], [f => { f.experiences = [] }, 'pengalaman'],
    [f => { f.preferences.expected_salary = null }, 'ekspektasi gaji'], [f => { f.preferences.expected_salary = 0 }, 'ekspektasi gaji'],
  ]
  for (const [change, expected] of cases) {
    const form = valid(); change(form)
    assert.ok(text(form).includes(expected), expected)
  }
  assert.ok(text(valid(), { consent: false, freshGraduate: false }).includes('persetujuan'))
})

test('problems are reported together', () => {
  const form = valid(); form.phone = ''; form.skills = []; form.education = []
  assert.ok(intakeProblems(form, { consent: false, freshGraduate: false }).length >= 4)
})

test('every filled education row needs level, campus, major and a GPA from D3 upwards; blank rows are ignored', () => {
  const form = valid()
  form.education = [{ level: 'S1', campus: 'Universitas Contoh', major: 'Statistika', gpa: null }, { level: null, campus: '', major: '', gpa: null }]
  assert.ok(text(form).includes('ipk'))
  form.education = [{ level: null, campus: 'Universitas Contoh', major: 'Statistika', gpa: 3.5 }]
  assert.ok(text(form).includes('jenjang'))
  form.education = [{ level: 'SMA/SMK', campus: 'SMAN 1 Contoh', major: 'IPA', gpa: null }]
  assert.deepEqual(intakeProblems(form, flags), [])
})

test('no experience is fine only with the fresh-graduate declaration; a listed experience needs title, organisation and start', () => {
  const form = valid(); form.experiences = []
  assert.ok(text(form).includes('pengalaman'))
  assert.deepEqual(intakeProblems(form, { consent: true, freshGraduate: true }), [])
  form.experiences = [{ title: '', organization: 'PT Contoh', start: '2023', end: '', description: '' }]
  assert.ok(text(form).includes('posisi'))
  form.experiences = [{ title: 'Analis', organization: '', start: '', end: '', description: '' }]
  assert.ok(text(form).includes('organisasi') && text(form).includes('mulai'))
})

test('links must be plain http(s) urls; blank link lines are ignored', () => {
  const form = valid(); form.links = ['', 'https://www.linkedin.com/in/budi-contoh']
  assert.deepEqual(intakeProblems(form, flags), [])
  for (const bad of ['javascript:alert(1)', 'linkedin.com/in/budi', 'ftp://example.test/x', 'https://a b.example.test']) {
    form.links = [bad]
    assert.ok(text(form).includes('tautan'), bad)
  }
})

test('blank-row helpers', () => {
  assert.equal(blankEducation({ level: null, campus: ' ', major: '', gpa: null }), true)
  assert.equal(blankEducation({ level: 'S1', campus: '', major: '', gpa: null }), false)
  assert.equal(blankExperience({ title: '', organization: ' ', start: '', end: '', description: '' }), true)
  assert.equal(blankExperience({ title: 'x', organization: '', start: '', end: '', description: '' }), false)
})
