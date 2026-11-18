import type { ReactNode } from 'react'

export function Mark() {
  return <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M5.6 18.4 18.4 5.6" stroke="currentColor" strokeWidth="3" /></svg></span>
}

export function Workspace({ role, title, navigation, actions, children }: {
  role: string; title: string; navigation: ReactNode; actions?: ReactNode; children: ReactNode
}) {
  return <div className="workspace">
    <aside className="workspace-sidebar">
      <a className="brand" href={role === 'Recruiter' ? '/app' : '/pelamar'}><Mark /><span><strong>TIG</strong><small>Recruitment workspace</small></span></a>
      <div className="workspace-role"><span className="role-dot" />{role}</div>
      <nav aria-label="Navigasi workspace">{navigation}</nav>
      <div className="sidebar-note"><strong>Penilaian yang dapat ditelusuri.</strong><p>AI membantu membaca kecocokan. Keputusan tetap di tangan tim rekrutmen.</p></div>
    </aside>
    <div className="workspace-main">
      <header className="workspace-toolbar"><span>Workspace <span aria-hidden="true">/</span> <strong>{title}</strong></span><div className="toolbar-actions">{actions}</div></header>
      <main className="workspace-content">{children}</main>
    </div>
  </div>
}

export function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="page-heading"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return <main className="auth-layout"><aside className="auth-intro"><a className="brand" href="/app"><Mark /><span><strong>TIG</strong><small>Recruitment workspace</small></span></a><div><p className="eyebrow">REKRUTMEN · BERBASIS BUKTI</p><h1>Kenali kecocokan.<br />Pahami alasannya.</h1><p>Formulir yang terstruktur, penilaian yang transparan, dan keputusan oleh manusia.</p></div><p className="auth-footnote">Data pribadi bukan ukuran kompetensi.</p></aside><div className="auth-content">{children}</div></main>
}

export function Metric({ label, value, description }: { label: string; value: ReactNode; description: string }) {
  return <div className="metric"><dt>{label}</dt><dd>{value}</dd><p>{description}</p></div>
}
