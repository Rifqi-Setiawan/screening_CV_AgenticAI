// Small SVG/CSS charts for the score detail page. No chart library: the shapes are trivial and the
// page must stay light. Every chart has a text equivalent next to it, so colour is never the only signal.

const clamp = (value: number) => Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0

export function Donut({ value, label }: { value: number; label: string }) {
  const percent = clamp(value)
  const radius = 42
  const circumference = 2 * Math.PI * radius
  return <svg className="sd-donut" viewBox="0 0 100 100" role="img" aria-label={label}>
    <circle cx="50" cy="50" r={radius} fill="none" stroke="#eceef1" strokeWidth="11" />
    {percent > 0 && <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--accent-strong)" strokeWidth="11" strokeLinecap="round"
      strokeDasharray={circumference * percent / 100 + ' ' + circumference} transform="rotate(-90 50 50)" />}
    <text x="50" y="56" textAnchor="middle" className="sd-donut-text">{Math.round(percent)}%</text>
  </svg>
}

export function Gauge({ value, color, label }: { value: number; color: string; label: string }) {
  const percent = clamp(value)
  const length = Math.PI * 50
  const arc = 'M10 62 A50 50 0 0 1 110 62'
  return <svg className="sd-gauge" viewBox="0 0 120 72" role="img" aria-label={label}>
    <path d={arc} fill="none" stroke="#eceef1" strokeWidth="11" strokeLinecap="round" />
    {percent > 0 && <path d={arc} fill="none" stroke={color} strokeWidth="11" strokeLinecap="round" strokeDasharray={length * percent / 100 + ' ' + length} />}
    <text x="60" y="60" textAnchor="middle" className="sd-gauge-text">{Math.round(percent)}</text>
  </svg>
}

export function StackedBar({ segments, label }: { segments: { key: string; width: number; color: string; title: string }[]; label: string }) {
  return <div className="sd-track" role="img" aria-label={label}>
    {segments.map(segment => segment.width > 0 &&
      <span key={segment.key} className="sd-seg" style={{ width: segment.width + '%', background: segment.color }} title={segment.title} />)}
  </div>
}

export function MiniBars({ points, label }: { points: { score: number; label: string; current: boolean }[]; label: string }) {
  return <div className="sd-bars" role="img" aria-label={label}>
    {points.map((point, index) => <div key={index} className="sd-bar-col">
      <span className="sd-bar-value">{Math.round(point.score)}</span>
      <span className={'sd-bar' + (point.current ? ' current' : '')} style={{ height: Math.max(4, clamp(point.score) * 0.9) + 'px' }} />
      <small>{point.label}</small>
    </div>)}
  </div>
}
