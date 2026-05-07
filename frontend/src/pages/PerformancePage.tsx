import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import clsx from 'clsx'
import { api, type RecentOutcome } from '../api/client'

const SPORT_LABEL: Record<string, string> = {
  football: 'Fußball',
  hockey: 'NHL',
  basketball: 'NBA',
  baseball: 'MLB',
}

const RANGE_OPTIONS = [
  { days: 7, label: '7 Tage' },
  { days: 30, label: '30 Tage' },
  { days: 90, label: '90 Tage' },
]

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: 'short',
  })
}

function PrimaryHitTag({ hit, market, prob }: {
  hit: boolean | null
  market: string | null
  prob: number | null
}) {
  if (hit === null || !market) {
    return <span className="text-text-quiet text-[10px]">—</span>
  }
  const label = market.replace(/_/g, ' ').replace('over ', 'O ').replace('under ', 'U ')
  const probPct = prob != null ? `${Math.round(prob * 100)}%` : ''
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={clsx(
          'w-1.5 h-1.5 rounded-full shrink-0',
          hit ? 'bg-pos' : 'bg-neg',
        )}
      />
      <span className="font-mono text-[10px] text-text-mute tabular-nums">
        {label} · {probPct}
      </span>
    </span>
  )
}

function OutcomeRow({ o }: { o: RecentOutcome }) {
  const totalErr = o.total_abs_error
  const errColor =
    totalErr < 0.5 ? 'text-pos' :
      totalErr < 1.5 ? 'text-warn' :
        'text-neg'

  return (
    <a
      href={`/match/${o.match_id}`}
      className="grid grid-cols-12 gap-3 items-center px-3 py-2.5 hover:bg-canvas-2 transition-colors text-[12px]"
    >
      <span className="col-span-2 smallcaps text-[10px] text-text-quiet">
        {o.league}
      </span>
      <span className="col-span-1 text-text-quiet text-[10px]">
        {formatDate(o.kickoff_time)}
      </span>
      <span className="col-span-3 text-text-dim truncate">
        {o.home_team}
      </span>
      <span className="col-span-1 font-display font-medium text-text tabular-nums text-center">
        {Math.round(o.actual_home)}–{Math.round(o.actual_away)}
      </span>
      <span className="col-span-3 text-text-dim truncate">
        {o.away_team}
      </span>
      <span className="col-span-1 text-right">
        <span className={clsx('font-mono text-[11px] tabular-nums', errColor)}>
          {totalErr.toFixed(2)}
        </span>
      </span>
      <span className="col-span-1 text-right">
        <PrimaryHitTag
          hit={o.primary_hit}
          market={o.primary_market}
          prob={o.primary_prob}
        />
      </span>
    </a>
  )
}

function SportFilterTabs({ value, onChange, available }: {
  value: string
  onChange: (s: string) => void
  available: Set<string>
}) {
  const opts = [
    { id: '', label: 'Alle' },
    ...Object.entries(SPORT_LABEL)
      .filter(([k]) => available.has(k))
      .map(([k, label]) => ({ id: k, label })),
  ]
  return (
    <div className="flex items-center gap-1">
      {opts.map(o => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={clsx(
            'px-3 py-1 rounded-md text-[12px] transition-colors',
            value === o.id
              ? 'bg-accent-soft text-accent-dim font-semibold'
              : 'text-text-mute hover:text-text hover:bg-canvas-2',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export default function PerformancePage() {
  const [days, setDays] = useState(30)
  const [sportFilter, setSportFilter] = useState('')

  const accuracyQuery = useQuery({
    queryKey: ['backtests', 'accuracy', days],
    queryFn: () => api.backtests.accuracy(days),
    refetchInterval: 60_000,
  })
  const recentQuery = useQuery({
    queryKey: ['backtests', 'recent', 50, sportFilter],
    queryFn: () => api.backtests.recent(50, sportFilter || undefined),
    refetchInterval: 60_000,
  })

  const acc = accuracyQuery.data
  const outcomes = recentQuery.data ?? []
  const availableSports = new Set(Object.keys(acc?.by_sport ?? {}))

  return (
    <div className="space-y-10">
      {/* Headline */}
      <header>
        <p className="smallcaps text-text-mute text-[11px] mb-1.5">
          Backtest · Self-Evaluation
        </p>
        <h1 className="font-display font-medium text-text text-[36px] sm:text-[44px] leading-[0.95] tracking-tighter2">
          Modell-<span className="italic font-normal text-accent">Trefferquote</span>.
        </h1>
        <p className="text-text-mute text-[14px] mt-2 max-w-xl">
          Jede Nacht um 04:00 wertet das Modell die fertigen Spiele aus,
          rekalibriert seine Wahrscheinlichkeiten und re-trainiert sich.
          So wird es täglich genauer.
        </p>
      </header>

      {/* Time-Range Tabs */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-1">
          {RANGE_OPTIONS.map(r => (
            <button
              key={r.days}
              onClick={() => setDays(r.days)}
              className={clsx(
                'px-3.5 py-1.5 rounded-md text-[12px] transition-colors',
                days === r.days
                  ? 'bg-accent text-canvas-1 font-semibold'
                  : 'text-text-mute hover:text-text hover:bg-canvas-2',
              )}
            >
              {r.label}
            </button>
          ))}
        </div>

        {availableSports.size > 0 && (
          <SportFilterTabs
            value={sportFilter}
            onChange={setSportFilter}
            available={availableSports}
          />
        )}
      </div>

      {/* KPI-Cards */}
      {acc && acc.n > 0 ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card p-5">
              <p className="smallcaps text-[10px] text-text-quiet mb-2">
                Top-Pick-Trefferquote
              </p>
              <p className="font-display font-medium text-text text-[44px] leading-none tabular-nums">
                {Math.round(acc.hit_rate * 100)}
                <span className="font-mono text-text-mute text-[18px] ml-1">%</span>
              </p>
              <p className="text-text-mute text-[11px] mt-2 font-mono">
                n = {acc.n} ausgewertete Spiele
              </p>
            </div>

            <div className="card p-5">
              <p className="smallcaps text-[10px] text-text-quiet mb-2">
                Ø Total-Fehler
              </p>
              <p className="font-display font-medium text-text text-[44px] leading-none tabular-nums">
                {acc.mae_total.toFixed(2)}
              </p>
              <p className="text-text-mute text-[11px] mt-2">
                Durchschnittlicher Tor-/Punkt-/Run-Fehler
              </p>
            </div>

            <div className="card p-5">
              <p className="smallcaps text-[10px] text-text-quiet mb-2">
                Bewertungsfenster
              </p>
              <p className="font-display font-medium text-text text-[44px] leading-none tabular-nums">
                {acc.days}
              </p>
              <p className="text-text-mute text-[11px] mt-2">
                Tage rolling
              </p>
            </div>
          </div>

          {/* Pro Sport */}
          {Object.keys(acc.by_sport).length > 0 && (
            <div className="card p-5">
              <p className="smallcaps text-[10px] text-text-quiet mb-4">
                Trefferquote pro Sport
              </p>
              <div className="space-y-3">
                {Object.entries(acc.by_sport).map(([sport, s]) => {
                  const pct = Math.round(s.hit_rate * 100)
                  return (
                    <div key={sport}>
                      <div className="flex items-baseline justify-between mb-1">
                        <span className="text-[13px] font-medium text-text-dim">
                          {SPORT_LABEL[sport] ?? sport}
                        </span>
                        <span className="font-mono text-[11px] text-text-mute tabular-nums">
                          <span className="text-text font-semibold">{pct}%</span>
                          {' · '}n={s.n}
                          {' · '}MAE {s.mae.toFixed(2)}
                        </span>
                      </div>
                      <div className="h-1.5 bg-canvas-3 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="card p-8">
          <p className="font-display text-text-dim text-lg italic mb-2">
            Noch keine ausgewerteten Spiele.
          </p>
          <p className="text-text-mute text-[13px]">
            Sobald Matches abgeschlossen sind, läuft der Backtest automatisch
            jede Nacht um 04:00 — oder manuell über{' '}
            <code className="font-mono text-accent-dim bg-canvas-2 px-1.5 py-0.5 rounded text-[11px]">
              POST /admin/daily-cycle
            </code>
          </p>
        </div>
      )}

      {/* Letzte Spiele Tabelle */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-canvas-line flex items-baseline justify-between">
          <h2 className="font-display text-text text-[20px]">
            Letzte ausgewertete Spiele
          </h2>
          <span className="font-mono text-[11px] text-text-mute">
            {outcomes.length} Einträge
          </span>
        </div>

        {recentQuery.isLoading ? (
          <div className="p-5 space-y-2">
            {[0, 1, 2, 3].map(i => (
              <div key={i} className="h-6 bg-canvas-2 rounded animate-pulse" />
            ))}
          </div>
        ) : outcomes.length === 0 ? (
          <p className="p-5 text-[12px] text-text-quiet italic">
            Keine ausgewerteten Spiele in der DB.
          </p>
        ) : (
          <div>
            <div className="grid grid-cols-12 gap-3 px-3 py-2 border-b border-canvas-line bg-canvas-2 text-[10px] uppercase tracking-wider text-text-quiet font-semibold">
              <span className="col-span-2">Liga</span>
              <span className="col-span-1">Datum</span>
              <span className="col-span-3">Heim</span>
              <span className="col-span-1 text-center">Score</span>
              <span className="col-span-3">Auswärts</span>
              <span className="col-span-1 text-right">Δ Total</span>
              <span className="col-span-1 text-right">Top-Pick</span>
            </div>
            <div className="divide-y divide-canvas-line">
              {outcomes.map(o => (
                <OutcomeRow key={o.id} o={o} />
              ))}
            </div>
          </div>
        )}
      </div>

      <p className="text-[11px] text-text-quiet">
        Δ Total = absoluter Fehler zwischen erwarteter und tatsächlicher
        Gesamttoranzahl. Top-Pick = O/U-Linie mit höchster Modell-Wahrscheinlichkeit
        des jeweiligen Spiels. Grün = Hit, rot = Miss.
      </p>
    </div>
  )
}
