import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, box, Field, input, primary, secondary, sectionTitle } from './TigFields'
import TigConfigForm, { cleanConfig } from './TigConfigForm'
import ScoreExplanation from './TigExplain'
import { emptyRegular, jsonOptions, stages, tigRequest } from './tigTypes'
import type { Application, AssessmentResult, Config, HistoryEntry, Stage } from './tigTypes'
import { Metric } from './Workspace'

type ConfigResponse = { config: Config; can_edit: boolean; job_status: string }
type Row = {
  id: string; stage: Stage; created_at: string; assessed_at: string | null; score: number | null
  category: 'Belum dinilai' | 'Rendah' | 'Sedang' | 'Tinggi'; assessment_status: 'PENDING' | 'RUNNING' | 'FAILED' | 'DONE'
}
type ListResponse = { applications: Row[]; can_edit: boolean }
type Detail = Row & { form: Application; assessment: AssessmentResult | null; assessment_history: HistoryEntry[] }

function scoreLabel(row: Row) {
  if (row.score !== null) return row.score + ' · ' + row.category
  if (row.assessment_status === 'FAILED') return 'Gagal dinilai'
  if (row.assessment_status === 'RUNNING') return 'Sedang dinilai'
  if (row.assessment_status === 'PENDING') return 'Menunggu penilaian'
  return 'Belum dinilai'
}

function FormSummary({ form }: { form: Application }) {
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

const scoreStyles: Record<Row['category'], string> = {
  Tinggi: 'bg-emerald-100 text-emerald-900', Sedang: 'bg-amber-100 text-amber-900',
  Rendah: 'bg-rose-100 text-rose-900', 'Belum dinilai': 'bg-slate-100 text-slate-700',
}

export default function TigStaff({ jobId, title, token, view }: { jobId: string; title: string; token: string; view: 'lowongan' | 'lamaran' }) {
  const endpoint = '/api/v1/jobs/' + jobId + '/tig'
  const headers = useMemo(() => ({ Authorization: 'Bearer ' + token }), [token])
  const [settings, setSettings] = useState<ConfigResponse | null>(null)
  const [draft, setDraft] = useState<Config>({ published: false, regular: emptyRegular, program: [] })
  const [applications, setApplications] = useState<ListResponse | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [selection, setSelection] = useState('')
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

  // Reload the detail only when the selected row changes; each detail view is written to the audit log.
  const selectedRow = applications?.applications.find(row => row.id === selection)
  const selectedVersion = selectedRow ? [selectedRow.stage, selectedRow.assessment_status, selectedRow.assessed_at].join('|') : ''
  useEffect(() => {
    if (!selection) return
    const controller = new AbortController()
    tigRequest<Detail>(endpoint + '/applications/' + selection, { headers, signal: controller.signal })
      .then(setDetail).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [selectedVersion, endpoint, headers, selection])

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
          <tbody>{visible.map(row => <tr key={row.id} className={'application-row border-b border-slate-200' + (selection === row.id ? ' selected-row' : '')}>
            <td className="p-3"><button type="button" aria-pressed={selection === row.id} className="application-link"
              onClick={() => { setSelection(row.id); if (detail?.id !== row.id) setDetail(null) }}>Lamaran {row.id.slice(0, 8)}</button></td>
            <td className="p-3"><span className={'rounded-full px-2 py-1 font-medium ' + scoreStyles[row.category]}>{scoreLabel(row)}</span></td>
            <td className="p-3">{row.stage}</td>
            <td className="p-3">{new Date(row.created_at).toLocaleString('id-ID')}</td>
          </tr>)}</tbody>
        </table>
      </div>
      {!visible.length && <p className="text-sm text-slate-600">Belum ada lamaran yang cocok dengan filter.</p>}
    </section>}
    {view === 'lamaran' && selection && <section className={box + ' space-y-4'} aria-label="Detail lamaran">
      <div className="flex items-center justify-between gap-3">
        <h2 className={sectionTitle + ' mb-0'}>Detail lamaran {selection.slice(0, 8)}</h2>
        <button className={secondary} onClick={() => { setSelection(''); setDetail(null) }}>Tutup detail</button>
      </div>
      {detail ? <>
        <p role="status" className="text-sm font-semibold text-slate-700">{scoreLabel(detail)} · {detail.stage}</p>
        <div className="candidate-layout">
          <section className="candidate-form"><h3 className="pane-title">Data formulir yang dikirim pelamar</h3><p className="pane-description">Isian asli pelamar · bukan pratinjau file CV</p><FormSummary form={detail.form} /></section>
          <section className="candidate-assessment"><h3 className="pane-title">Penilaian & bukti</h3><p className="pane-description">Skor membantu peninjauan, bukan keputusan otomatis.</p>
        {detail.assessment && <ScoreExplanation result={detail.assessment} assessedAt={detail.assessed_at} history={detail.assessment_history} />}
        {!detail.assessment && <p className="empty-assessment">{scoreLabel(detail)}. Bukti penilaian tersedia setelah proses selesai.</p>}
        {!detail.assessment && detail.assessment_history.length > 0 && <p className="text-sm text-slate-600">
          Skor terakhir sebelum dinilai ulang: {detail.assessment_history[detail.assessment_history.length - 1].assessment.score}/100.</p>}
          </section>
        </div>
        {applications?.can_edit && <div className="flex flex-wrap items-end gap-3">
          <Field label="Ubah tahap (manual)"><select className={input} value={detail.stage} disabled={busy} onChange={event =>
            void changeApplication('', jsonOptions('PATCH', { stage: event.target.value }, headers))}>
            {stages.map(stage => <option key={stage}>{stage}</option>)}
          </select></Field>
          <button className={primary} disabled={busy || ['PENDING', 'RUNNING'].includes(detail.assessment_status)}
            onClick={() => void changeApplication('/rescore', { method: 'POST', headers })}>Nilai ulang dengan AI</button>
        </div>}
      </> : <p role="status">Memuat detail…</p>}
    </section>}
  </section>
}
