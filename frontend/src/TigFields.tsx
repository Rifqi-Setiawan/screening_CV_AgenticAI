import type { ReactNode } from 'react'

export const box = 'panel'
export const grid = 'grid gap-4 sm:grid-cols-2'
export const input = 'form-input'
export const primary = 'button button-primary'
export const secondary = 'button button-secondary'
export const sectionTitle = 'mb-4 text-lg font-semibold text-slate-950'

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block min-w-0 space-y-1.5 text-sm font-medium text-slate-700">
    <span>{label}</span>{children}
  </label>
}

export function Lines({ label, values, onChange, maxLength }: {
  label: string; values: string[]; onChange: (values: string[]) => void; maxLength?: number
}) {
  // Keep trailing newlines while typing. Empty lines are removed before submit.
  return <Field label={label}>
    <textarea className={input} value={values.join('\n')} maxLength={maxLength}
      onChange={event => onChange(event.target.value.split('\n'))} rows={3} placeholder="Satu isian per baris" />
  </Field>
}

export function NumberField({ label, value, onChange, min = 0, max, step = 1 }: {
  label: string; value: number | null; onChange: (value: number | null) => void; min?: number; max?: number; step?: number
}) {
  return <Field label={label}><input className={input} type="number" min={min} max={max} step={step}
    value={value ?? ''} onChange={event => onChange(event.target.value === '' ? null : Number(event.target.value))} /></Field>
}

export function Options<T extends string>({ label, value, options, onChange, empty = 'Pilih' }: {
  label: string; value: T | null; options: readonly T[]; onChange: (value: T | null) => void; empty?: string
}) {
  return <Field label={label}><select className={input} value={value ?? ''} onChange={event => {
    const chosen = options.find(option => option === event.target.value)
    onChange(chosen ?? null)
  }}>
    <option value="">{empty}</option>
    {options.map(option => <option key={option}>{option}</option>)}
  </select></Field>
}

export function Alert({ children }: { children: ReactNode }) {
  return <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">{children}</div>
}

export function cleanLines(values: string[]) { return values.map(value => value.trim()).filter(Boolean) }

const campuses = [
  ['Universitas Indonesia', 'UI'], ['Universitas Gadjah Mada', 'UGM'],
  ['Institut Teknologi Bandung', 'ITB'], ['Institut Teknologi Sepuluh Nopember', 'ITS'],
  ['IPB University', 'IPB'], ['Universitas Airlangga', 'UNAIR'], ['Universitas Padjadjaran', 'UNPAD'],
  ['Universitas Diponegoro', 'UNDIP'], ['Universitas Brawijaya', 'UB'],
  ['Universitas Negeri Jakarta', 'UNJ'], ['Universitas Pendidikan Indonesia', 'UPI'],
  ['Universitas Negeri Yogyakarta', 'UNY'],
]

export function CampusSuggestions() {
  return <datalist id="tig-campus-suggestions">
    {campuses.map(([campus, alias]) => <option key={campus} value={campus}>{alias}</option>)}
  </datalist>
}
