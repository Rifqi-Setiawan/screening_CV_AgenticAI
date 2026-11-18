import type { ReactNode } from 'react'
import { highestEducation, latestExperience } from './profile'
import type { Application } from './tigTypes'

const present = (value: string) => /^(present|sekarang|saat ini|kini)$/i.test(value.trim()) ? 'Sekarang' : value

function Item({ label, children }: { label: string; children: ReactNode }) {
  return <div className="sd-profile-item"><dt>{label}</dt><dd>{children || <span className="sd-sub">—</span>}</dd></div>
}

/** Everything the recruiter needs at a glance, taken from the applicant's own form. */
export default function ProfileCard({ form }: { form: Application }) {
  const school = highestEducation(form.education)
  const job = latestExperience(form.experiences)
  const salary = form.preferences.expected_salary
  const period = job ? [job.start, job.end].filter(Boolean).map(present).join(' – ') : ''
  return <section className="sd-card sd-span-12" aria-label="Profil pelamar">
    <div className="sd-card-head"><h2 className="sd-card-title">Profil pelamar</h2><span className="sd-sub">Data dari formulir yang dikirim pelamar</span></div>
    <dl className="sd-profile">
      <Item label="Nama lengkap"><strong>{form.full_name}</strong></Item>
      <Item label="Email">{form.email}</Item>
      <Item label="Telepon">{form.phone}</Item>
      <Item label="Domisili">{form.preferences.domicile}</Item>
      <Item label="Pendidikan tertinggi">{school && [school.level, school.campus, school.major, school.gpa !== null ? 'IPK ' + school.gpa : ''].filter(Boolean).join(' · ')}</Item>
      <Item label="Pengalaman terbaru">{job && [job.title, job.organization, period].filter(Boolean).join(' · ')}</Item>
      <Item label="Ekspektasi gaji">{salary ? 'Rp ' + salary.toLocaleString('id-ID') : ''}</Item>
      <Item label="Bisa mulai bekerja">{form.available_from}</Item>
      <Item label="Model kerja">{[form.preferences.work_modes.join(', '), form.preferences.open_to_placement === null ? '' : form.preferences.open_to_placement ? 'Bersedia ditempatkan' : 'Tidak bersedia ditempatkan'].filter(Boolean).join(' · ')}</Item>
      <Item label="Tautan">{form.links?.length ? form.links.length + ' tautan (lihat data formulir)' : ''}</Item>
    </dl>
  </section>
}
