import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import MatchCard from '../components/MatchCard'
import SportSidebar, { type SportSelection } from '../components/SportSidebar'

export default function Dashboard() {
  const [selected, setSelected] = useState<SportSelection>({ league: '', sport: '' })
  const queryClient = useQueryClient()

  // Wir laden immer ALLE Predictions, filtern client-seitig.  Das ist
  // billiger als pro Filter-Klick einen Server-Round-Trip — unter 200
  // Karten ist React schnell genug.  Ausserdem brauchen wir die Counts
  // pro Liga für die Sidebar.
  const { data: allPredictions, isLoading, isError } = useQuery({
    queryKey: ['predictions', 'today', 'all'],
    queryFn: () => api.predictions.today(),
  })

  const seedMutation = useMutation({
    mutationFn: api.admin.seed,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
      queryClient.invalidateQueries({ queryKey: ['backtests'] })
    },
  })

  const refreshMutation = useMutation({
    mutationFn: api.admin.refresh,
    onSuccess: () => setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
    }, 2000),
  })

  // Counts pro Liga + Total — für die Sidebar
  const counts = useMemo(() => {
    const out: Record<string, number> = { __total: 0 }
    if (!allPredictions) return out
    for (const p of allPredictions) {
      out.__total++
      out[p.league] = (out[p.league] ?? 0) + 1
    }
    return out
  }, [allPredictions])

  const filteredPredictions = useMemo(() => {
    if (!allPredictions) return []
    if (!selected.league) return allPredictions
    return allPredictions.filter(p => p.league === selected.league)
  }, [allPredictions, selected.league])

  const now = new Date()
  const dateLong = now.toLocaleDateString('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-x-10 gap-y-6">
      {/* ───────  Linke Sport-Sidebar  ─────── */}
      <aside className="lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-2 -mr-2">
        <SportSidebar
          selected={selected}
          onChange={setSelected}
          counts={counts}
        />
      </aside>

      {/* ───────  Hauptbereich  ─────── */}
      <div className="space-y-8 min-w-0">
        <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <p className="smallcaps text-text-mute text-[11px] mb-1.5">
              {dateLong}
            </p>
            <h1 className="font-display font-medium text-text text-[36px] sm:text-[44px] leading-[0.95] tracking-tighter2">
              Heutige <span className="italic font-normal text-accent">Prognosen</span>.
            </h1>
            <p className="text-text-mute text-[14px] mt-2 max-w-xl">
              {filteredPredictions.length > 0
                ? `${filteredPredictions.length} Spiele in den nächsten 36 Stunden — kalibriert mit Time-Decay und Liga-Priors.`
                : 'Tor-, Punkt- und Run-Modelle für die nächsten 36 Stunden.'}
            </p>
          </div>

          <div className="flex items-center gap-4 text-[13px] shrink-0">
            <button
              onClick={() => seedMutation.mutate()}
              disabled={seedMutation.isPending}
              className="text-text-mute hover:text-text transition-colors disabled:opacity-40 underline-offset-4 hover:underline decoration-accent/60"
            >
              {seedMutation.isPending ? 'Lade…' : 'Daten laden'}
            </button>
            <button
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              className="text-text-mute hover:text-text transition-colors disabled:opacity-40 underline-offset-4 hover:underline decoration-accent/60"
            >
              {refreshMutation.isPending ? 'Aktualisiere…' : 'Aktualisieren'}
            </button>
          </div>
        </header>

        {seedMutation.data && (
          <div className="rule pt-3 text-[12px] text-text-mute">
            Geladen:{' '}
            <span className="text-text font-mono">
              {seedMutation.data.matches_ingested}
            </span>{' '}
            Spiele ·{' '}
            <span className="text-text font-mono">
              {seedMutation.data.predictions_generated}
            </span>{' '}
            Prognosen
          </div>
        )}

        {/* States */}
        {isLoading && <Skeletons />}

        {isError && (
          <div className="card p-6 max-w-md">
            <div className="flex flex-col items-start gap-3">
              <AlertCircle className="w-5 h-5 text-neg" />
              <div>
                <p className="font-display font-medium text-text text-lg">
                  Backend nicht erreichbar.
                </p>
                <p className="text-text-mute text-[13px] mt-1.5">
                  Starte das API in einem Terminal:
                </p>
                <code className="block mt-2 text-[12px] font-mono text-accent-dim bg-canvas-2 px-2 py-1 rounded">
                  cd backend && uvicorn main:app --reload
                </code>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !isError && filteredPredictions.length === 0 && (
          <div className="card p-8 max-w-md">
            <p className="font-display text-text-dim text-lg italic">
              {selected.league
                ? `Keine Prognosen für ${selected.league}.`
                : 'Keine Prognosen vorhanden.'}
            </p>
            <p className="text-text-mute text-[13px] mt-2">
              {selected.league
                ? 'Wähle eine andere Liga oder lade Daten neu.'
                : 'Klick auf '}
              {!selected.league && (
                <button
                  onClick={() => seedMutation.mutate()}
                  className="text-accent underline underline-offset-4 hover:text-accent-bright"
                >
                  Daten laden
                </button>
              )}
              {!selected.league && ' um Spiele und Modelle aufzubauen.'}
            </p>
          </div>
        )}

        {filteredPredictions.length > 0 && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6 gap-y-8">
            {filteredPredictions.map(pred => (
              <MatchCard key={pred.id} prediction={pred} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Skeletons() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-6 gap-y-8">
      {[0, 1, 2, 3].map(i => (
        <div key={i} className="card p-5 space-y-4 animate-pulse">
          <div className="h-3 w-20 bg-canvas-3 rounded" />
          <div className="h-6 w-3/5 bg-canvas-3 rounded" />
          <div className="h-6 w-2/5 bg-canvas-3 rounded" />
          <div className="rule pt-4 grid grid-cols-2 gap-3">
            <div className="h-2 bg-canvas-3 rounded" />
            <div className="h-2 bg-canvas-3 rounded" />
            <div className="h-2 bg-canvas-3 rounded" />
            <div className="h-2 bg-canvas-3 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}
