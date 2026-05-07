import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api/client'
import MatchCard from '../components/MatchCard'

/**
 * Dashboard — Editorial-Layout.
 *
 * Hierarchie:
 *  1. Datums-Eyebrow (klein, smallcaps)
 *  2. Headline „Heutige Prognosen" als Serif
 *  3. Lead-Zeile mit Anzahl Spiele/Prognosen
 *  4. Filter-Bar als ruhige Inline-Liste, nicht als Tab-Border-Bottom
 *  5. Match-Grid 2-spaltig auf Desktop (großzügiger als 3-spaltig)
 *
 * Bewusste Entscheidung: keine Emoji-Liga-Tags mehr.  Die Liga steht
 * als reiner Text-Tag in den Karten — Emojis sehen nach „AI-cute" aus.
 */

const CATEGORIES = [
  { league: '', sport: '', label: 'Alles' },
  { league: 'BL1', sport: 'football', label: 'Bundesliga' },
  { league: 'BL2', sport: 'football', label: '2. Bundesliga' },
  { league: 'PL', sport: 'football', label: 'Premier League' },
  { league: 'PD', sport: 'football', label: 'La Liga' },
  { league: 'SSL', sport: 'football', label: 'Süper Lig' },
  { league: 'NHL', sport: 'hockey', label: 'NHL' },
  { league: 'NBA', sport: 'basketball', label: 'NBA' },
  { league: 'MLB', sport: 'baseball', label: 'MLB' },
]

export default function Dashboard() {
  const [selected, setSelected] = useState('')
  const queryClient = useQueryClient()

  const active = CATEGORIES.find(c => c.league === selected) ?? CATEGORIES[0]

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['predictions', 'today', selected],
    queryFn: () =>
      api.predictions.today({
        sport: active.sport || undefined,
        league: active.league || undefined,
      }),
  })

  const seedMutation = useMutation({
    mutationFn: api.admin.seed,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
    },
  })

  const refreshMutation = useMutation({
    mutationFn: api.admin.refresh,
    onSuccess: () => setTimeout(() => refetch(), 2000),
  })

  const now = new Date()
  const dateLong = now.toLocaleDateString('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="space-y-12">
      {/* ────────  Eyebrow + Headline  ──────── */}
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6">
        <div>
          <p className="smallcaps text-paper-mute text-[11px] mb-2">
            {dateLong}
          </p>
          <h1 className="font-display font-medium text-paper text-[44px] sm:text-[56px] leading-[0.95] tracking-tighter2">
            Heutige <span className="italic font-normal">Prognosen</span>.
          </h1>
          <p className="text-paper-mute text-[14px] mt-3 max-w-xl">
            {data && data.length > 0
              ? `${data.length} Spiele in den nächsten 36 Stunden — Tor-, Punkt- und Run-Modelle, kalibriert mit Time-Decay und Liga-Priors.`
              : 'Tor-, Punkt- und Run-Modelle für die nächsten 36 Stunden.'}
          </p>
        </div>

        <div className="flex items-center gap-5 text-[13px] shrink-0 mt-2">
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="text-paper-mute hover:text-paper transition-colors disabled:opacity-40 underline-offset-4 hover:underline decoration-signal/60"
          >
            {seedMutation.isPending ? 'Lade…' : 'Daten laden'}
          </button>
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="text-paper-mute hover:text-paper transition-colors disabled:opacity-40 underline-offset-4 hover:underline decoration-signal/60"
          >
            {refreshMutation.isPending ? 'Aktualisiere…' : 'Aktualisieren'}
          </button>
        </div>
      </header>

      {seedMutation.data && (
        <div className="rule pt-3 text-[12px] text-paper-mute">
          Geladen: <span className="text-paper font-mono">{seedMutation.data.matches_ingested}</span>{' '}
          Spiele ·{' '}
          <span className="text-paper font-mono">
            {seedMutation.data.predictions_generated}
          </span>{' '}
          Prognosen
        </div>
      )}

      {/* ────────  Filter-Bar  ──────── */}
      <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 -mt-4 pb-1 border-b border-ink-line">
        {CATEGORIES.map(c => {
          const isActive = selected === c.league
          return (
            <button
              key={c.league || 'all'}
              onClick={() => setSelected(c.league)}
              className={clsx(
                'text-[13px] tracking-tight transition-colors pb-2 -mb-[1px] relative',
                isActive
                  ? 'text-paper'
                  : 'text-paper-quiet hover:text-paper-dim',
              )}
            >
              {c.label}
              {isActive && (
                <span className="absolute -bottom-[1px] left-0 right-0 h-px bg-signal" />
              )}
            </button>
          )
        })}
      </nav>

      {/* ────────  Body  ──────── */}
      {isLoading && <Skeletons />}

      {isError && (
        <div className="flex flex-col items-start gap-3 py-12 max-w-md">
          <AlertCircle className="w-5 h-5 text-neg" />
          <div>
            <p className="font-display font-medium text-paper text-lg">
              Backend nicht erreichbar.
            </p>
            <p className="text-paper-mute text-[13px] mt-1.5">
              Starte das API in einem Terminal:
            </p>
            <code className="block mt-2 text-[12px] font-mono text-signal-high">
              cd backend && uvicorn main:app --reload
            </code>
          </div>
        </div>
      )}

      {!isLoading && !isError && data?.length === 0 && (
        <div className="py-12 max-w-md">
          <p className="font-display text-paper-dim text-lg italic">
            Keine Prognosen vorhanden.
          </p>
          <p className="text-paper-mute text-[13px] mt-1.5">
            Klick auf{' '}
            <button
              onClick={() => seedMutation.mutate()}
              className="text-signal underline underline-offset-4 hover:text-signal-high"
            >
              Daten laden
            </button>{' '}
            um Spiele und Modelle aufzubauen.
          </p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-10">
          {data.map(pred => (
            <MatchCard key={pred.id} prediction={pred} />
          ))}
        </div>
      )}
    </div>
  )
}

function Skeletons() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8 gap-y-10">
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="space-y-4 animate-pulse">
          <div className="h-3 w-20 bg-ink-2 rounded" />
          <div className="h-6 w-3/5 bg-ink-2 rounded" />
          <div className="h-6 w-2/5 bg-ink-2 rounded" />
          <div className="rule pt-4 grid grid-cols-2 gap-3">
            <div className="h-2 bg-ink-2 rounded" />
            <div className="h-2 bg-ink-2 rounded" />
            <div className="h-2 bg-ink-2 rounded" />
            <div className="h-2 bg-ink-2 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}
