import { Outlet, NavLink } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { useState } from 'react'
import Top3Modal from './Top3Modal'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import clsx from 'clsx'

export default function Layout() {
  const [top3Open, setTop3Open] = useState(false)
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false })

  return (
    <div className="min-h-screen flex flex-col bg-[#0d0d0d]">
      <header className="border-b border-surface-border px-6 flex items-center justify-between sticky top-0 z-50 bg-[#0d0d0d]/95 backdrop-blur-sm" style={{ height: 52 }}>
        <div className="flex items-center gap-3">
          <span className="font-display font-extrabold text-white tracking-tight" style={{ fontSize: 15 }}>
            Prediction<span className="text-accent-green">.</span>
          </span>
          <span className={clsx(
            'text-[10px] px-1.5 py-0.5 rounded font-bold tracking-widest uppercase',
            healthQuery.data
              ? 'bg-accent-green/15 text-accent-green'
              : 'bg-red-500/15 text-red-400'
          )}>
            {healthQuery.data ? 'Live' : 'Offline'}
          </span>
        </div>

        <nav className="flex items-center h-full">
          {[
            { to: '/', label: 'Today', end: true },
            { to: '/backtests', label: 'Backtests', end: false },
          ].map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'px-4 h-full flex items-center text-sm font-medium border-b-2 transition-colors',
                  isActive
                    ? 'border-white text-white'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                )
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={() => setTop3Open(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-accent-green text-[#0d0d0d] text-sm font-bold hover:opacity-90 transition-opacity"
        >
          <Zap className="w-3.5 h-3.5" />
          Top 3
        </button>
      </header>

      <main className="flex-1 px-4 md:px-8 py-6 max-w-7xl mx-auto w-full">
        <Outlet />
      </main>

      {top3Open && <Top3Modal onClose={() => setTop3Open(false)} />}
    </div>
  )
}
