import { summaryLists } from './profile'
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
    {summaryLists(form).map(({ label, items, layout }) => layout === 'bullets'
      ? <div key={label}><strong>{label}</strong><ul className="list-disc pl-5">{items.map((item, index) => <li key={index} className="whitespace-pre-wrap">{item}</li>)}</ul></div>
      : <p key={label}><strong>{label}</strong> · {items.join(', ')}</p>)}
    <p><strong>Preferensi kerja</strong> · {[
      form.preferences.domicile, form.preferences.work_modes.join(', '),
      form.preferences.expected_salary === null ? null : 'Rp ' + form.preferences.expected_salary.toLocaleString('id-ID'),
      form.preferences.open_to_placement === null ? null : form.preferences.open_to_placement ? 'Bersedia ditempatkan' : 'Tidak bersedia ditempatkan',
    ].filter(Boolean).join(' · ') || 'Belum diisi'}</p>
    {form.available_from && <p><strong>Bisa mulai bekerja</strong> · {form.available_from}</p>}
    {!!form.links?.length && <div><strong>Tautan</strong><ul className="list-disc pl-5">
      {form.links.map((link, index) => <li key={index}><a className="break-all text-indigo-700 underline" href={link} target="_blank" rel="noopener noreferrer nofollow">{link}</a></li>)}
    </ul></div>}
    {form.consent_at && <p className="text-slate-600"><strong>Persetujuan data pribadi</strong> · {new Date(form.consent_at).toLocaleString('id-ID')}</p>}
  </div>
}
