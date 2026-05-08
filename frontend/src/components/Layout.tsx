import { Outlet, NavLink, Link } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sun, Moon } from 'lucide-react'
import clsx from 'clsx'
import Top3Modal from './Top3Modal'
import { api } from '../api/client'
import { useTheme } from '../hooks/useTheme'

/**
 * ThePredicter — Top-Level-Layout.
 *
 * Header: Wordmark, Tab-Navigation (Heute / Modellgüte), Top-3-Trigger.
 * Body: Routes rendern in den Outlet — das Dashboard bringt eigene
 *   linke Sport-Sidebar mit, andere Seiten nutzen die volle Breite.
 */
export default function Layout() {
  const [top3Open, setTop3Open] = useState(false)
  const [theme, toggleTheme] = useTheme()
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    retry: false,
    refetchInterval: 30_000,
  })

  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      <header className="sticky top-0 z-40 bg-canvas-1/95 backdrop-blur-md border-b border-canvas-border">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-14 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2.5 group">
            <span className="font-display font-semibold text-text text-[20px] tracking-tighter2 leading-none">
              The<span className="italic font-medium text-accent">Predicter</span>
            </span>
            <span
              className={clsx(
                'inline-block w-1.5 h-1.5 rounded-full',
                healthQuery.data ? 'bg-pos' : 'bg-neg',
              )}
              title={healthQuery.data ? 'API live' : 'API offline'}
            />
          </Link>

          <nav className="hidden sm:flex items-center gap-1">
            {[
              { to: '/', label: 'Heute', end: true },
              { to: '/performance', label: 'Modellgüte', end: false },
              { to: '/backtests', label: 'Backtest-Details', end: false },
            ].map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    'text-[13px] font-medium tracking-tight transition-colors px-3 py-1.5 rounded-md',
                    isActive
                      ? 'bg-accent-soft text-accent-dim'
                      : 'text-text-mute hover:text-text hover:bg-canvas-2',
                  )
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              title={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              className="p-2 rounded-md text-text-mute hover:text-text hover:bg-canvas-2 transition-colors"
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={() => setTop3Open(true)}
              className="flex items-center gap-2 text-[13px] font-semibold text-canvas-1 bg-accent hover:bg-accent-bright transition-colors px-3.5 py-1.5 rounded-md"
            >
              <span className="leading-none">→</span>
              Top 3 heute
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-5 sm:px-8 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-canvas-line text-text-quiet text-[11px] mt-auto">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-4 flex flex-col sm:flex-row justify-between gap-1">
          <span>
            <span className="font-display italic">ThePredicter</span> · Tor-,
            Punkt- und Run-Modelle für Fußball, NHL, NBA, MLB
          </span>
          <span className="hidden sm:inline">
            Daten: OpenLigaDB · ESPN · NHL · MLB Stats API
          </span>
        </div>
      </footer>

      {top3Open && <Top3Modal onClose={() => setTop3Open(false)} />}
    </div>
  )
}
