import type { FormEvent, ReactNode } from 'react'
import { box, CampusSuggestions, cleanLines, Field, grid, input, Lines, NumberField, Options, primary, secondary, sectionTitle } from './TigFields'
import { categories, degrees, emptyPosition, emptyRegular, modes } from './tigTypes'
import type { Category, Config, PositionSummary, Regular } from './tigTypes'

function SummaryFields({ position, update }: { position: PositionSummary; update: (patch: Partial<PositionSummary>) => void }) {
  return <div className={grid}>
    <Options label="Pendidikan minimum" value={position.education_minimum} options={degrees} empty="Semua jenjang"
      onChange={education_minimum => update({ education_minimum })} />
    <NumberField label="IPK minimum (skala 4)" value={position.gpa_minimum} max={4} step={0.001}
      onChange={gpa_minimum => update({ gpa_minimum })} />
    <Lines label="Jurusan yang direkomendasikan" values={position.majors} onChange={majors => update({ majors })} maxLength={3000} />
    <Lines label="Kompetensi kunci" values={position.skills} onChange={skills => update({ skills })} maxLength={5000} />
    <div className="sm:col-span-2"><Field label="Kualifikasi"><textarea className={input} value={position.qualifications} rows={3} maxLength={1800}
      onChange={event => update({ qualifications: event.target.value })} /></Field></div>
  </div>
}

export function cleanConfig(config: Config): Config {
  return {
    ...config,
    regular: config.regular ? {
      ...config.regular, majors: cleanLines(config.regular.majors), skills: cleanLines(config.regular.skills),
      campus_tiers: config.regular.campus_tiers.map(row => ({ ...row, aliases: cleanLines(row.aliases) })),
    } : null,
    program: config.program.map(option => ({ ...option, majors: cleanLines(option.majors), skills: cleanLines(option.skills) })),
  }
}

export default function TigConfigForm({ config, onChange, onSave, busy, children, actions, saveLabel = 'Simpan aturan' }: {
  config: Config; onChange: (config: Config) => void; onSave: (event: FormEvent) => void; busy: boolean
  children?: ReactNode; actions?: ReactNode; saveLabel?: string
}) {
  const regular = config.regular
  const updateRegular = (patch: Partial<Regular>) => {
    if (regular) onChange({ ...config, regular: { ...regular, ...patch } })
  }
  const weightTotal = regular ? Object.values(regular.weights).reduce((sum, value) => sum + value, 0) : 0
  const campusUpdate = (index: number, patch: Partial<Regular['campus_tiers'][number]>) => {
    if (regular) updateRegular({ campus_tiers: regular.campus_tiers.map((row, i) => i === index ? { ...row, ...patch } : row) })
  }

  return <form className={box + ' space-y-5'} onSubmit={onSave}>
    {children}
    <fieldset disabled={busy} className="min-w-0 space-y-5">
    <h2 className={sectionTitle}>Aturan penilaian posisi</h2>
    <Options label="Jenis lowongan" value={regular ? 'Reguler' : 'Program / gabungan'} options={['Reguler', 'Program / gabungan'] as const}
      onChange={value => {
        if (value === 'Reguler' && !regular) onChange({ ...config, regular: emptyRegular, program: [] })
        else if (value === 'Program / gabungan' && regular) {
          onChange({ ...config, regular: null, program: [{ ...emptyPosition, title: '' }, { ...emptyPosition, title: '' }] })
        }
      }} />
    {regular ? <>
      <SummaryFields position={regular} update={updateRegular} />
      <Field label="Pengalaman yang dibutuhkan"><textarea className={input} rows={3} maxLength={1800}
        value={regular.experience} onChange={event => updateRegular({ experience: event.target.value })} /></Field>
      <div className={grid}>
        <Field label="Lokasi kerja"><input className={input} value={regular.location} maxLength={220}
          onChange={event => updateRegular({ location: event.target.value })} /></Field>
        <Options label="Model kerja" value={regular.work_mode} options={modes} empty="Belum ditetapkan"
          onChange={work_mode => updateRegular({ work_mode })} />
        <NumberField label="Gaji minimum bulanan (Rp)" value={regular.salary_minimum} max={1e10}
          onChange={salary_minimum => updateRegular({ salary_minimum })} />
        <NumberField label="Gaji maksimum bulanan (Rp)" value={regular.salary_maximum} max={1e10}
          onChange={salary_maximum => updateRegular({ salary_maximum })} />
      </div>
      <fieldset className="space-y-3 rounded-xl border border-slate-200 p-4">
        <legend className="px-2 font-semibold text-slate-800">Bobot kategori</legend>
        <div className={grid}>{(Object.entries(categories) as [Category, string][]).map(([key, label]) =>
          <NumberField key={key} label={label + ' (%)'} value={regular.weights[key]} max={100}
            onChange={value => updateRegular({ weights: { ...regular.weights, [key]: value ?? 0 } })} />)}</div>
        <p className={weightTotal === 100 ? 'text-sm text-emerald-800' : 'text-sm text-rose-800'}>Total bobot {weightTotal}%. Total wajib 100%.</p>
      </fieldset>
      <fieldset className="space-y-3 rounded-xl border border-slate-200 p-4">
        <legend className="px-2 font-semibold text-slate-800">Target pendidikan dan tier kampus</legend>
        <CampusSuggestions />
        <p className="text-sm text-slate-600">Nama kampus hanya dipertimbangkan ketika daftar tier diisi. Kampus di luar daftar tetap dinilai berdasarkan jenjang, jurusan, dan IPK.</p>
        {regular.campus_tiers.map((row, index) => <div key={index} className="space-y-3 rounded-lg bg-slate-50 p-3">
          <div className={grid}>
            <Field label="Nama kampus"><input className={input} list="tig-campus-suggestions" required maxLength={220} value={row.campus}
              onChange={event => campusUpdate(index, { campus: event.target.value })} /></Field>
            <Options label="Tier" value={String(row.tier) as '1' | '2' | '3'} options={['1', '2', '3'] as const} onChange={value => {
              if (value) campusUpdate(index, { tier: Number(value) as 1 | 2 | 3 })
            }} />
          </div>
          <Lines label="Nama lain atau singkatan" values={row.aliases} onChange={aliases => campusUpdate(index, { aliases })} maxLength={1500} />
          <button className={secondary} type="button" onClick={() =>
            updateRegular({ campus_tiers: regular.campus_tiers.filter((_, i) => i !== index) })}>Hapus kampus</button>
        </div>)}
        <button className={secondary} type="button" disabled={regular.campus_tiers.length >= 100} onClick={() =>
          updateRegular({ campus_tiers: [...regular.campus_tiers, { campus: '', tier: 1, aliases: [] }] })}>Tambah kampus</button>
      </fieldset>
    </> : <div className="space-y-4">
      <p className="text-sm text-slate-600">Program memerlukan sedikitnya dua posisi. AI menilai setiap opsi dari ringkasan persyaratan masing-masing.</p>
      {config.program.map((position, index) => {
        const update = (patch: Partial<typeof position>) => onChange({
          ...config, program: config.program.map((row, i) => i === index ? { ...row, ...patch } : row),
        })
        return <fieldset className="space-y-3 rounded-xl border border-slate-200 p-4" key={index}>
          <legend className="px-2 font-semibold text-slate-800">Opsi {index + 1}</legend>
          <Field label="Nama posisi"><input className={input} value={position.title} required maxLength={160}
            onChange={event => update({ title: event.target.value })} /></Field>
          <SummaryFields position={position} update={update} />
          <button className={secondary} type="button" disabled={config.program.length <= 2} onClick={() =>
            onChange({ ...config, program: config.program.filter((_, i) => i !== index) })}>Hapus opsi</button>
        </fieldset>
      })}
      <button className={secondary} type="button" disabled={config.program.length >= 12} onClick={() =>
        onChange({ ...config, program: [...config.program, { ...emptyPosition, title: '' }] })}>Tambah opsi</button>
    </div>}
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
      <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <input type="checkbox" checked={config.published} onChange={event => onChange({ ...config, published: event.target.checked })} />
        Buka formulir untuk pelamar
      </label>
      <button className={primary} disabled={busy || Boolean(regular && weightTotal !== 100)}>
        {busy ? 'Menyimpan…' : saveLabel}
      </button>
      {actions}
    </div>
    </fieldset>
  </form>
}
