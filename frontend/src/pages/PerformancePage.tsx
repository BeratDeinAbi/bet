import { useQuery } from '@tanstack/react-query'
import { useState, useMemo } from 'react'
import clsx from 'clsx'
import { api, type RecentOutcome, type RecommendedPick } from '../api/client'

const SPORT_ORDER = ['football', 'hockey', 'basketball', 'baseball'] as const
type SportKey = (typeof SPORT_ORDER)[number]

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

// ────────────────────────────────────────────────────────────────────
//  Outcomes (alle ausgewerteten Predictions, gruppiert pro Sport)
// ────────────────────────────────────────────────────────────────────

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
      <span className={clsx(
        'w-1.5 h-1.5 rounded-full shrink-0',
        hit ? 'bg-pos' : 'bg-neg',
      )} />
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

function SportOutcomeTable({ sport, outcomes }: {
  sport: SportKey
  outcomes: RecentOutcome[]
}) {
  if (outcomes.length === 0) return null
  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-canvas-line flex items-baseline justify-between">
        <h3 className="font-display text-text text-[18px]">
          {SPORT_LABEL[sport]}
        </h3>
        <span className="font-mono text-[11px] text-text-mute">
          {outcomes.length} Spiele
        </span>
      </div>
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
        {outcomes.map(o => <OutcomeRow key={o.id} o={o} />)}
      </div>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────
//  Recommended Picks (Wett-Empfehlungen ≥ 1.25)
// ────────────────────────────────────────────────────────────────────

function PickResultCell({ pick }: { pick: RecommendedPick }) {
  if (pick.actual_hit === null) {
    return (
      <span className="font-mono text-[10px] text-text-quiet">
        {pick.match_status === 'FINISHED' ? 'n.b.' : 'offen'}
      </span>
    )
  }
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold',
      pick.actual_hit ? 'text-pos' : 'text-neg',
    )}>
      <span className={clsx(
        'w-1.5 h-1.5 rounded-full',
        pick.actual_hit ? 'bg-pos' : 'bg-neg',
      )} />
      {pick.actual_hit ? 'Hit' : 'Miss'}
    </span>
  )
}

function PickRow({ pick }: { pick: RecommendedPick }) {
  const directionLabel = pick.direction === 'over' ? 'O' : 'U'
  const probPct = Math.round(pick.model_probability * 100)
  return (
    <a
      href={`/match/${pick.match_id}`}
      className="grid grid-cols-12 gap-3 items-center px-3 py-2.5 hover:bg-canvas-2 transition-colors text-[12px]"
    >
      <span className="col-span-2 smallcaps text-[10px] text-text-quiet">
        {pick.league}
      </span>
      <span className="col-span-1 text-text-quiet text-[10px]">
        {formatDate(pick.kickoff_time)}
      </span>
      <span className="col-span-3 text-text-dim truncate">
        {pick.home_team} <span className="text-text-quiet">vs</span> {pick.away_team}
      </span>
      <span className="col-span-2 text-text font-medium">
        {directionLabel} {pick.line} <span className="text-text-quiet text-[10px]">{pick.market}</span>
      </span>
      <span className="col-span-1 font-mono text-[11px] text-accent-dim tabular-nums text-right">
        {probPct}%
      </span>
      <span className="col-span-1 font-mono text-[11px] text-text-dim tabular-nums text-right">
        {pick.fair_odds.toFixed(2)}
      </span>
      <span className="col-span-1 text-right">
        {pick.actual_total !== null ? (
          <span className="font-mono text-[10px] text-text-mute">
            {pick.actual_total.toFixed(0)}
          </span>
        ) : (
          <span className="text-text-quiet text-[10px]">—</span>
        )}
      </span>
      <span className="col-span-1 text-right">
        <PickResultCell pick={pick} />
      </span>
    </a>
  )
}

function SportPicksTable({ sport, picks, hitRate, n }: {
  sport: SportKey
  picks: RecommendedPick[]
  hitRate?: number
  n?: number
}) {
  if (picks.length === 0) return null
  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-canvas-line flex items-baseline justify-between gap-3">
        <h3 className="font-display text-text text-[18px]">
          {SPORT_LABEL[sport]}
        </h3>
        <div className="flex items-center gap-4 text-[11px]">
          {n !== undefined && n > 0 && hitRate !== undefined && (
            <span className="font-mono text-text-mute tabular-nums">
              <span className={clsx(
                'font-semibold',
                hitRate >= 0.55 ? 'text-pos' :
                  hitRate >= 0.45 ? 'text-warn' : 'text-neg',
              )}>
                {Math.round(hitRate * 100)}%
              </span>
              {' '}Trefferquote · n={n}
            </span>
          )}
          <span className="font-mono text-text-mute">
            {picks.length} Picks
          </span>
        </div>
      </div>
      <div className="grid grid-cols-12 gap-3 px-3 py-2 border-b border-canvas-line bg-canvas-2 text-[10px] uppercase tracking-wider text-text-quiet font-semibold">
        <span className="col-span-2">Liga</span>
        <span className="col-span-1">Datum</span>
        <span className="col-span-3">Spiel</span>
        <span className="col-span-2">Pick</span>
        <span className="col-span-1 text-right">Modell</span>
        <span className="col-span-1 text-right">Quote</span>
        <span className="col-span-1 text-right">Total</span>
        <span className="col-span-1 text-right">Result</span>
      </div>
      <div className="divide-y divide-canvas-line">
        {picks.map(p => <PickRow key={p.id} pick={p} />)}
      </div>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────
//  Page
// ────────────────────────────────────────────────────────────────────

type Tab = 'outcomes' | 'recommended'

export default function PerformancePage() {
  const [tab, setTab] = useState<Tab>('outcomes')
  const [days, setDays] = useState(30)

  const accuracyQuery = useQuery({
    queryKey: ['backtests', 'accuracy', days],
    queryFn: () => api.backtests.accuracy(days),
    refetchInterval: 60_000,
  })
  const recentQuery = useQuery({
    queryKey: ['backtests', 'recent', 200],
    queryFn: () => api.backtests.recent(200),
    refetchInterval: 60_000,
  })
  const recommendedQuery = useQuery({
    queryKey: ['backtests', 'recommended'],
    queryFn: () => api.backtests.recommended(undefined, false, 300),
    refetchInterval: 60_000,
  })
  const recommendedAccQuery = useQuery({
    queryKey: ['backtests', 'recommendedAccuracy'],
    queryFn: () => api.backtests.recommendedAccuracy(),
    refetchInterval: 60_000,
  })

  const acc = accuracyQuery.data
  const recAcc = recommendedAccQuery.data

  const outcomesBySport = useMemo(() => {
    const grouped: Record<SportKey, RecentOutcome[]> = {
      football: [], hockey: [], basketball: [], baseball: [],
    }
    for (const o of recentQuery.data ?? []) {
      const s = o.sport as SportKey
      if (grouped[s]) grouped[s].push(o)
    }
    return grouped
  }, [recentQuery.data])

  const picksBySport = useMemo(() => {
    const grouped: Record<SportKey, RecommendedPick[]> = {
      football: [], hockey: [], basketball: [], baseball: [],
    }
    for (const p of recommendedQuery.data ?? []) {
      const s = p.sport as SportKey
      if (grouped[s]) grouped[s].push(p)
    }
    return grouped
  }, [recommendedQuery.data])

  return (
    <div className="space-y-10">
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

      {/* Tab Switch */}
      <div className="flex gap-1 border-b border-canvas-line">
        {([
          { id: 'outcomes' as Tab, label: 'Alle Vorhersagen' },
          { id: 'recommended' as Tab, label: 'Wett-Empfehlungen ≥ 1.25' },
        ]).map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'px-4 py-2 text-[13px] transition-colors -mb-px border-b-2',
              tab === t.id
                ? 'border-accent text-text font-semibold'
                : 'border-transparent text-text-mute hover:text-text',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ──────────────────  TAB: OUTCOMES  ────────────────── */}
      {tab === 'outcomes' && (
        <>
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

          {acc && acc.n > 0 ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <KpiCard
                  label="Top-Pick-Trefferquote"
                  value={`${Math.round(acc.hit_rate * 100)}%`}
                  hint={`n = ${acc.n} ausgewertet`}
                />
                <KpiCard
                  label="Ø Total-Fehler"
                  value={acc.mae_total.toFixed(2)}
                  hint="Tor-/Punkt-/Run-Distanz"
                />
                <KpiCard
                  label="Bewertungsfenster"
                  value={String(acc.days)}
                  hint="Tage rolling"
                />
              </div>

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
            <EmptyState
              title="Noch keine ausgewerteten Spiele."
              description="Sobald Matches abgeschlossen sind, läuft der Backtest automatisch jede Nacht um 04:00."
            />
          )}

          {/* Pro Sport eine eigene Tabelle */}
          <div className="space-y-6">
            {SPORT_ORDER.map(sport => (
              <SportOutcomeTable
                key={sport}
                sport={sport}
                outcomes={outcomesBySport[sport]}
              />
            ))}
          </div>
        </>
      )}

      {/* ──────────────────  TAB: RECOMMENDED  ────────────────── */}
      {tab === 'recommended' && (
        <>
          <div className="card p-5">
            <p className="smallcaps text-[10px] text-text-quiet mb-2">
              Wett-Empfehlungen
            </p>
            <p className="text-[13px] text-text-dim leading-relaxed">
              Für jedes Match wählt das Modell die O/U-Linie mit dem
              besten Verhältnis aus Wahrscheinlichkeit (≥ 60 %) und
              Wettwert (faire Quote ≥ 1.25). Triviale Lock-Picks fliegen
              raus. Nur diese Picks zählen für die Wett-Trefferquote.
            </p>
          </div>

          {recAcc && recAcc.n > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KpiCard
                label="Wett-Trefferquote"
                value={`${Math.round(recAcc.hit_rate * 100)}%`}
                hint={`${recAcc.hits} von ${recAcc.n} bewertet`}
                emphasize
              />
              <KpiCard
                label="Bewertete Picks"
                value={String(recAcc.n)}
                hint="Full-Game-Märkte"
              />
              <KpiCard
                label="Sportarten"
                value={String(Object.keys(recAcc.by_sport).length)}
                hint="mit Picks"
              />
            </div>
          ) : (
            <EmptyState
              title="Noch keine bewerteten Empfehlungen."
              description="Sobald Spiele mit Empfehlung beendet sind, werden sie hier ausgewertet."
            />
          )}

          {/* Pro Sport eine Picks-Tabelle */}
          <div className="space-y-6">
            {SPORT_ORDER.map(sport => (
              <SportPicksTable
                key={sport}
                sport={sport}
                picks={picksBySport[sport]}
                hitRate={recAcc?.by_sport[sport]?.hit_rate}
                n={recAcc?.by_sport[sport]?.n}
              />
            ))}
          </div>
        </>
      )}

      <p className="text-[11px] text-text-quiet">
        Δ Total = absoluter Fehler zwischen erwarteter und tatsächlicher
        Gesamttoranzahl. Top-Pick = beste O/U-Linie pro Match.
        Wett-Empfehlungen filtern zusätzlich auf faire Quote ≥ 1.25 und
        werten nur Full-Game-Märkte aus.
      </p>
    </div>
  )
}

function KpiCard({ label, value, hint, emphasize }: {
  label: string
  value: string
  hint: string
  emphasize?: boolean
}) {
  return (
    <div className="card p-5">
      <p className="smallcaps text-[10px] text-text-quiet mb-2">
        {label}
      </p>
      <p className={clsx(
        'font-display font-medium leading-none tabular-nums',
        emphasize ? 'text-[44px] text-accent' : 'text-[44px] text-text',
      )}>
        {value}
      </p>
      <p className="text-text-mute text-[11px] mt-2">{hint}</p>
    </div>
  )
}

function EmptyState({ title, description }: {
  title: string
  description: string
}) {
  return (
    <div className="card p-8">
      <p className="font-display text-text-dim text-lg italic mb-2">
        {title}
      </p>
      <p className="text-text-mute text-[13px]">{description}</p>
    </div>
  )
}
