import type { ReactNode } from 'react'
import './scoreDetail.css'
import { Alert, Field, input, primary } from './TigFields'
import FormSummary from './FormSummary'
import ProfileCard from './ProfileCard'
import { Donut, Gauge, MiniBars, StackedBar } from './ScoreCards'
import { HistoryDetails, OptionsDetails, TraceDetails } from './TigExplain'
import { categoryColor, evidenceStyle, scoreLabel, scoreStyles } from './tigApplication'
import type { Detail, Row } from './tigApplication'
import { contributions, evidenceShare, historySeries, lastChange, rankOf, trackSegments } from './scoreView'
import { categories, stages } from './tigTypes'
import type { Category, CategoryResult, Stage } from './tigTypes'

const dateTime = (value: string | null) => value ? new Date(value).toLocaleString('id-ID') : null
const shortDate = (value: string) => new Date(value).toLocaleDateString('id-ID', { day: '2-digit', month: 'short' })
const signed = (value: number) => (value > 0 ? '+' : '') + value.toFixed(1)

function jump(id: string) {
  const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(id)?.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'start' })
}

function Card({ span, title, id, aside, children }: { span: number; title: string; id?: string; aside?: ReactNode; children: ReactNode }) {
  return <section id={id} className={'sd-card sd-span-' + span} aria-label={title}>
    <div className="sd-card-head"><h2 className="sd-card-title">{title}</h2>{aside}</div>
    {children}
  </section>
}

export default function TigApplicationPage({ jobTitle, applicationId, detail, rows, canEdit, busy, error, onStage, onRescore }: {
  jobTitle: string; applicationId: string; detail: Detail | null; rows: Row[]; canEdit: boolean; busy: boolean; error: string
  onStage: (stage: Stage) => void; onRescore: () => void
}) {
  const back = <a className="sd-back" href="#lamaran">← Kembali ke daftar lamaran</a>
  if (error) return <div className="sd-page">{back}<Alert>{error}</Alert></div>
  if (!detail) return <div className="sd-page">{back}<p role="status" className="panel">Memuat detail lamaran…</p></div>

  const result = detail.assessment
  const results = result?.categories
  const weights = result?.trace?.weights ?? null
  const parts = contributions(results, weights)
  const segments = trackSegments(parts)
  const share = evidenceShare(results)
  const rank = rankOf(rows, applicationId)
  const series = historySeries(detail.assessment_history, detail.score)
  const change = lastChange(series)
  const entries = results ? (Object.keys(categories) as Category[]).filter(key => results[key]).map(key => [key, results[key]] as [Category, CategoryResult]) : []
  const best = entries.reduce<[Category, CategoryResult] | null>((top, item) => !top || item[1].score > top[1].score ? item : top, null)
  const pending = ['PENDING', 'RUNNING'].includes(detail.assessment_status)

  return <div className="sd-page">
    {back}
    <header className="sd-header">
      <div>
        <p className="eyebrow">DETAIL SKOR PELAMAR</p>
        <h1>Lamaran {applicationId.slice(0, 8)}</h1>
        <p className="sd-meta">
          <span>{jobTitle}</span><span>Masuk {dateTime(detail.created_at)}</span>
          <span className="status-badge">{detail.stage}</span>
          <span className={'sd-chip ' + scoreStyles[detail.category]}>{scoreLabel(detail)}</span>
        </p>
      </div>
      {canEdit && <div className="sd-actions">
        <Field label="Ubah tahap (manual)"><select className={input} value={detail.stage} disabled={busy} onChange={event => onStage(event.target.value as Stage)}>
          {stages.map(stage => <option key={stage}>{stage}</option>)}
        </select></Field>
        <button type="button" className={primary} disabled={busy || pending} onClick={onRescore}>Nilai ulang dengan AI</button>
      </div>}
    </header>

    {!result && <p role="status" className="empty-assessment">
      {scoreLabel(detail)}. {pending ? 'Halaman diperbarui otomatis saat penilaian selesai.' : 'Bukti penilaian tersedia setelah proses selesai.'}
      {detail.assessment_history.length > 0 && ' Skor terakhir sebelum dinilai ulang: ' + detail.assessment_history[detail.assessment_history.length - 1].assessment.score + '/100.'}
    </p>}

    <div className="sd-grid">
      <ProfileCard form={detail.form} />

      <Card span={3} title="Skor akhir">
        <p className="sd-big">{result ? result.score : '—'}<span className="sd-unit"> /100</span></p>
        {result && <meter className="category-meter" min={0} max={100} value={result.score} aria-label={'Skor akhir ' + result.score + ' dari 100'}>{result.score}/100</meter>}
        <p className="sd-sub"><span className={'sd-chip ' + scoreStyles[detail.category]}>{detail.category}</span>{detail.assessed_at && ' · dinilai ' + dateTime(detail.assessed_at)}</p>
      </Card>

      <Card span={3} title="Rata-rata berbobot">
        {result?.weighted_reference !== undefined ? <>
          <p className="sd-big">{result.weighted_reference.toFixed(1)}</p>
          <p className="sd-sub">Skor AI <strong className={(result.weighted_difference ?? 0) >= 0 ? 'sd-up' : 'sd-down'}>{signed(result.weighted_difference ?? 0)}</strong> dari rata-rata. Bobot hanya pedoman; skor akhir ditentukan AI secara holistik.</p>
        </> : best ? <>
          <p className="sd-big">{best[1].score}<span className="sd-unit"> /100</span></p>
          <p className="sd-sub">Subskor tertinggi: {categories[best[0]]}. Bobot tidak tersedia untuk penilaian ini.</p>
        </> : <>
          <p className="sd-big">—</p>
          <p className="sd-sub">Belum ada rincian subskor.</p>
        </>}
      </Card>

      <Card span={3} title="Bukti ditemukan">
        {share.total ? <div className="sd-donut-row">
          <Donut value={share.foundPct} label={'Bukti ada di formulir: ' + share.foundPct + ' persen dari ' + share.total + ' kutipan'} />
          <ul className="sd-legend">
            <li><span className="sd-dot" style={{ background: '#047857' }} />Ada di formulir <strong>{share.found}</strong></li>
            <li><span className="sd-dot" style={{ background: '#b45309' }} />Sebagian cocok <strong>{share.partial}</strong></li>
            <li><span className="sd-dot" style={{ background: '#be123c' }} />Tidak ditemukan <strong>{share.notFound}</strong></li>
          </ul>
        </div> : <>
          <p className="sd-big">—</p>
          <p className="sd-sub">{result ? 'AI tidak mengutip bukti pada penilaian ini.' : 'Muncul setelah penilaian selesai.'}</p>
        </>}
      </Card>

      <Card span={3} title="Peringkat di lowongan">
        {rank && detail.score !== null ? <>
          <p className="sd-big">#{rank.rank}<span className="sd-unit"> dari {rank.total}</span></p>
          <p className="sd-sub">Dihitung dari lamaran yang sudah dinilai pada lowongan ini.</p>
          <dl className="sd-mini-stats">
            <div><dt>Rata-rata lowongan</dt><dd>{rank.average.toFixed(1)}</dd></div>
            <div><dt>Selisih</dt><dd className={detail.score - rank.average >= 0 ? 'sd-up' : 'sd-down'}>{detail.score - rank.average >= 0 ? '↑ ' : '↓ '}{signed(detail.score - rank.average)}</dd></div>
          </dl>
        </> : <>
          <p className="sd-big">—</p>
          <p className="sd-sub">{rows.length ? 'Muncul setelah skor lamaran ini tersedia.' : 'Menghitung dari daftar lamaran…'}</p>
        </>}
      </Card>

      {parts.length > 0 && result && <Card span={7} title="Pembentukan skor" aside={<div className="sd-chips">
        <button type="button" className="sd-chip-button" onClick={() => jump('sd-transparansi')}>Data yang dilihat AI</button>
        <button type="button" className="sd-chip-button" onClick={() => jump('sd-formulir')}>Formulir</button>
        {series.length > 1 && <button type="button" className="sd-chip-button" onClick={() => jump('sd-riwayat')}>Riwayat</button>}
      </div>}>
        <p className="sd-big">{result.score}<span className="sd-unit"> skor akhir dari AI</span></p>
        <StackedBar label={'Kontribusi kategori terhadap skor: ' + parts.map(part => categories[part.key] + ' ' + part.contribution.toFixed(1)).join(', ')}
          segments={segments.map((segment, index) => ({ key: segment.key, width: segment.width, color: categoryColor[segment.key], title: categories[segment.key] + ': ' + parts[index].contribution.toFixed(1) }))} />
        <div className="sd-scale" aria-hidden="true"><span>0</span><span>100</span></div>
        <div className="sd-table" role="table" aria-label="Rincian pembentukan skor">
          <div className="sd-row sd-row-head" role="row"><span role="columnheader">Kategori</span><span role="columnheader">Subskor</span><span role="columnheader">Bobot</span><span role="columnheader">Kontribusi</span></div>
          {parts.map(part => <div className="sd-row" role="row" key={part.key}>
            <span role="cell"><span className="sd-dot" style={{ background: categoryColor[part.key] }} />{categories[part.key]}</span>
            <span role="cell">{part.score}</span><span role="cell">{part.weight}%</span><span role="cell"><strong>{part.contribution.toFixed(1)}</strong></span>
          </div>)}
          <div className="sd-row sd-row-total" role="row"><span role="cell">Rata-rata berbobot</span><span /><span /><span role="cell"><strong>{(result.weighted_reference ?? parts.reduce((sum, part) => sum + part.contribution, 0)).toFixed(1)}</strong></span></div>
        </div>
        {result.score_reasoning && <p className="sd-note"><strong>Alasan AI:</strong> {result.score_reasoning}</p>}
        {result.summary && <p className="sd-note">{result.summary}</p>}
      </Card>}

      {result && parts.length === 0 && <Card span={7} title="Pembentukan skor">
        <p className="sd-big">{result.score}<span className="sd-unit"> /100</span></p>
        <p className="sd-note">{result.summary}</p>
        <p className="sd-sub">Rincian bobot dan kontribusi tidak tersedia untuk penilaian ini (dibuat sebelum rincian transparansi). Nilai ulang untuk melihatnya.</p>
      </Card>}

      {result && <Card span={5} title="Bukti per kategori">
        {share.total ? <div className="sd-evidence" tabIndex={0} role="region" aria-label="Daftar bukti per kategori">
          {entries.filter(([, item]) => item.evidence?.length).map(([key, item]) => <div key={key} className="sd-evidence-group">
            <p className="sd-group-title"><span className="sd-dot" style={{ background: categoryColor[key] }} />{categories[key]} <span className="sd-sub">· subskor {item.score}</span></p>
            <ul>{item.evidence!.map((evidence, index) => <li key={index}>
              <span className={'sd-status ' + evidenceStyle[evidence.status][0]}>{evidenceStyle[evidence.status][1]}</span>
              <q>{evidence.quote}</q>
            </li>)}</ul>
          </div>)}
        </div> : <p className="sd-sub">AI tidak mengutip bukti pada penilaian ini (biasanya karena datanya kosong, atau penilaian dibuat sebelum bukti per kategori tersedia).</p>}
      </Card>}

      {entries.length > 0 && <Card span={7} title="Subskor per kategori">
        <div className="sd-gauges">{entries.map(([key, item]) => <figure key={key}>
          <Gauge value={item.score} color={categoryColor[key]} label={categories[key] + ': ' + item.score + ' dari 100'} />
          <figcaption>{categories[key]}{weights && <span className="sd-sub"> · bobot {weights[key]}%</span>}</figcaption>
        </figure>)}</div>
      </Card>}

      {result && <Card span={entries.length > 0 ? 5 : 12} title="Riwayat penilaian" id="sd-riwayat">
        {change ? <dl className="sd-mini-stats sd-three">
          <div><dt>Skor terbaru</dt><dd>{change.latest}</dd></div>
          <div><dt>Sebelumnya</dt><dd>{change.previous}</dd></div>
          <div><dt>Selisih</dt><dd className={change.delta >= 0 ? 'sd-up' : 'sd-down'}>{change.delta >= 0 ? '↑ ' : '↓ '}{signed(change.delta)}</dd></div>
        </dl> : <p className="sd-sub">Belum pernah dinilai ulang. Riwayat muncul setelah penilaian ulang pertama.</p>}
        {series.length > 1 && <MiniBars label={'Riwayat skor: ' + series.map(point => point.score).join(', ')}
          points={series.map(point => ({ score: point.score, current: point.current, label: point.at ? shortDate(point.at) : 'Kini' }))} />}
      </Card>}

      {!!result?.strengths?.length && <Card span={6} title="Kelebihan"><ul className="sd-list sd-good">{result.strengths.map((item, index) => <li key={index}>{item}</li>)}</ul></Card>}
      {!!result?.gaps?.length && <Card span={6} title="Kekurangan"><ul className="sd-list sd-bad">{result.gaps.map((item, index) => <li key={index}>{item}</li>)}</ul></Card>}

      {entries.length > 0 && <Card span={12} title="Penjelasan per kategori">
        <div className="sd-explain">{entries.map(([key, item]) => <div key={key}>
          <p className="sd-group-title"><span className="sd-dot" style={{ background: categoryColor[key] }} />{categories[key]} <span className="sd-sub">· subskor {item.score}</span></p>
          <p>{item.explanation}</p>
        </div>)}</div>
      </Card>}

      <Card span={6} title="Data formulir yang dikirim pelamar" id="sd-formulir">
        <p className="sd-sub sd-lead">Isian asli pelamar · bukan pratinjau file CV</p>
        <FormSummary form={detail.form} />
      </Card>

      <Card span={6} title="Transparansi penilaian" id="sd-transparansi">
        <div className="sd-transparency">
          <p className="sd-sub">Skor membantu peninjauan, bukan keputusan otomatis.</p>
          {result?.primary && <p className="text-sm"><strong>Posisi utama</strong> · {result.primary}. Prioritas {result.priorities?.join(' → ')}.</p>}
          {result?.trace ? <TraceDetails trace={result.trace} assessedAt={detail.assessed_at} />
            : <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-700">{result ? 'Penilaian ini dibuat sebelum rincian transparansi tersedia. Nilai ulang untuk melihat data yang dilihat AI.' : 'Rincian tersedia setelah penilaian selesai.'}</p>}
          {result?.options && <OptionsDetails options={result.options} />}
          {detail.assessment_history.length > 0 && <HistoryDetails history={detail.assessment_history} />}
        </div>
      </Card>
    </div>
  </div>
}
