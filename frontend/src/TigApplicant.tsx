import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Account } from './ApplicantPortal'
import { blankEducation, blankExperience, intakeProblems, normalizeEnd } from './intakeRules'
import { mergePrefill } from './prefillMerge'
import { Alert, box, CampusSuggestions, cleanLines, Field, grid, input, Lines, NumberField, Options, primary, secondary, sectionTitle } from './TigFields'
import { degrees, emptyApplication, jsonOptions, modes, RequestError, tigRequest } from './tigTypes'
import type { Application, Education, Experience } from './tigTypes'

type Job = { title: string; location: string | null; options: string[] }

const blankRow = (): Education => ({ level: null, campus: '', major: '', gpa: null })

export default function TigApplicant({ jobId, token, account, onAuthLost }: {
  jobId: string; token: string; account: Account; onAuthLost: () => void
}) {
  const endpoint = '/api/v1/tig/apply/' + encodeURIComponent(jobId)
  const auth = { Authorization: 'Bearer ' + token }
  const [job, setJob] = useState<Job | null>(null)
  const [form, setForm] = useState<Application>(() => ({
    ...emptyApplication, full_name: account.full_name, email: account.email, education: [blankRow()],
  }))
  const [error, setError] = useState('')
  const [problems, setProblems] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [filled, setFilled] = useState<string[]>([])
  const [cvDone, setCvDone] = useState(false)
  const [working, setWorking] = useState(false)
  const [receipt, setReceipt] = useState('')
  const [consent, setConsent] = useState(false)
  const [freshGraduate, setFreshGraduate] = useState(false)
  const problemsBox = useRef<HTMLDivElement>(null)

  function failed(error: unknown, fallback: string) {
    if (error instanceof RequestError && error.status === 401) onAuthLost()
    else setError(error instanceof Error ? error.message : fallback)
  }

  // Move focus to the list of problems once it is rendered, so screen readers announce it and keyboard users land on it.
  useEffect(() => {
    if (problems.length) problemsBox.current?.focus()
  }, [problems])

  useEffect(() => {
    const controller = new AbortController()
    tigRequest<Job>(endpoint, { signal: controller.signal }).then(setJob).catch(error => {
      if (!controller.signal.aborted) setError(error.message)
    })
    return () => controller.abort()
  }, [endpoint])

  const update = <K extends keyof Application>(key: K, value: Application[K]) => setForm(previous => ({ ...previous, [key]: value }))
  const education = (index: number, updateRow: Partial<Education>) => update('education',
    form.education.map((row, i) => i === index ? { ...row, ...updateRow } : row))
  const experience = (index: number, updateRow: Partial<Experience>) => update('experiences',
    form.experiences.map((row, i) => i === index ? { ...row, ...updateRow } : row))

  async function prefill(file: File) {
    setError('')
    setNotice('')
    setWorking(true)
    const body = new FormData()
    body.append('file', file)
    try {
      const result = await tigRequest<{ form: Partial<Application>; notice: string }>(endpoint + '/prefill', { method: 'POST', body, headers: auth })
      const { next, changes } = mergePrefill(form, result.form)
      setForm(next)
      setFilled(changes)
      setNotice(result.notice)
      setCvDone(true)
    } catch (error) {
      failed(error, 'CV gagal dibaca. Isi formulir secara manual.')
    } finally {
      setWorking(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    const found = intakeProblems(form, { consent, freshGraduate })
    setProblems(found)
    if (found.length) return
    setWorking(true)
    try {
      const experiences = form.experiences.filter(row => !blankExperience(row)).map(row => ({ ...row, end: normalizeEnd(row.end) }))
      const prepared = {
        ...form, projects: cleanLines(form.projects), skills: cleanLines(form.skills),
        languages: cleanLines(form.languages), certifications: cleanLines(form.certifications), links: cleanLines(form.links),
        education: form.education.filter(row => !blankEducation(row)), experiences,
        consent, fresh_graduate: freshGraduate && !experiences.length,
      }
      const result = await tigRequest<{ application_id: string }>(endpoint, jsonOptions('POST', prepared, auth))
      setReceipt(result.application_id)
      setForm(emptyApplication)
    } catch (error) {
      failed(error, 'Lamaran belum terkirim.')
    } finally {
      setWorking(false)
    }
  }

  return <div className="space-y-5">
    {job?.location && <p className="text-sm text-slate-600">Lokasi: {job.location}</p>}
    {error && <Alert>{error}</Alert>}
    {receipt ? <section className={box} role="status">
      <h2 className={sectionTitle}>Lamaran terkirim</h2>
      <p>Tim rekrutmen akan meninjau lamaran Anda. Referensi lamaran <strong>{receipt}</strong>.</p>
      <a className={secondary + ' mt-4 inline-block'} href="/pelamar">Pantau status lamaran</a>
    </section> : job ? <form className="space-y-5" onSubmit={submit} noValidate>
      <section className={box}>
        <h2 className={sectionTitle}>Langkah 1 · Unggah CV untuk isi otomatis (opsional)</h2>
        <p className="mb-3 text-sm text-slate-600">Unggah PDF atau Word. Sistem membaca teks CV dan mengisi kolom yang masih kosong. CV hasil scan atau gambar tidak terbaca, jadi isi formulir secara manual. File CV tidak disimpan.</p>
        <Field label="Pilih CV"><input className={input} type="file" accept=".pdf,.doc,.docx" disabled={working} onChange={event => {
          const file = event.currentTarget.files?.[0]
          if (file) void prefill(file)
          event.currentTarget.value = ''
        }} /></Field>
        {working && !cvDone && <p role="status" className="mt-3 text-sm text-slate-600">Membaca CV…</p>}
        {notice && <div role="status" className="mt-3 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900">
          <p>{notice}</p>
          {filled.length > 0 && <p className="mt-1">Terisi otomatis: {filled.join(', ')}.</p>}
        </div>}
      </section>
      <p className="px-1 text-sm font-semibold text-slate-700">Langkah 2 · Periksa dan lengkapi data diri Anda</p>
      <p className="px-1 text-sm text-slate-600">Isian bertanda <strong>(wajib)</strong> harus dilengkapi sebelum lamaran dapat dikirim. Isian lainnya opsional tetapi membantu penilaian.</p>
      {problems.length > 0 && <div ref={problemsBox} tabIndex={-1} role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
        <p className="font-semibold">Lengkapi {problems.length} hal berikut sebelum mengirim:</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">{problems.map((problem, index) => <li key={index}>{problem}</li>)}</ul>
      </div>}
      <section className={box}>
        <h2 className={sectionTitle}>Data diri</h2>
        <div className={grid}>
          <Field label="Nama lengkap (wajib)"><input className={input} autoComplete="name" required maxLength={160}
            value={form.full_name} onChange={event => update('full_name', event.target.value)} /></Field>
          <Field label="Email (wajib)"><input className={input} autoComplete="email" type="email" required maxLength={254}
            value={form.email} onChange={event => update('email', event.target.value)} /></Field>
          <Field label="Nomor telepon / WhatsApp (wajib)"><input className={input} autoComplete="tel" type="tel" required maxLength={32} placeholder="08xxxxxxxxxx"
            value={form.phone} onChange={event => update('phone', event.target.value)} /></Field>
          <Field label="Domisili, kota atau kabupaten (wajib)"><input className={input} autoComplete="address-level2" required maxLength={220}
            value={form.preferences.domicile} onChange={event => update('preferences', { ...form.preferences, domicile: event.target.value })} /></Field>
        </div>
      </section>
      <section className={box}>
        <h2 className={sectionTitle}>Pendidikan terakhir (wajib)</h2>
        <CampusSuggestions />
        {form.education.map((row, index) => <div key={index} className="mb-4 rounded-xl border border-slate-200 p-4">
          <div className={grid}>
            <Options label="Jenjang (wajib)" value={row.level} options={degrees} onChange={level => education(index, { level })} />
            <Field label="Sekolah atau kampus (wajib)"><input className={input} maxLength={220} list="tig-campus-suggestions" value={row.campus}
              onChange={event => education(index, { campus: event.target.value })} /></Field>
            <Field label="Jurusan (wajib)"><input className={input} maxLength={220} value={row.major}
              onChange={event => education(index, { major: event.target.value })} /></Field>
            <NumberField label="IPK, skala 4 (wajib untuk D3 ke atas)" value={row.gpa} max={4} step={0.001} onChange={gpa => education(index, { gpa })} />
          </div>
          <button className={secondary + ' mt-3'} type="button" disabled={form.education.length < 2}
            onClick={() => update('education', form.education.filter((_, i) => i !== index))}>Hapus pendidikan</button>
        </div>)}
        <button className={secondary} type="button" disabled={form.education.length >= 12} onClick={() =>
          update('education', [...form.education, blankRow()])}>Tambah pendidikan</button>
      </section>
      <section className={box}>
        <h2 className={sectionTitle}>Pengalaman dan proyek</h2>
        <label className="mb-4 flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" checked={freshGraduate} onChange={event => setFreshGraduate(event.target.checked)} />
          Saya belum memiliki pengalaman kerja (fresh graduate)
        </label>
        <p className="mb-3 text-sm text-slate-600">{freshGraduate ? 'Anda dapat tetap menambahkan magang atau pengalaman organisasi.' : 'Isi minimal satu pengalaman kerja, atau centang pilihan di atas.'}</p>
        {form.experiences.map((row, index) => <div key={index} className="mb-4 rounded-xl border border-slate-200 p-4">
          <div className={grid}>
            {([['title', 'Posisi (wajib)'], ['organization', 'Organisasi (wajib)'], ['start', 'Mulai (wajib)'], ['end', 'Selesai (tulis Sekarang jika masih bekerja)']] as const).map(([key, label]) =>
              <Field label={label} key={key}><input className={input} maxLength={220} value={row[key]}
                onChange={event => experience(index, { [key]: event.target.value })} /></Field>)}
          </div>
          <div className="my-3"><Field label="Tanggung jawab dan pencapaian"><textarea className={input} maxLength={1800} rows={3}
            value={row.description} onChange={event => experience(index, { description: event.target.value })} /></Field></div>
          <button className={secondary} type="button"
            onClick={() => update('experiences', form.experiences.filter((_, i) => i !== index))}>Hapus pengalaman</button>
        </div>)}
        <button className={secondary + ' mb-4'} type="button" disabled={form.experiences.length >= 20} onClick={() =>
          update('experiences', [...form.experiences, { title: '', organization: '', start: '', end: '', description: '' }])}>Tambah pengalaman</button>
        <Lines label="Proyek relevan" values={form.projects} onChange={values => update('projects', values)} maxLength={12000} />
      </section>
      <section className={box}>
        <h2 className={sectionTitle}>Kompetensi dan tautan</h2>
        <div className={grid}>
          <Lines label="Keahlian (wajib, minimal satu)" values={form.skills} onChange={values => update('skills', values)} maxLength={4000} />
          <Lines label="Bahasa dan tingkat kemampuan" values={form.languages} onChange={values => update('languages', values)} maxLength={1500} />
          <Lines label="Sertifikasi, termasuk bahasa" values={form.certifications} onChange={values => update('certifications', values)} maxLength={3000} />
          <Lines label="Tautan profesional (opsional): LinkedIn, portofolio, GitHub" values={form.links} onChange={values => update('links', values)} maxLength={1500} />
        </div>
      </section>
      <section className={box}>
        <h2 className={sectionTitle}>Preferensi kerja</h2>
        <div className={grid}>
          <NumberField label="Ekspektasi gaji bulanan, Rp (wajib)" value={form.preferences.expected_salary} max={1e10}
            onChange={expected_salary => update('preferences', { ...form.preferences, expected_salary })} />
          <Field label="Tanggal bisa mulai bekerja (opsional)"><input className={input} maxLength={60} placeholder="Contoh: Segera, atau 1 Januari 2027"
            value={form.available_from} onChange={event => update('available_from', event.target.value)} /></Field>
          <Options label="Bersedia ditempatkan" options={['Ya', 'Tidak'] as const}
            value={form.preferences.open_to_placement === null ? null : form.preferences.open_to_placement ? 'Ya' : 'Tidak'}
            onChange={value => update('preferences', { ...form.preferences, open_to_placement: value === null ? null : value === 'Ya' })} />
          <fieldset className="space-y-2"><legend className="text-sm font-medium text-slate-700">Model kerja yang diminati</legend>
            <div className="flex flex-wrap gap-4 text-sm">{modes.map(mode => <label key={mode} className="flex items-center gap-2">
              <input type="checkbox" checked={form.preferences.work_modes.includes(mode)} onChange={event =>
                update('preferences', { ...form.preferences, work_modes: event.target.checked
                  ? [...form.preferences.work_modes, mode] : form.preferences.work_modes.filter(value => value !== mode) })} />
              {mode}</label>)}</div>
          </fieldset>
        </div>
      </section>
      {job.options.length > 0 && <section className={box}>
        <h2 className={sectionTitle}>Prioritas posisi (opsional)</h2>
        <p className="mb-3 text-sm text-slate-600">Tambahkan posisi sesuai urutan pilihan. Jika dikosongkan, dua posisi dengan skor tertinggi menjadi prioritas.</p>
        <ol className="mb-3 list-decimal space-y-2 pl-5">{form.priority.map((position, index) =>
          <li key={position}>{position} <button type="button" className={secondary + ' ml-2'}
            onClick={() => update('priority', form.priority.filter((_, i) => i !== index))}>Hapus pilihan</button></li>)}</ol>
        <Options label="Tambahkan posisi" value={null} options={job.options.filter(option => !form.priority.includes(option))}
          onChange={option => { if (option) update('priority', [...form.priority, option]) }} />
      </section>}
      <section className={box + ' space-y-4'}>
        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input type="checkbox" className="mt-1" checked={consent} onChange={event => setConsent(event.target.checked)} />
          <span><strong>(wajib)</strong> Saya menyetujui data pribadi saya diproses oleh tim rekrutmen untuk keperluan seleksi lowongan ini, sesuai Undang-Undang Pelindungan Data Pribadi, dan menyatakan bahwa data yang saya isi benar.</span>
        </label>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="max-w-xl text-sm text-slate-600">Saat dikirim, AI menilai kecocokan berdasarkan isian formulir ini, bukan file CV. Nama dan kontak digunakan untuk administrasi rekrutmen. Keputusan selanjutnya dibuat oleh tim rekrutmen.</p>
          <button className={primary} disabled={working}>{working ? 'Memproses…' : 'Kirim lamaran'}</button>
        </div>
      </section>
    </form> : !error && <p role="status">Memuat lowongan…</p>}
  </div>
}
