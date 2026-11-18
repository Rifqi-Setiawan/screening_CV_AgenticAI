import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, box, Field, input, secondary, sectionTitle } from './TigFields'
import TigConfigForm, { cleanConfig } from './TigConfigForm'
import TigApplicationPage from './TigApplicationPage'
import { detailHash } from './route'
import { rowVersion, scoreLabel, scoreStyles } from './tigApplication'
import type { Detail, ListResponse, Row } from './tigApplication'
import { emptyRegular, jsonOptions, RequestError, tigRequest } from './tigTypes'
import type { Config } from './tigTypes'
import { Metric } from './Workspace'

type ConfigResponse = { config: Config; can_edit: boolean; job_status: string }

export default function TigStaff({ jobId, title, token, view, applicationId }: {
  jobId: string; title: string; token: string; view: 'lowongan' | 'lamaran' | 'detail'; applicationId?: string
}) {
  const endpoint = '/api/v1/jobs/' + jobId + '/tig'
  const headers = useMemo(() => ({ Authorization: 'Bearer ' + token }), [token])
  const [settings, setSettings] = useState<ConfigResponse | null>(null)
  const [draft, setDraft] = useState<Config>({ published: false, regular: emptyRegular, program: [] })
  const [applications, setApplications] = useState<ListResponse | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [detailFailure, setDetailFailure] = useState<{ id: string; message: string } | null>(null)
  const [filter, setFilter] = useState<Row['category'] | 'Semua'>('Semua')
  const [sort, setSort] = useState('highest')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const reload = useCallback(async () => {
    const list = await tigRequest<ListResponse>(endpoint + '/applications', { headers })
    setApplications(list)
  }, [endpoint, headers])

  useEffect(() => {
    const controller = new AbortController()
    tigRequest<ConfigResponse>(endpoint + '/config', { headers, signal: controller.signal }).then(value => {
      setSettings(value)
      setDraft(value.config)
      return reload()
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [endpoint, headers, reload])

  useEffect(() => {
    if (!settings) return
    const interval = window.setInterval(() => { void reload().catch(error => setError(error.message)) }, 8000)
    return () => window.clearInterval(interval)
  }, [reload, settings])

  // Each detail view is written to the audit log: fetch once per opened application and again only when the
  // list reports a newer version of that row (stage or assessment changed). The detail itself is never polled.
  const selection = view === 'detail' ? applicationId ?? '' : ''
  const selectedRow = applications?.applications.find(row => row.id === selection)
  const selectedVersion = selectedRow ? rowVersion(selectedRow) : ''
  const loadedVersion = detail?.id === selection ? rowVersion(detail) : ''
  useEffect(() => {
    if (!selection) return
    if (loadedVersion && (!selectedVersion || selectedVersion === loadedVersion)) return
    const controller = new AbortController()
    tigRequest<Detail>(endpoint + '/applications/' + selection, { headers, signal: controller.signal })
      .then(setDetail).catch(error => {
        if (controller.signal.aborted) return
        setDetailFailure({ id: selection, message: error instanceof RequestError && error.status === 404 ? 'Lamaran tidak ditemukan pada lowongan ini.' : error.message })
      })
    return () => controller.abort()
  }, [selection, selectedVersion, loadedVersion, endpoint, headers])

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const saved = await tigRequest<ConfigResponse>(endpoint + '/config', jsonOptions('PUT', cleanConfig(draft), headers))
      setSettings(saved)
      setDraft(saved.config)
      setNotice('Aturan TIG disimpan.')
      await reload()
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function changeApplication(path: string, options: RequestInit) {
    setBusy(true)
    setError('')
    try {
      await tigRequest(endpoint + '/applications/' + selection + path, options)
      await reload()
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const visible = (applications?.applications ?? [])
    .filter(row => filter === 'Semua' || row.category === filter)
    .sort((a, b) => sort === 'highest' ? (b.score ?? -1) - (a.score ?? -1)
      : sort === 'lowest' ? (a.score ?? 101) - (b.score ?? 101)
        : b.created_at.localeCompare(a.created_at))
  const applyUrl = window.location.origin + '/apply/' + jobId
  const rows = applications?.applications ?? []

  if (view === 'detail') {
    const current = detail?.id === selection ? detail : null
    return <section id="lamaran" className="space-y-5">
      {error && <Alert>{error}</Alert>}
      <TigApplicationPage jobTitle={title} applicationId={selection} detail={current} rows={rows} canEdit={Boolean(applications?.can_edit)} busy={busy}
        error={!current && detailFailure?.id === selection ? detailFailure.message : ''}
        onStage={stage => void changeApplication('', jsonOptions('PATCH', { stage }, headers))}
        onRescore={() => void changeApplication('/rescore', { method: 'POST', headers })} />
    </section>
  }

  return <section id="lamaran" className="space-y-5">
    <header className={box}>
      <div className="section-heading"><p className="eyebrow">LOWONGAN TERPILIH</p><span className="status-badge">{settings ? settings.job_status : 'Memuat status…'}</span></div>
      <h2 className="mt-2 text-2xl font-bold">{title || 'Lamaran TIG'}</h2>

      {settings?.config?.published && settings.job_status === 'OPEN' && <div className="mt-4 flex flex-wrap gap-3">
        <a className="text-sm text-indigo-700 underline" href={applyUrl} target="_blank" rel="noreferrer">Buka formulir pelamar ↗</a>
        <button type="button" className={secondary} onClick={() => {
          navigator.clipboard.writeText(applyUrl).then(() => setNotice('Link formulir disalin.')).catch(() => setNotice('Buka formulir pelamar, lalu salin alamat dari browser.'))
        }}>Salin link formulir</button>
      </div>}
    </header>
    {error && <Alert>{error}</Alert>}
    {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {!applications && !error && <p role="status" className={box}>Memuat konfigurasi dan lamaran…</p>}
    {view === 'lamaran' && applications && <dl className="metrics-strip" aria-label="Ringkasan lowongan terpilih">
      <Metric label="Lamaran masuk" value={rows.length} description="Hanya lowongan terpilih" />
      <Metric label="Sudah dinilai" value={rows.filter(row => row.score !== null).length} description="Skor tersedia, bukan keputusan seleksi" />
      <Metric label="Dalam antrean" value={rows.filter(row => ['PENDING', 'RUNNING'].includes(row.assessment_status)).length} description="Menunggu atau sedang dinilai" />
      <Metric label="Gagal dinilai" value={rows.filter(row => row.assessment_status === 'FAILED').length} description="Perlu ditinjau dan dicoba ulang" />
    </dl>}
    {view === 'lowongan' && settings?.can_edit && <details open>
      <summary className="mb-2 cursor-pointer rounded-lg border border-slate-200 bg-white p-3 font-medium text-slate-700">Konfigurasi lowongan TIG</summary>
      <TigConfigForm config={draft} onChange={setDraft} onSave={save} busy={busy} />
    </details>}
    {view === 'lamaran' && applications && <section className={box + ' space-y-4'}>
      <div className="section-heading"><h2 className={sectionTitle}>Daftar lamaran</h2><span className="text-xs text-slate-600">{visible.length} dari {rows.length} lamaran · lowongan terpilih</span></div>
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="Kategori skor"><select className={input} value={filter} onChange={event => setFilter(event.target.value as typeof filter)}>
          {(['Semua', 'Tinggi', 'Sedang', 'Rendah', 'Belum dinilai'] as const).map(value => <option key={value}>{value}</option>)}
        </select></Field>
        <Field label="Urutan"><select className={input} value={sort} onChange={event => setSort(event.target.value)}>
          <option value="highest">Skor tertinggi</option><option value="lowest">Skor terendah</option><option value="newest">Lamaran terbaru</option>
        </select></Field>
        <button className={secondary} type="button" disabled={refreshing} onClick={async () => {
          setRefreshing(true)
          try { await reload() } catch (error) { setError((error as Error).message) } finally { setRefreshing(false) }
        }}>{refreshing ? 'Memuat…' : 'Muat ulang'}</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-md border-collapse text-left text-sm">
          <thead className="bg-slate-100 text-slate-600"><tr><th className="p-3">Lamaran</th><th className="p-3">Skor</th><th className="p-3">Tahap</th><th className="p-3">Masuk</th></tr></thead>
          <tbody>{visible.map(row => <tr key={row.id} className="application-row border-b border-slate-200">
            <td className="p-3"><a className="application-link" href={detailHash(jobId, row.id)}>Lamaran {row.id.slice(0, 8)}</a></td>
            <td className="p-3"><span className={'rounded-full px-2 py-1 font-medium ' + scoreStyles[row.category]}>{scoreLabel(row)}</span></td>
            <td className="p-3">{row.stage}</td>
            <td className="p-3">{new Date(row.created_at).toLocaleString('id-ID')}</td>
          </tr>)}</tbody>
        </table>
      </div>
      {!visible.length && <p className="text-sm text-slate-600">Belum ada lamaran yang cocok dengan filter.</p>}
    </section>}
  </section>
}
