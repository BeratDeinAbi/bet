import { useQuery } from '@tanstack/react-query'
import { api, type RecentOutcome } from '../api/client'
import clsx from 'clsx'

const SPORT_LABEL: Record<string, string> = {
  football: 'Fußball',
  hockey: 'NHL',
  basketball: 'NBA',
  baseball: 'MLB',
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: 'short' })
}

function PrimaryHitTag({ hit, market, prob }: {
  hit: boolean | null
  market: string | null
  prob: number | null
}) {
  if (hit === null || !market) {
    return <span className="text-paper-quiet text-[10px]">—</span>
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
      <span className="font-mono text-[10px] text-paper-mute tabular-nums">
        {label} · {probPct}
      </span>
    </span>
  )
}

function OutcomeRow({ o }: { o: RecentOutcome }) {
  const totalErr = o.total_abs_error
  const errBucket =
    totalErr < 0.5 ? 'pos' : totalErr < 1.5 ? 'signal' : 'neg'
  const errColor = {
    pos: 'text-pos',
    signal: 'text-signal',
    neg: 'text-neg',
  }[errBucket]

  return (
    <a
      href={`/match/${o.match_id}`}
      className="block py-3 border-b border-ink-line hover:bg-ink-2/30 -mx-3 px-3 transition-colors"
    >
      <div className="flex items-baseline justify-between gap-2 mb-1.5">
        <span className="smallcaps text-[9px] text-paper-quiet">
          {o.league} · {SPORT_LABEL[o.sport] ?? o.sport}
        </span>
        <span className="font-mono text-[10px] text-paper-quiet tabular-nums">
          {formatDate(o.kickoff_time)}
        </span>
      </div>

      <div className="flex items-baseline justify-between gap-2 mb-2">
        <span className="text-[12px] text-paper-dim leading-tight truncate flex-1">
          {o.home_team}
        </span>
        <span className="font-display font-medium text-paper text-[15px] tabular-nums shrink-0">
          {Math.round(o.actual_home)}–{Math.round(o.actual_away)}
        </span>
        <span className="text-[12px] text-paper-dim leading-tight truncate flex-1 text-right">
          {o.away_team}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-paper-quiet">
          Erw.{' '}
          <span className="font-mono text-paper-mute tabular-nums">
            {o.expected_total.toFixed(1)}
          </span>{' '}
          · Fehler{' '}
          <span className={clsx('font-mono tabular-nums', errColor)}>
            {totalErr.toFixed(2)}
          </span>
        </span>
        <PrimaryHitTag
          hit={o.primary_hit}
          market={o.primary_market}
          prob={o.primary_prob}
        />
      </div>
    </a>
  )
}

export default function PastResultsSidebar() {
  const recentQuery = useQuery({
    queryKey: ['backtests', 'recent', 25],
    queryFn: () => api.backtests.recent(25),
    refetchInterval: 60_000,
  })
  const accuracyQuery = useQuery({
    queryKey: ['backtests', 'accuracy', 30],
    queryFn: () => api.backtests.accuracy(30),
    refetchInterval: 60_000,
  })

  const acc = accuracyQuery.data
  const outcomes = recentQuery.data ?? []

  return (
    <aside className="space-y-6">
      {/* Header */}
      <div className="rule pb-3">
        <p className="smallcaps text-[10px] text-paper-quiet mb-2">
          Backtest · 30 Tage
        </p>
        <h2 className="font-display text-paper text-[22px] leading-tight">
          Modell-<span className="italic">Trefferquote</span>.
        </h2>
      </div>

      {/* Accuracy-KPIs */}
      {acc && acc.n > 0 ? (
        <div className="space-y-4">
          <div>
            <div className="flex items-baseline justify-between mb-1">
              <span className="smallcaps text-[10px] text-paper-quiet">
                Top-Pick-Treffer
              </span>
              <span className="font-mono text-[10px] text-paper-quiet tabular-nums">
                n={acc.n}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display font-medium text-paper text-[36px] leading-none tabular-nums">
                {Math.round(acc.hit_rate * 100)}
              </span>
              <span className="font-mono text-paper-mute text-[14px]">%</span>
            </div>
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1">
              <span className="smallcaps text-[10px] text-paper-quiet">
                Ø Total-Fehler
              </span>
            </div>
            <span className="font-display text-paper text-[22px] tabular-nums">
              {acc.mae_total.toFixed(2)}
            </span>
          </div>

          {/* Pro Sport */}
          {Object.keys(acc.by_sport).length > 0 && (
            <div className="rule pt-3 space-y-2">
              {Object.entries(acc.by_sport).map(([sport, s]) => (
                <div key={sport} className="flex items-baseline justify-between text-[11px]">
                  <span className="smallcaps text-paper-mute">
                    {SPORT_LABEL[sport] ?? sport}
                  </span>
                  <span className="font-mono text-paper-dim tabular-nums">
                    {Math.round(s.hit_rate * 100)}% · n={s.n}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="text-[12px] text-paper-mute italic">
          Noch keine ausgewerteten Spiele. Sobald Matches abgeschlossen
          sind, läuft der Backtest automatisch jede Nacht um 04:00.
        </p>
      )}

      {/* Liste */}
      <div className="rule pt-4">
        <p className="smallcaps text-[10px] text-paper-quiet mb-3">
          Letzte Spiele
        </p>
        {recentQuery.isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map(i => (
              <div key={i} className="space-y-2 animate-pulse">
                <div className="h-2 bg-ink-2 rounded w-2/3" />
                <div className="h-3 bg-ink-2 rounded" />
                <div className="h-2 bg-ink-2 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}
        {!recentQuery.isLoading && outcomes.length === 0 && (
          <p className="text-[11px] text-paper-quiet italic">
            Keine ausgewerteten Spiele in der DB.
          </p>
        )}
        {outcomes.length > 0 && (
          <div className="-mx-3">
            {outcomes.map(o => (
              <OutcomeRow key={o.id} o={o} />
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
