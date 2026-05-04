import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, AlertCircle, Loader2, Database } from 'lucide-react'
import { api } from '../api/client'
import MatchCard from '../components/MatchCard'
import clsx from 'clsx'

const CATEGORIES = [
  { league: '',     sport: '',            label: 'Alles' },
  { league: 'BL1',  sport: 'football',   label: '⚽ Bundesliga' },
  { league: 'BL2',  sport: 'football',   label: '⚽ 2. Bundesliga' },
  { league: 'PL',   sport: 'football',   label: '⚽ Premier League' },
  { league: 'PD',   sport: 'football',   label: '⚽ La Liga' },
  { league: 'SSL',  sport: 'football',   label: '⚽ Süper Lig' },
  { league: 'NHL',  sport: 'hockey',     label: '🏒 NHL' },
  { league: 'NBA',  sport: 'basketball', label: '🏀 NBA' },
  { league: 'MLB',  sport: 'baseball',   label: '⚾ MLB' },
]

export default function Dashboard() {
  const [selected, setSelected] = useState('')
  const queryClient = useQueryClient()

  const active = CATEGORIES.find(c => c.league === selected) ?? CATEGORIES[0]

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['predictions', 'today', selected],
    queryFn: () => api.predictions.today({
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

  const today = new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="font-display font-bold text-white text-2xl leading-tight">{today}</h1>
          <p className="text-gray-600 text-sm mt-0.5">
            Nächste 36 h · {data ? `${data.length} Prognosen` : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-white border border-surface-border hover:border-gray-600 transition-colors disabled:opacity-40"
          >
            {seedMutation.isPending
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Database className="w-3.5 h-3.5" />}
            Daten laden
          </button>
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-white border border-surface-border hover:border-gray-600 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={clsx('w-3.5 h-3.5', refreshMutation.isPending && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {seedMutation.data && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-accent-green/10 border border-accent-green/20 text-accent-green text-xs">
          {seedMutation.data.matches_ingested} Spiele · {seedMutation.data.predictions_generated} Prognosen geladen
        </div>
      )}

      {/* Tab filter */}
      <div className="flex overflow-x-auto scrollbar-hide border-b border-surface-border mb-6">
        {CATEGORIES.map(c => (
          <button
            key={c.league}
            onClick={() => setSelected(c.league)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium whitespace-nowrap shrink-0 transition-colors border-b-2 -mb-px',
              selected === c.league
                ? 'border-accent-green text-white'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* States */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-20 text-gray-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Laden...</span>
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <AlertCircle className="w-8 h-8 text-red-500/50" />
          <div>
            <p className="text-white text-sm font-medium">Backend nicht erreichbar</p>
            <p className="text-gray-600 text-xs mt-1">
              <code className="text-accent-blue">cd backend && uvicorn main:app --reload</code>
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && data?.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-400 text-sm">Keine Prognosen vorhanden.</p>
          <p className="text-gray-600 text-xs mt-1">
            Klicke auf <span className="text-gray-400 font-medium">Daten laden</span>.
          </p>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {data.map(pred => (
            <MatchCard key={pred.id} prediction={pred} />
          ))}
        </div>
      )}
    </div>
  )
}
