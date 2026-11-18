import type { Application } from './tigTypes'

export default function FormSummary({ form }: { form: Application }) {
  return <div className="form-summary space-y-5 text-sm">
    <p><strong>{form.full_name}</strong> · {form.email}{form.phone && ' · ' + form.phone}</p>
    {form.education.length > 0 && <div><strong>Pendidikan</strong><ul className="list-disc pl-5">
      {form.education.map((row, index) => <li key={index}>{[row.level, row.campus, row.major, row.gpa !== null ? 'IPK ' + row.gpa : null].filter(Boolean).join(' · ')}</li>)}
    </ul></div>}
    {form.experiences.length > 0 && <div><strong>Pengalaman</strong><ul className="list-disc pl-5">
      {form.experiences.map((row, index) => <li key={index}>{[row.title, row.organization, [row.start, row.end].filter(Boolean).join('–')].filter(Boolean).join(' · ')}
        {row.description && <p className="whitespace-pre-wrap text-slate-600">{row.description}</p>}</li>)}
    </ul></div>}
    {([['projects', 'Proyek'], ['skills', 'Keahlian'], ['languages', 'Bahasa'], ['certifications', 'Sertifikasi'], ['priority', 'Pilihan pelamar']] as const)
      .map(([key, label]) => form[key].length > 0 && <p key={key}><strong>{label}</strong> · {form[key].join(', ')}</p>)}
    <p><strong>Preferensi kerja</strong> · {[
      form.preferences.domicile, form.preferences.work_modes.join(', '),
      form.preferences.expected_salary === null ? null : 'Rp ' + form.preferences.expected_salary.toLocaleString('id-ID'),
      form.preferences.open_to_placement === null ? null : form.preferences.open_to_placement ? 'Bersedia ditempatkan' : 'Tidak bersedia ditempatkan',
    ].filter(Boolean).join(' · ') || 'Belum diisi'}</p>
  </div>
}
