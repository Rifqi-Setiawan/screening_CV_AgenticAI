import { useEffect, useRef, useState } from 'react'
import { ChevronRight, ExternalLink, Info, ShieldCheck, TriangleAlert } from 'lucide-react'
import type { SourceHighlight, TraceEvidence, TraceFacet, TraceRequirement, ScoreTrace } from './types'

const STATE_STYLE: Record<string, string> = {
  STRONG: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  PARTIAL: 'bg-amber-50 text-amber-700 border-amber-200',
  NOT_DEMONSTRATED: 'bg-rose-50 text-rose-700 border-rose-200',
  UNKNOWN: 'bg-slate-100 text-slate-500 border-slate-200',
}

const VERDICT_STYLE: Record<string, string> = {
  ENTAILED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  SATISFIED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  PARTIAL: 'bg-amber-50 text-amber-700 border-amber-200',
  NOT_ENTAILED: 'bg-rose-50 text-rose-700 border-rose-200',
  CONTRADICTED: 'bg-rose-100 text-rose-800 border-rose-300',
  UNKNOWN: 'bg-slate-100 text-slate-500 border-slate-200',
}

const TIER_STYLE: Record<string, string> = {
  T0: 'bg-slate-100 text-slate-600 border-slate-300',
  T1: 'bg-sky-50 text-sky-700 border-sky-200',
  T2: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  T3: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  T4: 'bg-emerald-200 text-emerald-900 border-emerald-400',
}

const IMPORTANCE_LABEL: Record<string, string> = {
  MUST_HAVE: 'Wajib',
  STRONG_PREFERENCE: 'Diutamakan',
  NICE_TO_HAVE: 'Nilai tambah',
}

const BAND_STYLE: Record<string, string> = {
  A: 'bg-emerald-600 text-white',
  B: 'bg-sky-600 text-white',
  C: 'bg-amber-500 text-white',
  R: 'bg-slate-600 text-white',
}

const METHOD_LABEL: Record<string, string> = {
  llm: 'Dinilai AI (Matcher)',
  matcher: 'Dinilai AI (Matcher)',
  ontology: 'Aturan ontologi (tanpa AI)',
  nli: 'Model NLI lokal',
  critic: 'Diaudit AI kedua (Critic)',
  manual: 'Penilaian manual',
  interview: 'Hasil wawancara',
}

const CRITIC_ACTION_LABEL: Record<string, string> = {
  CONFIRM: 'Dikonfirmasi',
  DOWNGRADE: 'Diturunkan',
  UPGRADE: 'Dinaikkan',
  ESCALATE: 'Dieskalasi ke manusia',
}

function Chip({ className, children }: { className: string; children: React.ReactNode }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-bold ${className}`}>{children}</span>
}

function EvidenceCard({ ev, onShowInCv }: { ev: TraceEvidence; onShowInCv: (atomKey: string) => void }) {
  return (
    <div className={`rounded-lg border p-2.5 text-[11px] ${ev.is_evidence ? 'bg-white border-slate-200' : 'bg-slate-50 border-dashed border-slate-300'}`}>
      <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
        <Chip className={TIER_STYLE[ev.tier] || TIER_STYLE.T0}>{ev.tier}</Chip>
        <span className="text-slate-500">{ev.tier_label}</span>
        {ev.page ? <span className="text-slate-400">• halaman {ev.page}</span> : null}
        <span className="text-slate-400 font-mono">• {ev.atom_key}</span>
        {!ev.is_evidence && (
          <span className="text-amber-700 font-semibold">Klaim saja, tidak dihitung sebagai bukti kerja</span>
        )}
      </div>
      <p className="text-slate-800 leading-relaxed">
        {ev.context_before && <span className="text-slate-400">…{ev.context_before} </span>}
        <mark className="bg-amber-100 text-slate-900 px-0.5 rounded-sm">{ev.quote}</mark>
        {ev.context_after && <span className="text-slate-400"> {ev.context_after}…</span>}
      </p>
      <div className="mt-1.5 flex items-center justify-between">
        {ev.source_found ? (
          <button
            onClick={() => onShowInCv(ev.atom_key)}
            className="text-indigo-600 hover:text-indigo-800 font-medium flex items-center space-x-1"
          >
            <span>Lihat di naskah CV</span>
            <ExternalLink className="w-2.5 h-2.5" />
          </button>
        ) : (
          <span className="text-slate-400 italic">Letak persis kutipan di naskah tidak ditemukan</span>
        )}
      </div>
    </div>
  )
}

function FacetBlock({ facet, onShowInCv }: { facet: TraceFacet; onShowInCv: (atomKey: string) => void }) {
  const method = facet.method ? METHOD_LABEL[facet.method] || facet.method : null
  return (
    <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-800">
            <span className="font-mono text-slate-500 mr-1.5">{facet.facet_key}</span>
            {facet.hypothesis}
            {!facet.core && <span className="ml-1.5 text-[10px] text-slate-400 font-normal">(pendukung)</span>}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Chip className={VERDICT_STYLE[facet.verdict] || VERDICT_STYLE.UNKNOWN}>{facet.verdict_label || facet.verdict}</Chip>
          <Chip className="bg-white text-slate-600 border-slate-200">Kedalaman {facet.depth}</Chip>
        </div>
      </div>
      {method && <p className="text-[10px] text-slate-400">{method}</p>}
      {facet.analysis && <p className="text-[11px] text-slate-600 italic">“{facet.analysis}”</p>}

      {facet.evidence.length > 0 ? (
        <div className="space-y-2">
          {facet.evidence.map((ev) => (
            <EvidenceCard key={ev.atom_key} ev={ev} onShowInCv={onShowInCv} />
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-slate-500">
          {facet.evidence_tracked
            ? 'Tidak ada kutipan CV yang mendukung facet ini.'
            : 'Tautan ke kutipan sumber tidak tersimpan untuk hasil ini (dibuat oleh versi lama). Jalankan screening ulang untuk melihat kutipannya.'}
        </p>
      )}

      {facet.critic && (
        <div
          className={`rounded-lg border p-2.5 text-[11px] ${
            facet.critic.action === 'CONFIRM' ? 'bg-emerald-50/50 border-emerald-200' : 'bg-amber-50 border-amber-200'
          }`}
        >
          <p className="font-bold text-slate-800 mb-0.5">
            Audit penilai kedua (Critic): {CRITIC_ACTION_LABEL[facet.critic.action] || facet.critic.action}
            {facet.critic.original_verdict && facet.critic.original_verdict !== facet.critic.final_verdict && (
              <span className="font-normal text-slate-600">
                {' '}
                — dari {facet.critic.original_verdict} menjadi {facet.critic.final_verdict}
              </span>
            )}
          </p>
          {facet.critic.reasoning && <p className="text-slate-600 italic">“{facet.critic.reasoning}”</p>}
        </div>
      )}
    </div>
  )
}

function RequirementBlock({
  req,
  open,
  onToggle,
  onShowInCv,
}: {
  req: TraceRequirement
  open: boolean
  onToggle: () => void
  onShowInCv: (atomKey: string) => void
}) {
  return (
    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-50">
        <div className="flex items-center space-x-2 min-w-0">
          <ChevronRight className={`w-3.5 h-3.5 text-slate-400 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`} />
          <span className="font-mono font-bold text-indigo-700 text-xs">{req.requirement_id}</span>
          <span className="text-xs font-medium text-slate-900 truncate">{req.description}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <span className="text-[10px] text-slate-400">{IMPORTANCE_LABEL[req.importance] || req.importance}</span>
          <Chip className={STATE_STYLE[req.state] || STATE_STYLE.UNKNOWN}>{req.state_label}</Chip>
        </div>
      </button>
      {open && (
        <div className="p-3 border-t border-slate-100 space-y-3">
          <div className="bg-indigo-50/50 border border-indigo-100 rounded-lg p-2.5 text-[11px] text-slate-700">
            <span className="font-bold text-indigo-800">Mengapa status ini: </span>
            {req.why || 'Tidak ada penjelasan tersimpan.'}
          </div>
          {req.duration && (
            <div className="text-[11px] text-slate-600">
              <p className="font-semibold text-slate-700 mb-1">
                Durasi pengalaman relevan ({req.duration.domain}):{' '}
                {req.duration.months_lo === req.duration.months_hi
                  ? `${req.duration.months_lo} bulan`
                  : `${req.duration.months_lo}–${req.duration.months_hi} bulan`}
                {req.duration.min_months ? ` • syarat minimal ${req.duration.min_months} bulan` : ''}
              </p>
              {req.duration.periods.length > 0 && (
                <ul className="space-y-0.5">
                  {req.duration.periods.map((p, i) => (
                    <li key={i} className="font-mono text-[10px] text-slate-500">
                      {p.start} → {p.end} • {p.months} bulan • bobot {p.weight} ({p.entry || 'pengalaman'})
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[10px] text-slate-400 mt-1">
                Bulan yang tumpang tindih tidak dihitung dua kali; magang dihitung setengah.
              </p>
            </div>
          )}
          <div className="space-y-2">
            {req.facets.map((f) => (
              <FacetBlock key={f.facet_key} facet={f} onShowInCv={onShowInCv} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function ScoreTracePanel({
  trace,
  onShowInCv,
}: {
  trace: ScoreTrace | null | undefined
  onShowInCv: (atomKey: string) => void
}) {
  const [openIds, setOpenIds] = useState<string[]>([])
  if (!trace) {
    return (
      <div className="border border-dashed border-slate-300 rounded-xl p-6 text-center text-xs text-slate-500">
        Penjelasan rinci belum tersedia untuk kandidat ini (server belum mengirim jejak skor).
      </div>
    )
  }
  const s = trace.summary
  const toggle = (id: string) => setOpenIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const totalPoints = trace.requirements.reduce((a, r) => a + (r.points ?? 0), 0)
  const notStrong = trace.requirements.filter((r) => r.state !== 'STRONG').map((r) => r.requirement_id)

  return (
    <div className="space-y-5 text-xs">
      {/* 1. Result and why */}
      <div className="border border-slate-200 rounded-xl p-4 bg-white">
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className="text-3xl font-mono font-bold text-slate-900">{s.final_score.toFixed(1)}</div>
            <div className="text-[10px] text-slate-400">skor akhir</div>
          </div>
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${BAND_STYLE[s.band] || BAND_STYLE.R}`}>Band {s.band}</span>
              <span className="font-bold text-slate-800">{s.recommendation}</span>
            </div>
            <p className="text-slate-600">
              <span className="font-semibold text-slate-700">Band: </span>
              {s.band_reason}
            </p>
            <p className="text-slate-600">
              <span className="font-semibold text-slate-700">Rekomendasi: </span>
              {s.recommendation_reason}
            </p>
            {s.score_interval[0] !== s.score_interval[1] && (
              <p className="text-amber-700">
                Rentang skor karena ada kriteria yang belum bisa dinilai: {s.score_interval[0]}–{s.score_interval[1]}.
              </p>
            )}
          </div>
        </div>
        {!trace.consistency.consistent && (
          <div className="mt-3 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-[11px] text-amber-800">
            <TriangleAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <div>
              {trace.consistency.note} (Tersimpan: {trace.consistency.stored_final}, band {trace.consistency.stored_band}; hitung ulang:{' '}
              {trace.consistency.recomputed_final}, band {trace.consistency.recomputed_band}.)
            </div>
          </div>
        )}
      </div>

      {/* 2. How the number is built */}
      <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
        <div className="p-3 border-b border-slate-100 bg-slate-50">
          <h4 className="font-bold text-slate-900 text-sm">Cara skor dihitung</h4>
          <p className="text-[11px] text-slate-500 mt-0.5">{trace.formula}</p>
        </div>
        <table className="w-full text-[11px]">
          <thead className="bg-white text-slate-500 text-left border-b border-slate-100">
            <tr>
              <th className="p-2 pl-3 font-semibold">Kriteria</th>
              <th className="p-2 font-semibold text-right">Bobot</th>
              <th className="p-2 font-semibold">Status</th>
              <th className="p-2 font-semibold text-right">Nilai</th>
              <th className="p-2 pr-3 font-semibold text-right">Poin</th>
            </tr>
          </thead>
          <tbody>
            {trace.requirements.map((r) => (
              <tr key={r.requirement_id} className={`border-b border-slate-50 ${r.counted ? '' : 'text-slate-400'}`}>
                <td className="p-2 pl-3">
                  <button className="text-left hover:text-indigo-700" onClick={() => toggle(r.requirement_id)}>
                    <span className="font-mono font-bold mr-1.5">{r.requirement_id}</span>
                    <span>{r.description.length > 56 ? `${r.description.slice(0, 56)}…` : r.description}</span>
                  </button>
                  <div className="text-[10px] text-slate-400">{IMPORTANCE_LABEL[r.importance] || r.importance}</div>
                </td>
                <td className="p-2 text-right font-mono">{r.weight.toFixed(0)}</td>
                <td className="p-2">
                  <Chip className={STATE_STYLE[r.state] || STATE_STYLE.UNKNOWN}>{r.state_label}</Chip>
                </td>
                <td className="p-2 text-right font-mono">{r.state_value === null ? '—' : r.state_value.toFixed(1)}</td>
                <td className="p-2 pr-3 text-right font-mono">
                  {r.points === null ? 'tidak dihitung' : `${r.points.toFixed(1)} / ${r.max_points.toFixed(0)}`}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-slate-50 font-bold text-slate-800">
              <td className="p-2 pl-3" colSpan={4}>
                Total poin ÷ bobot yang bisa dinilai × 100
              </td>
              <td className="p-2 pr-3 text-right font-mono">
                {totalPoints.toFixed(1)} / {s.counted_weight.toFixed(0)}
              </td>
            </tr>
            <tr className="bg-slate-50 text-slate-700">
              <td className="p-2 pl-3" colSpan={4}>
                Skor hitungan sebelum batas band
              </td>
              <td className="p-2 pr-3 text-right font-mono">{s.raw_score.toFixed(1)}</td>
            </tr>
          </tfoot>
        </table>
        {notStrong.length > 0 && (
          <p className="p-3 text-[11px] text-slate-500 border-t border-slate-100">
            Kriteria yang belum terbukti kuat: <span className="font-mono font-semibold">{notStrong.join(', ')}</span>.
          </p>
        )}
      </div>

      {/* 3. Per requirement */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-bold text-slate-900 text-sm">Dari mana tiap kriteria berasal</h4>
          <div className="space-x-2 text-[11px]">
            <button className="text-indigo-600 hover:underline" onClick={() => setOpenIds(trace.requirements.map((r) => r.requirement_id))}>
              Buka semua
            </button>
            <button className="text-slate-500 hover:underline" onClick={() => setOpenIds([])}>
              Tutup semua
            </button>
          </div>
        </div>
        <div className="space-y-2">
          {trace.requirements.map((r) => (
            <RequirementBlock
              key={r.requirement_id}
              req={r}
              open={openIds.includes(r.requirement_id)}
              onToggle={() => toggle(r.requirement_id)}
              onShowInCv={onShowInCv}
            />
          ))}
        </div>
      </div>

      {/* 4. Flags */}
      {trace.flags.length > 0 && (
        <div className="border border-slate-200 rounded-xl p-3 bg-white">
          <h4 className="font-bold text-slate-900 text-sm mb-2">Peringatan dan penanda pada kandidat ini</h4>
          <ul className="space-y-1.5">
            {trace.flags.map((f) => (
              <li key={f.flag} className="text-[11px]">
                <span className="font-mono text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded mr-1.5">{f.flag}</span>
                <span className="text-slate-600">{f.meaning || 'Penanda internal sistem.'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-start gap-2 text-[10px] text-slate-400">
        <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <p>
          Semua kutipan diambil apa adanya dari naskah CV (identitas sudah disamarkan). AI hanya memberi putusan kategorikal per facet; angka dan band
          dihitung oleh kode. Keputusan akhir tetap di tangan recruiter.
        </p>
      </div>
      <div className="flex items-start gap-2 text-[10px] text-slate-400">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <p>Kutipan dengan label “Klaim saja” berasal dari ringkasan atau daftar keahlian dan tidak pernah dihitung sebagai bukti kerja.</p>
      </div>
    </div>
  )
}

/** Splits the CV text into plain and highlighted segments (overlaps are merged). */
function segmentCvText(text: string, highlights: SourceHighlight[]): Array<{ text: string; keys: string[]; start: number }> {
  const bounds = Array.from(new Set([0, text.length, ...highlights.flatMap((h) => [h.start, h.end])]))
    .filter((b) => b >= 0 && b <= text.length)
    .sort((a, b) => a - b)
  const out: Array<{ text: string; keys: string[]; start: number }> = []
  for (let i = 0; i < bounds.length - 1; i++) {
    const [a, b] = [bounds[i], bounds[i + 1]]
    if (a === b) continue
    const keys = highlights.filter((h) => h.start <= a && h.end >= b).map((h) => h.atom_key)
    out.push({ text: text.slice(a, b), keys, start: a })
  }
  return out
}

/** The (redacted) CV text with every sentence used as evidence highlighted; the focused one is scrolled into view. */
export function CvTextViewer({
  text,
  highlights,
  focusKey,
  fallbackQuote,
}: {
  text: string
  highlights: SourceHighlight[]
  focusKey: string | null
  fallbackQuote: string | null
}) {
  const focusRef = useRef<HTMLElement | null>(null)
  const extra: SourceHighlight[] = []
  if (fallbackQuote && !focusKey) {
    const i = text.indexOf(fallbackQuote)
    if (i >= 0) extra.push({ atom_key: '__quote__', start: i, end: i + fallbackQuote.length })
  }
  const all = [...highlights, ...extra]
  const focus = focusKey ?? (extra.length ? '__quote__' : null)
  const segments = segmentCvText(text, all)
  const firstFocused = segments.findIndex((seg) => focus !== null && seg.keys.includes(focus))

  useEffect(() => {
    focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focus, text])

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span className="inline-block w-3 h-3 rounded-sm bg-amber-200" />
        <span>Kalimat yang dipakai sebagai bukti skor ({highlights.length})</span>
        {focus && <span className="inline-block w-3 h-3 rounded-sm bg-amber-400 ml-3" />}
        {focus && <span>kutipan yang sedang dilihat</span>}
      </div>
      <div className="p-4 bg-slate-900 text-slate-100 rounded-xl font-mono text-xs whitespace-pre-wrap leading-relaxed max-h-[520px] overflow-y-auto border border-slate-800">
        {segments.map((seg, i) =>
          seg.keys.length === 0 ? (
            <span key={i}>{seg.text}</span>
          ) : (
            <mark
              key={i}
              ref={i === firstFocused ? (el) => { focusRef.current = el } : undefined}
              title={`Bukti: ${seg.keys.join(', ')}`}
              className={`rounded-sm px-0.5 text-slate-900 ${focus !== null && seg.keys.includes(focus) ? 'bg-amber-400' : 'bg-amber-200'}`}
            >
              {seg.text}
            </mark>
          ),
        )}
      </div>
    </div>
  )
}
