import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Filter, AlertCircle, Loader2, Database } from 'lucide-react'
import { api } from '../api/client'
import MatchCard from '../components/MatchCard'
import clsx from 'clsx'

const SPORTS = [
  { value: '', label: 'Alle' },
  { value: 'football', label: '⚽ Fußball' },
  { value: 'hockey', label: '🏒 Eishockey' },
  { value: 'basketball', label: '🏀 Basketball' },
]

const LEAGUES = [
  { value: '', label: 'Alle Ligen' },
  { value: 'BL1', label: 'Bundesliga' },
  { value: 'BL2', label: '2. Bundesliga' },
  { value: 'PL', label: 'Premier League' },
  { value: 'PD', label: 'La Liga' },
  { value: 'SSL', label: 'Süper Lig' },
  { value: 'NHL', label: 'NHL' },
  { value: 'NBA', label: 'NBA' },
]

export default function Dashboard() {
  const [sport, setSport] = useState('')
  const [league, setLeague] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['predictions', 'today', sport, league],
    queryFn: () => api.predictions.today({ sport: sport || undefined, league: league || undefined }),
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
    onSuccess: () => {
      setTimeout(() => refetch(), 2000)
    },
  })

  const today = new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display font-bold text-white text-2xl">Heute &amp; Morgen</h1>
          <p className="text-gray-500 text-sm mt-0.5">{today} · inkl. anstehender Partien (nächste 36h)</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-surface-border text-gray-400 hover:text-white hover:border-gray-600 transition-colors disabled:opacity-50"
          >
            {seedMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
            Daten laden
          </button>
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-surface-border text-gray-400 hover:text-white hover:border-gray-600 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={clsx('w-4 h-4', refreshMutation.isPending && 'animate-spin')} />
            Aktualisieren
          </button>
        </div>
      </div>

      {/* Seed Result */}
      {seedMutation.data && (
        <div className="mb-4 p-3 rounded-lg bg-accent-green/10 border border-accent-green/20 text-accent-green text-sm">
          Daten geladen: {seedMutation.data.matches_ingested} Spiele, {seedMutation.data.predictions_generated} Prognosen
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <Filter className="w-4 h-4 text-gray-500" />
        <div className="flex gap-1">
          {SPORTS.map(s => (
            <button
              key={s.value}
              onClick={() => { setSport(s.value); setLeague('') }}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                sport === s.value
                  ? 'bg-surface-high text-white'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-surface-mid'
              )}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-surface-border" />

        <div className="flex gap-1 flex-wrap">
          {LEAGUES
            .filter(l => !sport || l.value === '' ||
              (sport === 'football' && ['BL1','BL2','PL','PD','SSL'].includes(l.value)) ||
              (sport === 'hockey' && l.value === 'NHL') ||
              (sport === 'basketball' && l.value === 'NBA'))
            .map(l => (
              <button
                key={l.value}
                onClick={() => setLeague(l.value)}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                  league === l.value
                    ? 'bg-surface-high text-white'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-surface-mid'
                )}
              >
                {l.label}
              </button>
            ))}
        </div>
      </div>

      {/* States */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-20 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Lade Prognosen...</span>
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <AlertCircle className="w-10 h-10 text-accent-red opacity-60" />
          <div>
            <p className="text-white font-medium">Backend nicht erreichbar</p>
            <p className="text-gray-500 text-sm mt-1">
              Starte das Backend: <code className="text-accent-blue">cd backend && uvicorn main:app --reload</code>
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && data?.length === 0 && (
        <div className="text-center py-16">
          <p className="text-white font-medium mb-2">Keine Prognosen für heute</p>
          <p className="text-gray-500 text-sm">
            Klicke <strong>Daten laden</strong> um Spiele und Prognosen zu generieren.
          </p>
        </div>
      )}

      {/* Match Grid */}
      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.map(pred => (
            <MatchCard key={pred.id} prediction={pred} />
          ))}
        </div>
      )}

      {data && data.length > 0 && (
        <p className="text-center text-gray-600 text-xs mt-8">
          {data.length} Prognose{data.length !== 1 ? 'n' : ''} · Powered by Poisson + Dixon-Coles Ensemble
        </p>
      )}
    </div>
  )
}
