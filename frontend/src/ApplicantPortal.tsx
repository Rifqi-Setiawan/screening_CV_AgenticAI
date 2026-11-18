import { useCallback, useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Alert, box, Field, input, primary, secondary, sectionTitle } from './TigFields'
import TigApplicant from './TigApplicant'
import { jsonOptions, RequestError, tigRequest } from './tigTypes'
import { AuthLayout, PageHeading, Workspace } from './Workspace'

export type Account = { id: string; email: string; full_name: string }
type Opening = { id: string; title: string; location: string | null; employment_type: string | null }
type MyApplication = { id: string; job_id: string; title: string; stage: string; created_at: string }

const tokenKey = 'tig_applicant_token'

function readToken() {
  try { return localStorage.getItem(tokenKey) } catch { return null }
}

function writeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(tokenKey, token)
    else localStorage.removeItem(tokenKey)
  } catch { /* The session still works for this page without storage. */ }
}

function Shell({ account, onLogout, title, children }: {
  account: Account | null; onLogout?: () => void; title: string; children: ReactNode
}) {
  if (!account) return <AuthLayout><div className="auth-form"><PageHeading eyebrow="AKUN PELAMAR" title={title} description="Langkah berikutnya dimulai dari profil Anda." />{children}</div></AuthLayout>
  return <Workspace role="Pelamar" title="Portal pelamar" navigation={<a className="nav-item active" href="/pelamar">Lowongan & lamaran saya</a>}
    actions={<><span className="account-name">{account.full_name}</span><button type="button" onClick={onLogout} className={secondary}>Keluar</button></>}>
    <PageHeading eyebrow="PERJALANAN KARIER ANDA" title={title} description="Lengkapi data Anda dan pantau proses rekrutmen. Keputusan akhir tetap dibuat oleh tim rekrutmen." />
    {children}
  </Workspace>
}

function AuthForm({ onAuth }: { onAuth: (token: string, account: Account) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = mode === 'login' ? { email, password } : { full_name: fullName, email, password, consent }
      const result = await tigRequest<{ access_token: string; applicant: Account }>(
        '/api/v1/applicant/' + mode, jsonOptions('POST', body))
      onAuth(result.access_token, result.applicant)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Gagal masuk.')
    } finally {
      setBusy(false)
    }
  }

  return <form className={box + ' space-y-4'} onSubmit={submit}>
    <div className="flex gap-2" role="tablist">
      {(['login', 'register'] as const).map(value => <button key={value} type="button" role="tab" aria-selected={mode === value}
        className={mode === value ? primary : secondary} onClick={() => { setMode(value); setError('') }}>
        {value === 'login' ? 'Masuk' : 'Daftar akun pelamar'}</button>)}
    </div>
    <p className="text-sm text-slate-600">{mode === 'login'
      ? 'Masuk untuk mengunggah CV, melengkapi formulir, dan memantau status lamaran.'
      : 'Buat akun sekali untuk melamar dan memantau status lamaran Anda.'}</p>
    {error && <Alert>{error}</Alert>}
    {mode === 'register' && <Field label="Nama lengkap"><input className={input} required maxLength={160} autoComplete="name"
      value={fullName} onChange={event => setFullName(event.target.value)} /></Field>}
    <Field label="Email"><input className={input} type="email" required maxLength={254} autoComplete="username"
      value={email} onChange={event => setEmail(event.target.value)} /></Field>
    <Field label={mode === 'register' ? 'Kata sandi (minimal 8 karakter)' : 'Kata sandi'}><input className={input} type="password" required
      minLength={mode === 'register' ? 8 : undefined} maxLength={72} autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
      value={password} onChange={event => setPassword(event.target.value)} /></Field>
    {mode === 'register' && <label className="flex items-start gap-2 text-sm text-slate-700">
      <input type="checkbox" className="mt-1" required checked={consent} onChange={event => setConsent(event.target.checked)} />
      <span>Saya setuju data lamaran saya diproses untuk rekrutmen TIG, termasuk penilaian kecocokan oleh AI dari isian formulir.
        Nama, kontak, usia, jenis kelamin, dan agama tidak dipakai dalam penilaian. Keputusan akhir tetap dibuat oleh tim rekrutmen.</span>
    </label>}
    <button className={primary} disabled={busy}>{busy ? 'Memproses…' : mode === 'login' ? 'Masuk' : 'Daftar dan lanjutkan'}</button>
  </form>
}

function Dashboard({ token, onAuthLost }: { token: string; onAuthLost: () => void }) {
  const [openings, setOpenings] = useState<Opening[] | null>(null)
  const [mine, setMine] = useState<MyApplication[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      tigRequest<Opening[]>('/api/v1/tig/jobs', { signal: controller.signal }),
      tigRequest<MyApplication[]>('/api/v1/applicant/applications', { headers: { Authorization: 'Bearer ' + token }, signal: controller.signal }),
    ]).then(([jobs, applications]) => {
      setOpenings(jobs)
      setMine(applications)
    }).catch(error => {
      if (controller.signal.aborted) return
      if (error instanceof RequestError && error.status === 401) onAuthLost()
      else setError(error.message)
    })
    return () => controller.abort()
  }, [token, onAuthLost])

  const applied = new Set(mine?.map(item => item.job_id))
  return <>
    {error && <Alert>{error}</Alert>}
    <section className={box}>
      <h2 className={sectionTitle}>Lamaran saya</h2>
      {!mine ? <p role="status">Memuat…</p> : mine.length ? <ul className="divide-y divide-slate-200 text-sm">{mine.map(item =>
        <li key={item.id} className="flex flex-wrap justify-between gap-2 py-3">
          <span className="font-medium">{item.title}</span>
          <span className="text-slate-600">Tahap: <strong>{item.stage}</strong> · dikirim {new Date(item.created_at).toLocaleDateString('id-ID')}</span>
        </li>)}</ul> : <p className="text-sm text-slate-600">Anda belum mengirim lamaran.</p>}
    </section>
    <section className={box}>
      <h2 className={sectionTitle}>Lowongan yang dibuka</h2>
      {!openings ? <p role="status">Memuat…</p> : openings.length ? <ul className="divide-y divide-slate-200 text-sm">{openings.map(job =>
        <li key={job.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div><p className="font-medium">{job.title}</p>
            <p className="text-slate-600">{[job.location, job.employment_type].filter(Boolean).join(' · ')}</p></div>
          {applied.has(job.id) ? <span className="text-slate-600">Sudah dilamar</span>
            : <a className={primary} href={'/apply/' + job.id}>Lamar</a>}
        </li>)}</ul> : <p className="text-sm text-slate-600">Belum ada lowongan yang dibuka.</p>}
    </section>
  </>
}

export default function ApplicantPortal({ jobId }: { jobId: string | null }) {
  const [token, setToken] = useState(readToken)
  const [account, setAccount] = useState<Account | null>(null)
  const [jobTitle, setJobTitle] = useState('')
  const [applied, setApplied] = useState<MyApplication | null | undefined>(undefined)

  const logout = useCallback(() => {
    writeToken(null)
    setToken(null)
    setAccount(null)
  }, [])

  useEffect(() => {
    if (!token || account) return
    const controller = new AbortController()
    tigRequest<Account>('/api/v1/applicant/me', { headers: { Authorization: 'Bearer ' + token }, signal: controller.signal })
      .then(setAccount).catch(() => { if (!controller.signal.aborted) logout() })
    return () => controller.abort()
  }, [token, account, logout])

  useEffect(() => {
    if (!jobId) return
    const controller = new AbortController()
    tigRequest<{ title: string }>('/api/v1/tig/apply/' + encodeURIComponent(jobId), { signal: controller.signal })
      .then(job => setJobTitle(job.title)).catch(() => undefined)
    return () => controller.abort()
  }, [jobId])

  useEffect(() => {
    if (!jobId || !token || !account) return
    const controller = new AbortController()
    tigRequest<MyApplication[]>('/api/v1/applicant/applications', { headers: { Authorization: 'Bearer ' + token }, signal: controller.signal })
      .then(items => setApplied(items.find(item => item.job_id === jobId) ?? null))
      .catch(() => { if (!controller.signal.aborted) setApplied(null) })
    return () => controller.abort()
  }, [jobId, token, account])

  const title = jobId ? jobTitle || 'Formulir lamaran' : 'Portal pelamar'
  if (token && !account) return <p className="p-6" role="status">Memeriksa sesi…</p>
  if (!token || !account) return <Shell account={null} title={title}>
    <AuthForm onAuth={(newToken, newAccount) => { writeToken(newToken); setToken(newToken); setAccount(newAccount) }} />
    <p className="text-center text-sm text-slate-600">Recruiter? <a className="text-indigo-700 underline" href="/app">Masuk sebagai recruiter</a></p>
  </Shell>
  if (!jobId) return <Shell account={account} onLogout={logout} title={title}><Dashboard token={token} onAuthLost={logout} /></Shell>
  return <Shell account={account} onLogout={logout} title={title}>
    {applied === undefined ? <p role="status">Memuat…</p>
      : applied ? <section className={box} role="status">
        <h2 className={sectionTitle}>Lamaran sudah terkirim</h2>
        <p>Anda sudah melamar lowongan ini pada {new Date(applied.created_at).toLocaleDateString('id-ID')}. Tahap saat ini: <strong>{applied.stage}</strong>.</p>
        <a className={secondary + ' mt-4 inline-block'} href="/pelamar">Lihat semua lamaran</a>
      </section>
      : <TigApplicant jobId={jobId} token={token} account={account} onAuthLost={logout} />}
  </Shell>
}
