import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, box, Field, grid, input, primary, secondary } from './TigFields'
import TigStaff from './TigStaff'
import { parseRoute } from './route'
import TigConfigForm, { cleanConfig } from './TigConfigForm'
import { emptyRegular, jsonOptions, tigRequest } from './tigTypes'
import type { Config } from './tigTypes'
import { Metric, PageHeading, Workspace } from './Workspace'

type Job = {
  id: string
  title: string
  status: 'DRAFT' | 'OPEN' | 'CLOSED'
  location: string | null
  employment_type: string | null
  application_count: number
}

const jobDraft = { title: '', location: '', employment_type: '' }

export default function App({ authToken, onLogout }: {
  authToken: string; onLogout: () => void
}) {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [editing, setEditing] = useState<'new' | 'edit' | null>(null)
  const [draft, setDraft] = useState(jobDraft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  const [config, setConfig] = useState<Config>({ published: false, regular: emptyRegular, program: [] })
  const [createdJob, setCreatedJob] = useState<Job | null>(null)
  const selected = jobs?.find(job => job.id === selectedId)
  // The detail page belongs to the "Lamaran" section of the sidebar.
  const view = route.view === 'lowongan' ? 'lowongan' : 'lamaran'
  const detailJobMissing = route.view === 'detail' && jobs !== null && !jobs.some(job => job.id === route.jobId)

  useEffect(() => {
    const navigate = () => {
      setRoute(parseRoute(window.location.hash))
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])

  // A detail link names its job: follow it once the jobs are known (the first job is only the default).
  // Adjusting state while rendering (guarded, so it settles in one extra pass) avoids an effect round trip.
  if (route.view === 'detail' && jobs?.some(job => job.id === route.jobId) && selectedId !== route.jobId) setSelectedId(route.jobId)

  useEffect(() => {
    const controller = new AbortController()
    tigRequest<Job[]>('/api/v1/jobs', {
      headers: { Authorization: 'Bearer ' + authToken }, signal: controller.signal,
    }).then(data => {
      setJobs(data)
      setSelectedId(data[0]?.id ?? '')
    }).catch(error => {
      if (!controller.signal.aborted) setError(error.message)
    })
    return () => controller.abort()
  }, [authToken])

  function edit() {
    if (!selected) return
    setEditing('edit')
    setDraft({ title: selected.title, location: selected.location ?? '', employment_type: selected.employment_type ?? '' })
    setError('')
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!editing || busy) return
    setBusy(true)
    setError('')
    const url = '/api/v1/jobs' + (editing === 'edit' ? '/' + selectedId : '')
    try {
      let saved = editing === 'new' && createdJob ? createdJob : await tigRequest<Job>(url, jsonOptions(editing === 'new' ? 'POST' : 'PATCH', draft, {
        Authorization: 'Bearer ' + authToken,
      }))
      if (editing === 'new') {
        // Keep the successful POST for config-only retries after partial failure.
        setCreatedJob(saved)
        const settings = await tigRequest<{ job_status: Job['status'] }>('/api/v1/jobs/' + saved.id + '/tig/config', jsonOptions('PUT', cleanConfig(config), {
          Authorization: 'Bearer ' + authToken,
        }))
        saved = { ...saved, status: settings.job_status }
      }
      setJobs(previous => previous?.some(job => job.id === saved.id)
        ? previous.map(job => job.id === saved.id ? saved : job) : [saved, ...(previous ?? [])])
      setSelectedId(saved.id)
      setEditing(null)
      setCreatedJob(null)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Lowongan belum tersimpan.')
    } finally {
      setBusy(false)
    }
  }

  return <Workspace role="Recruiter" title={route.view === 'detail' ? 'Detail skor' : 'Rekrutmen'} navigation={<>
    <a className={'nav-item' + (view === 'lowongan' ? ' active' : '')} aria-current={view === 'lowongan' ? 'page' : undefined} href="#lowongan"><span aria-hidden="true">▦</span> Lowongan</a>
    {selected && <a className={'nav-item' + (view === 'lamaran' ? ' active' : '')} aria-current={view === 'lamaran' ? 'page' : undefined} href="#lamaran"><span aria-hidden="true">≡</span> Lamaran terpilih</a>}
  </>} actions={<button type="button" onClick={onLogout} className={secondary}>Keluar</button>}>
    {route.view !== 'detail' && <PageHeading eyebrow="RECRUITMENT OVERVIEW" title="Dasbor rekrutmen" description="Kelola lowongan, tinjau lamaran, dan telusuri dasar penilaian dalam satu workspace." />}
    {view === 'lowongan' && jobs && <dl className="metrics-strip" aria-label="Ringkasan seluruh lowongan">
      <Metric label="Seluruh lowongan" value={jobs.length} description="Lowongan di workspace ini" />
      <Metric label="Lowongan terbuka" value={jobs.filter(job => job.status === 'OPEN').length} description="Status OPEN, seluruh lowongan" />
      <Metric label="Total lamaran" value={jobs.reduce((total, job) => total + job.application_count, 0)} description="Akumulasi seluruh lowongan" />
    </dl>}

    {error && <Alert>{error}</Alert>}
    {!jobs && !error && <p role="status">Memuat lowongan…</p>}
    {jobs && route.view !== 'detail' && <section id="lowongan" className={box + ' flex flex-wrap items-end gap-3'} aria-label="Lowongan TIG">
      <div className="min-w-0 flex-1 basis-56">
        <Field label="Lowongan TIG"><select value={selectedId} className={input} disabled={!jobs.length || busy || editing === 'new'} onChange={event => {
          setSelectedId(event.target.value)
          setEditing(null)
          setError('')
        }}>
          {!jobs.length && <option value="">Belum ada lowongan TIG</option>}
          {jobs.map(job => <option key={job.id} value={job.id}>{job.title}</option>)}
        </select></Field>
      </div>
      {view === 'lowongan' && selected && <button type="button" className={secondary} onClick={edit} disabled={busy || editing === 'new'}>Ubah lowongan</button>}
      {view === 'lowongan' && <button type="button" className={primary} disabled={busy || editing === 'new'} onClick={() => {
        setDraft(jobDraft)
        setConfig({ published: false, regular: emptyRegular, program: [] })
        setCreatedJob(null)
        setEditing('new')
        setError('')
      }}>Buat lowongan TIG</button>}
    </section>}

    <div hidden={view !== 'lowongan'}>
    {editing === 'new' && <TigConfigForm config={config} onChange={setConfig} onSave={save} busy={busy}
      saveLabel={createdJob ? 'Coba lagi simpan persyaratan' : 'Simpan lowongan dan persyaratan'}
      actions={<button type="button" className={secondary} disabled={busy || Boolean(createdJob)} onClick={() => setEditing(null)}>Batal</button>}>
      <h2 className="text-lg font-semibold">Buat lowongan TIG</h2>
      <p className="text-sm text-slate-600">Isi data lowongan dan persyaratan penilaian sebelum menyimpan.</p>
      {createdJob && <p role="status">Data lowongan sudah dibuat sebagai draf. Persyaratan belum tersimpan; coba lagi tanpa membuat lowongan baru.</p>}
      <fieldset disabled={busy || Boolean(createdJob)} className={grid}>
        <Field label="Nama lowongan (wajib)"><input className={input} required maxLength={160} value={draft.title}
          onChange={event => setDraft({ ...draft, title: event.target.value })} /></Field>
        <Field label="Lokasi"><input className={input} maxLength={220} value={draft.location}
          onChange={event => setDraft({ ...draft, location: event.target.value })} /></Field>
        <Field label="Jenis pekerjaan"><input className={input} maxLength={120} value={draft.employment_type}
          onChange={event => setDraft({ ...draft, employment_type: event.target.value })} /></Field>
      </fieldset>
    </TigConfigForm>}
    {editing === 'edit' && <form className={box + ' space-y-4'} onSubmit={save}>
      <h2 className="text-lg font-semibold">Ubah lowongan TIG</h2>
      <div className={grid}>
        <Field label="Nama lowongan (wajib)"><input className={input} required maxLength={160} value={draft.title}
          onChange={event => setDraft({ ...draft, title: event.target.value })} /></Field>
        <Field label="Lokasi"><input className={input} maxLength={220} value={draft.location}
          onChange={event => setDraft({ ...draft, location: event.target.value })} /></Field>
        <Field label="Jenis pekerjaan"><input className={input} maxLength={120} value={draft.employment_type}
          onChange={event => setDraft({ ...draft, employment_type: event.target.value })} /></Field>
      </div>
      <div className="flex flex-wrap gap-3">
        <button className={primary} disabled={busy}>{busy ? 'Menyimpan…' : 'Simpan lowongan'}</button>
        <button type="button" className={secondary} disabled={busy} onClick={() => setEditing(null)}>Batal</button>
      </div>
    </form>}

    </div>
    {selected && (editing === null || view === 'lamaran') && (route.view !== 'detail' || selected.id === route.jobId) &&
      <TigStaff key={selected.id} jobId={selected.id} title={selected.title} token={authToken}
        view={route.view === 'detail' ? 'detail' : view} applicationId={route.view === 'detail' ? route.applicationId : undefined} />}
    {detailJobMissing && <div className="sd-page">
      <a className="sd-back" href="#lamaran">← Kembali ke daftar lamaran</a>
      <Alert>Lowongan untuk lamaran ini tidak ditemukan di workspace Anda.</Alert>
    </div>}
    {jobs?.length === 0 && !editing && <p className={box + ' text-sm text-slate-600'}>
      Buat lowongan untuk mengatur formulir dan melihat lamaran.
    </p>}
  </Workspace>
}
