import { Outlet, NavLink } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import Top3Modal from './Top3Modal'
import { api } from '../api/client'

/**
 * Header-Anatomie:
 *  - Serif-Wordmark links, kein Tech-Logo, kein Emoji.
 *  - Live-Status als kleiner Punkt (kein Pill mit „LIVE"-Caps-Lock).
 *  - Nav als unterstrichene Links — Akzent-Underline statt voll-bordy
 *    Tab-Indicator.
 *  - „Top 3"-CTA als Inline-Link mit Akzent-Pfeil statt grünem Block.
 */
export default function Layout() {
  const [top3Open, setTop3Open] = useState(false)
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    retry: false,
  })

  return (
    <div className="min-h-screen flex flex-col bg-ink">
      <header className="sticky top-0 z-40 backdrop-blur-md bg-ink/85 border-b border-ink-line">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-14 flex items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="font-display font-semibold text-paper text-[19px] tracking-tighter2 leading-none">
              <span className="italic">b</span>riefing
            </span>
            <span
              className={clsx(
                'inline-block w-1.5 h-1.5 rounded-full',
                healthQuery.data ? 'bg-pos' : 'bg-neg',
              )}
              title={healthQuery.data ? 'API live' : 'API offline'}
            />
          </div>

          <nav className="hidden sm:flex items-center gap-6">
            {[
              { to: '/', label: 'Heute', end: true },
              { to: '/backtests', label: 'Modellgüte', end: false },
            ].map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    'text-[13px] font-medium tracking-tight transition-colors relative py-1',
                    isActive
                      ? 'text-paper'
                      : 'text-paper-mute hover:text-paper-dim',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {label}
                    {isActive && (
                      <span className="absolute -bottom-[1px] left-0 right-0 h-px bg-signal" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          <button
            onClick={() => setTop3Open(true)}
            className="group flex items-center gap-2 text-[13px] font-medium text-paper-dim hover:text-paper transition-colors"
          >
            <span className="font-display italic text-signal text-[15px] leading-none">→</span>
            Top 3 heute
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full px-5 sm:px-8 py-8 sm:py-12">
        <Outlet />
      </main>

      <footer className="border-t border-ink-line text-paper-quiet text-[11px]">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-4 flex flex-col sm:flex-row justify-between gap-1">
          <span>
            <span className="font-display italic">briefing</span> · Tor-, Punkt-
            und Run-Modelle für Fußball, NHL, NBA, MLB
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
