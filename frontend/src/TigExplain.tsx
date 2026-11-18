import { categories } from './tigTypes'
import { evidenceStyle } from './tigApplication'
import type { Assessment, AssessmentResult, Category, CategoryResult, HistoryEntry, Trace } from './tigTypes'

const attributeLabels: Record<string, string> = {
  BIRTH: 'tempat/tanggal lahir', AGE: 'usia', RELIGION: 'agama', GENDER: 'jenis kelamin', MARITAL: 'status pernikahan',
  ETHNICITY: 'suku/kewarganegaraan', PHYSICAL: 'ciri fisik', ADDRESS: 'alamat', PRIVATE_LABEL: 'label data pribadi',
}

const fieldLabels: Record<string, string> = {
  formulir: 'Formulir pelamar', posisi: 'Persyaratan posisi', opsi_posisi: 'Opsi posisi', education: 'Pendidikan',
  experiences: 'Pengalaman', projects: 'Proyek', skills: 'Keahlian', languages: 'Bahasa', certifications: 'Sertifikasi',
  preferences: 'Preferensi kerja', level: 'Jenjang', campus: 'Kampus', major: 'Jurusan', gpa: 'IPK', title: 'Posisi',
  organization: 'Organisasi', start: 'Mulai', end: 'Selesai', description: 'Deskripsi', expected_salary: 'Ekspektasi gaji',
  domicile: 'Domisili', work_modes: 'Model kerja', open_to_placement: 'Bersedia ditempatkan',
  education_minimum: 'Pendidikan minimum', gpa_minimum: 'IPK minimum', majors: 'Jurusan direkomendasikan',
  qualifications: 'Kualifikasi', experience: 'Pengalaman dibutuhkan', work_mode: 'Model kerja', location: 'Lokasi',
  salary_minimum: 'Gaji minimum', salary_maximum: 'Gaji maksimum', campus_tiers: 'Tier kampus', tier: 'Tier',
  aliases: 'Singkatan', weights: 'Bobot', option: 'Nomor opsi', published: 'Dibuka',
}

function fieldName(path: string) {
  return path.split('.').map(part => /^\d+$/.test(part) ? '#' + (Number(part) + 1) : fieldLabels[part] ?? part).join(' › ')
}

function DataTree({ value, name }: { value: unknown; name?: string }) {
  const label = name !== undefined ? <span className="font-medium text-slate-700">{/^\d+$/.test(name) ? '#' + (Number(name) + 1) : fieldLabels[name] ?? name}: </span> : null
  if (Array.isArray(value)) {
    if (!value.length) return <li>{label}<span className="text-slate-400">kosong</span></li>
    if (value.every(item => typeof item !== 'object' || item === null)) return <li>{label}{value.join(', ')}</li>
    return <li>{label}<ul className="ml-4 list-disc">{value.map((item, i) => <DataTree key={i} value={item} name={String(i)} />)}</ul></li>
  }
  if (name === 'weights' && value && typeof value === 'object') {
    return <li>{label}{Object.entries(value).map(([key, weight]) => (categories[key as Category] ?? key) + ' ' + weight + '%').join(' · ')}</li>
  }
  if (value && typeof value === 'object') {
    return <li>{label}<ul className="ml-4 list-disc">{Object.entries(value).map(([key, item]) => <DataTree key={key} value={item} name={key} />)}</ul></li>
  }
  const text = value === null || value === '' ? <span className="text-slate-400">kosong</span>
    : typeof value === 'boolean' ? (value ? 'Ya' : 'Tidak') : String(value)
  return <li className="whitespace-pre-wrap">{label}{text}</li>
}

function CategoryCard({ name, category, weight }: { name: Category; category: CategoryResult; weight?: number }) {
  return <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
    <p className="font-semibold">{categories[name]} · subskor {category.score}
      {weight !== undefined && <span className="font-normal text-slate-600"> · bobot {weight}% · kontribusi {(weight * category.score / 100).toFixed(1)}</span>}
    </p>
    <meter className="category-meter" min={0} max={100} value={category.score} aria-label={categories[name] + ': ' + category.score + ' dari 100'}>{category.score}/100</meter>
    <p className="mt-1">{category.explanation}</p>
    {category.evidence && <div className="mt-2">
      <p className="text-xs font-semibold text-slate-600">Bukti yang dikutip AI dari formulir</p>
      {category.evidence.length ? <ul className="mt-1 space-y-1">{category.evidence.map((item, i) =>
        <li key={i} className="flex flex-wrap items-start gap-2">
          <span className={'shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ' + evidenceStyle[item.status][0]}>{evidenceStyle[item.status][1]}</span>
          <q className="text-slate-800">{item.quote}</q>
        </li>)}</ul>
        : <p className="mt-1 text-slate-500">AI tidak mengutip bukti untuk kategori ini (biasanya karena datanya kosong).</p>}
    </div>}
  </div>
}

export function Breakdown({ result, weights }: { result: Assessment; weights?: Record<Category, number> | null }) {
  return <div className="space-y-3 text-sm">
    <p><strong>{result.score}/100</strong> · {result.summary}</p>
    {result.estimated && <p className="rounded-lg bg-amber-50 p-2 text-amber-900">Skor ini perkiraan sistem (85% dari skor utama) karena AI tidak mengembalikan penilaian untuk opsi ini.</p>}
    {result.categories && <div className="grid gap-3 sm:grid-cols-2">
      {(Object.entries(result.categories) as [Category, CategoryResult][]).map(([key, category]) =>
        <CategoryCard key={key} name={key} category={category} weight={weights?.[key]} />)}
    </div>}
    {!!result.strengths?.length && <div><strong>Kelebihan</strong><ul className="list-disc pl-5">{result.strengths.map((item, i) => <li key={i}>{item}</li>)}</ul></div>}
    {!!result.gaps?.length && <div><strong>Kekurangan</strong><ul className="list-disc pl-5">{result.gaps.map((item, i) => <li key={i}>{item}</li>)}</ul></div>}
  </div>
}

function ScoreMath({ result, weights }: { result: Assessment; weights: Record<Category, number> }) {
  if (!result.categories || result.weighted_reference === undefined) return null
  const difference = result.weighted_difference ?? 0
  return <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm">
    <p className="font-semibold text-indigo-950">Bagaimana skor {result.score} terbentuk</p>
    <div className="mt-2 overflow-x-auto">
      <table className="w-full min-w-sm text-left">
        <thead className="text-indigo-900"><tr><th className="py-1 pr-3">Kriteria</th><th className="py-1 pr-3">Bobot</th><th className="py-1 pr-3">Subskor</th><th className="py-1">Kontribusi</th></tr></thead>
        <tbody>{(Object.keys(categories) as Category[]).map(key => <tr key={key} className="border-t border-indigo-100">
          <td className="py-1 pr-3">{categories[key]}</td><td className="py-1 pr-3">{weights[key]}%</td>
          <td className="py-1 pr-3">{result.categories![key].score}</td><td className="py-1">{(weights[key] * result.categories![key].score / 100).toFixed(1)}</td>
        </tr>)}
          <tr className="border-t border-indigo-200 font-semibold"><td className="py-1 pr-3" colSpan={3}>Rata-rata berbobot</td><td className="py-1">{result.weighted_reference.toFixed(1)}</td></tr>
          <tr className="font-semibold"><td className="py-1 pr-3" colSpan={3}>Skor akhir dari AI</td><td className="py-1">{result.score} ({difference > 0 ? '+' : ''}{difference.toFixed(1)})</td></tr>
        </tbody>
      </table>
    </div>
    <p className="mt-2 text-indigo-900">Sesuai aturan TIG, bobot adalah pedoman. Skor akhir ditentukan AI secara holistik, sehingga bisa sedikit berbeda dari rata-rata berbobot dan dari penilaian ulang.</p>
    {result.score_reasoning && <p className="mt-2"><strong>Alasan AI:</strong> {result.score_reasoning}</p>}
  </div>
}

export function TraceDetails({ trace, assessedAt }: { trace: Trace; assessedAt: string | null }) {
  const { hidden, attributes, links } = trace.sanitization
  return <>
    <details className="rounded-lg border border-slate-200 p-3">
      <summary className="cursor-pointer font-medium">Data yang dilihat AI</summary>
      <p className="mt-2 text-sm text-slate-600">Ini isi persis yang dikirim ke AI setelah data pribadi disaring. AI tidak membaca file CV, hanya data ini.</p>
      <ul className="mt-2 space-y-1 text-sm">{Object.entries(trace.input).map(([key, value]) => <DataTree key={key} value={value} name={key} />)}</ul>
    </details>
    <details className="rounded-lg border border-slate-200 p-3">
      <summary className="cursor-pointer font-medium">Data yang tidak dipakai atau disembunyikan</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {trace.excluded.map((item, i) => <li key={i}>{item}</li>)}
        {attributes.length > 0 && <li>Disaring dari teks bebas: {attributes.map(code => attributeLabels[code] ?? code).join(', ')}.</li>}
        {links > 0 && <li>{links} tautan dihapus.</li>}
        {hidden.map((item, i) => <li key={'h' + i} className="text-rose-800">Isian <strong>{fieldName(item.field)}</strong> disembunyikan dari AI karena berisi teks yang menyerupai instruksi ke AI ({item.reasons.join(', ')}). Periksa isian aslinya di data formulir.</li>)}
      </ul>
    </details>
    <p className="text-xs text-slate-500">Model {trace.model} · aturan penilaian {trace.prompt_version}{assessedAt && ' · dinilai ' + new Date(assessedAt).toLocaleString('id-ID')}</p>
  </>
}

export function OptionsDetails({ options }: { options: Record<string, Assessment> }) {
  return <details className="rounded-lg border border-slate-200 p-3">
    <summary className="cursor-pointer font-medium">Penilaian semua opsi posisi</summary>
    <div className="mt-3 space-y-4">{Object.entries(options).map(([position, option]) =>
      <div key={position} className="border-t border-slate-200 pt-3"><h3 className="mb-2 font-semibold">{position}</h3><Breakdown result={option} /></div>)}</div>
  </details>
}

export function HistoryDetails({ history }: { history: HistoryEntry[] }) {
  return <details className="rounded-lg border border-slate-200 p-3">
    <summary className="cursor-pointer font-medium">Riwayat penilaian sebelumnya ({history.length})</summary>
    <ul className="mt-2 space-y-2 text-sm">{[...history].reverse().map((entry, i) => <li key={i} className="border-t border-slate-200 pt-2">
      <strong>{entry.assessment.score}/100</strong>
      {entry.assessed_at && ' · dinilai ' + new Date(entry.assessed_at).toLocaleString('id-ID')}
      {' · dinilai ulang oleh ' + entry.replaced_by + ' pada ' + new Date(entry.replaced_at).toLocaleString('id-ID')}
      <p className="text-slate-600">{entry.assessment.summary}</p>
    </li>)}</ul>
  </details>
}

export default function ScoreExplanation({ result, assessedAt, history }: {
  result: AssessmentResult; assessedAt: string | null; history: HistoryEntry[]
}) {
  const weights = result.trace?.weights ?? null
  return <div className="space-y-4">
    {result.primary && <p className="text-sm"><strong>Posisi utama</strong> · {result.primary}. Prioritas {result.priorities?.join(' → ')}.</p>}
    {weights && <ScoreMath result={result} weights={weights} />}
    {!weights && result.score_reasoning && <p className="text-sm"><strong>Alasan AI:</strong> {result.score_reasoning}</p>}
    <Breakdown result={result} weights={weights} />
    {result.options && <OptionsDetails options={result.options} />}
    {result.trace ? <TraceDetails trace={result.trace} assessedAt={assessedAt} />
      : <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-700">Penilaian ini dibuat sebelum rincian transparansi tersedia. Nilai ulang untuk melihat data yang dilihat AI dan bukti per kategori.</p>}
    {history.length > 0 && <HistoryDetails history={history} />}
  </div>
}
