import type { Application, Education, Experience } from './tigTypes.ts'

// Required fields for a professional application. These mirror the server rules (ApplicationSubmission in
// src/domain/tig.py) so the applicant sees every problem at once, in Indonesian, before anything is sent.

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const phonePattern = /^[+0-9][0-9 ().-]{5,31}$/
const linkPattern = /^https?:\/\/\S+$/i
const degreesWithGpa = ['D3', 'D4', 'S1', 'S2', 'S3']

export type IntakeFlags = { consent: boolean; freshGraduate: boolean }

export const blankEducation = (row: Education) => !row.level && !row.campus.trim() && !row.major.trim() && row.gpa === null
export const blankExperience = (row: Experience) => ![row.title, row.organization, row.start, row.end, row.description].some(value => value.trim())

export function intakeProblems(form: Application, flags: IntakeFlags): string[] {
  const problems: string[] = []
  if (!form.full_name.trim()) problems.push('Nama lengkap wajib diisi.')
  const email = form.email.trim()
  if (!email) problems.push('Email wajib diisi.')
  else if (!emailPattern.test(email)) problems.push('Format email tidak valid.')
  const phone = form.phone.trim()
  if (!phone) problems.push('Nomor telepon wajib diisi.')
  else if (!phonePattern.test(phone)) problems.push('Format nomor telepon tidak valid (angka, spasi, +, tanda kurung, atau strip).')
  if (!form.preferences.domicile.trim()) problems.push('Domisili wajib diisi.')

  const education = form.education.filter(row => !blankEducation(row))
  if (!education.length) problems.push('Pendidikan terakhir wajib diisi (jenjang, sekolah atau kampus, dan jurusan).')
  education.forEach((row, index) => {
    const missing = [!row.level && 'jenjang', !row.campus.trim() && 'sekolah atau kampus', !row.major.trim() && 'jurusan'].filter(Boolean)
    if (missing.length) problems.push('Pendidikan #' + (index + 1) + ': ' + missing.join(', ') + ' wajib diisi.')
    if (row.level && degreesWithGpa.includes(row.level) && row.gpa === null) {
      problems.push('Pendidikan #' + (index + 1) + ': IPK wajib diisi untuk jenjang ' + row.level + '.')
    }
  })

  if (!form.skills.some(skill => skill.trim())) problems.push('Minimal satu keahlian wajib diisi.')

  const experiences = form.experiences.filter(row => !blankExperience(row))
  if (!experiences.length && !flags.freshGraduate) {
    problems.push('Isi minimal satu pengalaman kerja, atau centang bahwa Anda belum berpengalaman.')
  }
  experiences.forEach((row, index) => {
    const missing = [!row.title.trim() && 'posisi', !row.organization.trim() && 'organisasi', !row.start.trim() && 'tanggal mulai'].filter(Boolean)
    if (missing.length) problems.push('Pengalaman #' + (index + 1) + ': ' + missing.join(', ') + ' wajib diisi.')
  })

  if (!form.preferences.expected_salary) problems.push('Ekspektasi gaji bulanan wajib diisi.')
  form.links.map(link => link.trim()).filter(Boolean).forEach(link => {
    if (!linkPattern.test(link)) problems.push('Tautan "' + link.slice(0, 60) + '" harus diawali http:// atau https:// dan tanpa spasi.')
  })
  if (!flags.consent) problems.push('Persetujuan pemrosesan data pribadi wajib dicentang.')
  return problems
}
