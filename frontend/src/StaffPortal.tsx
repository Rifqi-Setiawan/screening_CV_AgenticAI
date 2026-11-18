import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import App from './App'
import { Alert, box, Field, input, primary, sectionTitle } from './TigFields'
import { jsonOptions, tigRequest } from './tigTypes'
import { AuthLayout } from './Workspace'

const tokenKey = 'cv_screening_token'
type Staff = { role: 'recruiter' }

export default function StaffPortal() {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey))
  const [staff, setStaff] = useState<Staff | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function logout() {
    localStorage.removeItem(tokenKey)
    setToken(null)
    setStaff(null)
  }

  useEffect(() => {
    if (!token || staff) return
    const controller = new AbortController()
    tigRequest<Staff>('/api/v1/auth/me', { headers: { Authorization: 'Bearer ' + token }, signal: controller.signal })
      .then(setStaff).catch(error => {
        if (!controller.signal.aborted) {
          logout()
          setError(error.message)
        }
      })
    return () => controller.abort()
  }, [token, staff])

  async function login(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await tigRequest<{ access_token: string; user: Staff }>('/api/v1/auth/login', jsonOptions('POST', { email, password }))
      localStorage.setItem(tokenKey, result.access_token)
      setToken(result.access_token)
      setStaff(result.user)
      setPassword('')
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (token && !staff) return <p className="p-6" role="status">Memeriksa sesi…</p>
  if (token && staff) return <App authToken={token} onLogout={logout} />

  return <AuthLayout><div className="auth-form">
    <form className={box + ' space-y-4'} onSubmit={login}>
      <p className="eyebrow">WORKSPACE RECRUITER</p>
      <h2 className={sectionTitle}>Masuk sebagai recruiter</h2>
      <p className="text-sm text-slate-600">Lanjutkan peninjauan lamaran dan pengaturan lowongan Anda.</p>
      {error && <Alert>{error}</Alert>}
      <Field label="Email"><input type="email" autoComplete="username" value={email} required className={input}
        onChange={event => setEmail(event.target.value)} /></Field>
      <Field label="Kata sandi"><input type="password" autoComplete="current-password" value={password} required className={input}
        onChange={event => setPassword(event.target.value)} /></Field>
      <button className={primary} disabled={busy}>{busy ? 'Memproses…' : 'Masuk'}</button>
    </form>
    <p className="mt-4 text-center text-sm text-slate-600">Pelamar? <a className="text-indigo-700 underline" href="/pelamar">Masuk atau daftar sebagai pelamar</a></p>
  </div></AuthLayout>
}
