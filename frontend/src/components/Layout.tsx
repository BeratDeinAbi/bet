import { Outlet, NavLink } from 'react-router-dom'
import { Activity, BarChart2, Zap } from 'lucide-react'
import { useState } from 'react'
import Top3Modal from './Top3Modal'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import clsx from 'clsx'

export default function Layout() {
  const [top3Open, setTop3Open] = useState(false)
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false })

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#0f0f0f' }}>
      {/* Header */}
      <header className="border-b border-surface-border px-6 py-3 flex items-center justify-between sticky top-0 z-50" style={{ background: '#111111' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent-green/20 flex items-center justify-center">
            <Activity className="w-4 h-4 text-accent-green" />
          </div>
          <span className="font-display font-bold text-white text-lg tracking-tight">
            Prediction Dashboard
          </span>
          <span className={clsx(
            'text-xs px-2 py-0.5 rounded-full font-medium ml-1',
            healthQuery.data ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
          )}>
            {healthQuery.data ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-1">
          <NavLink to="/" end className={({ isActive }) =>
            clsx('px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              isActive ? 'bg-surface-high text-white' : 'text-gray-400 hover:text-white hover:bg-surface-mid')
          }>
            Today
          </NavLink>
          <NavLink to="/backtests" className={({ isActive }) =>
            clsx('px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              isActive ? 'bg-surface-high text-white' : 'text-gray-400 hover:text-white hover:bg-surface-mid')
          }>
            Backtests
          </NavLink>
        </nav>

        <button
          onClick={() => setTop3Open(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all"
          style={{ background: 'linear-gradient(135deg, #8eff71 0%, #60a5fa 100%)', color: '#0f0f0f' }}
        >
          <Zap className="w-4 h-4" />
          Top 3 Picks
        </button>
      </header>

      <main className="flex-1 px-4 md:px-8 py-6 max-w-7xl mx-auto w-full">
        <Outlet />
      </main>

      {top3Open && <Top3Modal onClose={() => setTop3Open(false)} />}
    </div>
  )
}
