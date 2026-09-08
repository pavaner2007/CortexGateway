import { type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

interface NavItem {
  icon: ReactNode
  label: string
  to: string
}

const navItems: NavItem[] = [
  {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
    label: 'Dashboard',
    to: '/',
  },
]

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-64 flex-shrink-0 flex flex-col border-r border-white/5 bg-surface-900/80 backdrop-blur-xl">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shadow-lg glow-brand">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
            </svg>
          </div>
          <div>
            <span className="text-sm font-bold text-slate-100 block leading-tight">Cortex</span>
            <span className="text-xs text-brand-400 font-semibold tracking-widest uppercase">Gateway</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            Navigation
          </p>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                ['nav-item', isActive ? 'nav-item--active' : ''].join(' ')
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/5">
          <p className="text-[11px] text-slate-600 font-medium">Phase 1 — Foundation</p>
          <p className="text-[10px] text-slate-700 mt-0.5">v1.0.0</p>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <header className="sticky top-0 z-10 flex items-center justify-between px-8 py-4 border-b border-white/5 bg-surface-950/80 backdrop-blur-xl">
          <div>
            <h1 className="text-lg font-semibold text-slate-100">Dashboard</h1>
            <p className="text-xs text-slate-500 mt-0.5">System overview and health status</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
            <span className="status-dot status-dot--healthy" />
            <span className="text-xs text-slate-400 font-medium">Live</span>
          </div>
        </header>

        <div className="p-8 animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  )
}
