import { blankEducation, blankExperience, shownEnd } from './intakeRules.ts'
import type { Application, Education, Experience } from './tigTypes.ts'

// Fields read from the CV that hold a list of entries (one per row or line).
export const listFields = [
  ['education', 'pendidikan'], ['experiences', 'pengalaman'], ['projects', 'proyek'], ['skills', 'keahlian'],
  ['languages', 'bahasa'], ['certifications', 'sertifikasi'], ['links', 'tautan'],
] as const

type ListField = typeof listFields[number][0]

const blankRow = (): Education => ({ level: null, campus: '', major: '', gpa: null })

// A field counts as empty when it only holds blank rows, so the single empty education row does not block prefill.
function isEmpty(form: Application, field: ListField) {
  if (field === 'education') return form.education.every(blankEducation)
  if (field === 'experiences') return form.experiences.every(blankExperience)
  return form[field].every(value => !value.trim())
}

// Only empty fields are filled, so anything the applicant already typed is kept.
export function mergePrefill(form: Application, result: Partial<Application>): { next: Application; changes: string[] } {
  const changes: string[] = []
  const next = { ...form }
  for (const [field, label] of [['full_name', 'nama'], ['email', 'email'], ['phone', 'telepon']] as const) {
    if (!form[field] && result[field]) {
      next[field] = result[field]
      changes.push(label)
    }
  }
  for (const [field, label] of listFields) {
    const values = result[field]
    if (isEmpty(form, field) && values?.length) {
      const shown = field === 'experiences' ? (values as Experience[]).map(row => ({ ...row, end: shownEnd(row.end) })) : values
      Object.assign(next, { [field]: shown })
      changes.push(label + ' (' + values.length + ')')
    }
  }
  if (!form.preferences.domicile && result.preferences?.domicile) {
    next.preferences = { ...form.preferences, domicile: result.preferences.domicile }
    changes.push('domisili')
  }
  if (!next.education.length) next.education = [blankRow()]
  return { next, changes }
}
