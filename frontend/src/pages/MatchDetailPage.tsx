import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import ConfidenceBadge from '../components/ConfidenceBadge'
import ProbBar from '../components/ProbBar'
import type { Prediction } from '../types'

const SPORT_ICON: Record<string, string> = {
  football: '⚽',
  hockey: '🏒',
  basketball: '🏀',
  baseball: '⚾',
}

function num(v: unknown): number | undefined {
  return typeof v === 'number' ? v : undefined
}

function getEx(p: Prediction, key: string): number | undefined {
  return num(p.extra_markets?.[key])
}

function getExArr(p: Prediction, key: string): number[] | undefined {
  const v = p.extra_markets?.[key]
  return Array.isArray(v) ? v : undefined
}

export default function MatchDetailPage() {
  const { id } = useParams<{ id: string }>()
  const matchId = Number(id)

  const { data: pred, isLoading, isError } = useQuery({
    queryKey: ['prediction', matchId],
    queryFn: () => api.predictions.forMatch(matchId),
    enabled: !isNaN(matchId),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-text-mute">
        <Loader2 className="w-5 h-5 animate-spin" />
        Lade Match-Details...
      </div>
    )
  }

  if (isError || !pred) {
    return (
      <div className="flex flex-col items-center gap-3 py-16">
        <AlertCircle className="w-10 h-10 text-accent-red opacity-60" />
        <p className="text-text">Prognose nicht gefunden</p>
        <Link to="/" className="text-accent-blue text-sm hover:underline">Zurück zum Dashboard</Link>
      </div>
    )
  }

  const isFootball = pred.sport === 'football'
  const isHockey = pred.sport === 'hockey'
  const isBasketball = pred.sport === 'basketball'
  const isBaseball = pred.sport === 'baseball'

  // Sport-spezifische Anzeigewerte
  const totalLabel = isBasketball ? 'Gesamtpunkte'
    : isBaseball ? 'Gesamt-Runs'
    : 'Gesamttore'
  const teamMetricLabel = isBasketball ? 'Erwartete Punkte'
    : isBaseball ? 'Erwartete Runs'
    : 'Erwartete Tore'

  const totalValue = isBasketball ? (getEx(pred, 'expected_total_points') ?? pred.expected_total_goals)
    : isBaseball ? (getEx(pred, 'expected_total_runs') ?? pred.expected_total_goals)
    : pred.expected_total_goals

  const homeValue = isBasketball ? (getEx(pred, 'expected_home_points') ?? pred.expected_home_goals)
    : isBaseball ? (getEx(pred, 'expected_home_runs') ?? pred.expected_home_goals)
    : pred.expected_home_goals

  const awayValue = isBasketball ? (getEx(pred, 'expected_away_points') ?? pred.expected_away_goals)
    : isBaseball ? (getEx(pred, 'expected_away_runs') ?? pred.expected_away_goals)
    : pred.expected_away_goals

  // NBA / MLB O/U-Linien aus extra_markets ziehen
  const totalLines: number[] = (() => {
    const used = pred.extra_markets?.total_lines_used
    if (Array.isArray(used)) return used as number[]
    if (isBasketball) return [200.5, 210.5, 220.5, 230.5, 240.5]
    if (isBaseball) return [6.5, 7.5, 8.5, 9.5, 10.5]
    return []
  })()

  // MLB Inning-Daten
  const inningPct = isBaseball ? getExArr(pred, 'inning_distribution_pct') : undefined
  const inningRuns: number[] | undefined = isBaseball
    ? Array.from({ length: 9 }, (_, i) => getEx(pred, `expected_runs_inn_${i + 1}`) ?? 0)
    : undefined
  const inningOver05: number[] | undefined = isBaseball
    ? Array.from({ length: 9 }, (_, i) => getEx(pred, `prob_over_0_5_inn_${i + 1}`) ?? 0)
    : undefined

  // NBA-Quartal-Daten
  const quarterData = isBasketball
    ? (['q1', 'q2', 'q3', 'q4'] as const).map(q => ({
        label: `Q${q.slice(1)}`,
        exp: getEx(pred, `expected_points_${q}`) ?? 0,
        over55: getEx(pred, `prob_over_55_5_${q}`),
        over60: getEx(pred, `prob_over_60_5_${q}`),
      }))
    : []

  // F5-Daten für MLB
  const f5Exp = isBaseball ? getEx(pred, 'expected_runs_f5') : undefined

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="flex items-center gap-1.5 text-text-mute hover:text-text text-sm mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Zurück
      </Link>

      {/* Match Header */}
      <div className="card mb-5 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-text-mute text-xs">{pred.league} · {SPORT_ICON[pred.sport] ?? ''}</p>
            <p className="text-text-dim text-xs mt-0.5">
              {new Date(pred.kickoff_time).toLocaleString('de-DE')}
            </p>
          </div>
          <ConfidenceBadge label={pred.confidence_label} score={pred.confidence_score} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="font-display font-bold text-text text-xl">{pred.home_team}</p>
            <p className="text-text-mute text-sm mt-1">{teamMetricLabel}: <span className="text-text font-semibold">{homeValue.toFixed(isBasketball ? 1 : 2)}</span></p>
          </div>
          <div className="text-center px-6">
            <p className="font-display font-bold text-3xl text-accent-green">{totalValue.toFixed(isBasketball ? 1 : 2)}</p>
            <p className="text-text-quiet text-xs">{totalLabel}</p>
          </div>
          <div className="flex-1 text-right">
            <p className="font-display font-bold text-text text-xl">{pred.away_team}</p>
            <p className="text-text-mute text-sm mt-1">{teamMetricLabel}: <span className="text-text font-semibold">{awayValue.toFixed(isBasketball ? 1 : 2)}</span></p>
          </div>
        </div>
      </div>

      {/* Full Game O/U */}
      <div className="card mb-5 p-5">
        <h3 className="font-display font-semibold text-text mb-4">
          {isBasketball ? 'Total Punkte' : isBaseball ? 'Total Runs' : 'Gesamttore'} Over/Under
        </h3>
        <div className="space-y-2.5">
          {(isFootball || isHockey) && (
            <>
              <ProbBar label="Over 0.5" probability={pred.prob_over_0_5} color="#8eff71" />
              <ProbBar label="Over 1.5" probability={pred.prob_over_1_5} color="#60a5fa" />
              <ProbBar label="Over 2.5" probability={pred.prob_over_2_5} color="#a78bfa" />
              <ProbBar label="Over 3.5" probability={pred.prob_over_3_5} color="#fbbf24" />
              <div className="border-t border-canvas-line pt-2.5 space-y-2">
                <ProbBar label="Under 1.5" probability={pred.prob_under_1_5} color="#f87171" />
                <ProbBar label="Under 2.5" probability={pred.prob_under_2_5} color="#f87171" />
              </div>
            </>
          )}
          {(isBasketball || isBaseball) && totalLines.map((line, i) => {
            const key = String(line).replace('.', '_')
            const over = getEx(pred, `prob_over_${key}`) ?? 0
            const under = getEx(pred, `prob_under_${key}`) ?? 0
            const colors = ['#8eff71', '#60a5fa', '#a78bfa', '#fbbf24', '#f87171']
            return (
              <div key={line} className="grid grid-cols-2 gap-3">
                <ProbBar label={`Over ${line}`} probability={over} color={colors[i % colors.length]} />
                <ProbBar label={`Under ${line}`} probability={under} color="#94a3b8" />
              </div>
            )
          })}
        </div>
      </div>

      {/* Football H1/H2 */}
      {isFootball && pred.expected_goals_h1 !== undefined && (
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div className="card p-5">
            <h3 className="font-display font-semibold text-text mb-3">1. Halbzeit</h3>
            <p className="font-display font-bold text-accent-green text-2xl mb-3">{pred.expected_goals_h1!.toFixed(2)}</p>
            <div className="space-y-2">
              <ProbBar label="Over 0.5 H1" probability={pred.prob_over_0_5_h1 ?? 0} />
              <ProbBar label="Over 1.5 H1" probability={pred.prob_over_1_5_h1 ?? 0} color="#a78bfa" />
            </div>
          </div>
          <div className="card p-5">
            <h3 className="font-display font-semibold text-text mb-3">2. Halbzeit</h3>
            <p className="font-display font-bold text-accent-green text-2xl mb-3">{pred.expected_goals_h2!.toFixed(2)}</p>
            <div className="space-y-2">
              <ProbBar label="Over 0.5 H2" probability={pred.prob_over_0_5_h2 ?? 0} />
              <ProbBar label="Over 1.5 H2" probability={pred.prob_over_1_5_h2 ?? 0} color="#a78bfa" />
            </div>
          </div>
        </div>
      )}

      {/* NHL Periods */}
      {isHockey && pred.expected_goals_p1 !== undefined && (
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: 'Periode 1', exp: pred.expected_goals_p1, o05: pred.prob_over_0_5_p1, o15: pred.prob_over_1_5_p1 },
            { label: 'Periode 2', exp: pred.expected_goals_p2, o05: pred.prob_over_0_5_p2, o15: pred.prob_over_1_5_p2 },
            { label: 'Periode 3', exp: pred.expected_goals_p3, o05: pred.prob_over_0_5_p3, o15: pred.prob_over_1_5_p3 },
          ].map(({ label, exp, o05, o15 }) => (
            <div key={label} className="card p-5">
              <h3 className="font-display font-semibold text-text mb-2 text-sm">{label}</h3>
              <p className="font-display font-bold text-accent-green text-2xl mb-3">{(exp ?? 0).toFixed(2)}</p>
              <div className="space-y-2">
                <ProbBar label="O 0.5" probability={o05 ?? 0} />
                <ProbBar label="O 1.5" probability={o15 ?? 0} color="#a78bfa" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* NBA Quarters */}
      {isBasketball && quarterData.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          {quarterData.map(({ label, exp, over55, over60 }) => (
            <div key={label} className="card p-4">
              <h3 className="font-display font-semibold text-text mb-2 text-sm">{label}</h3>
              <p className="font-display font-bold text-accent-green text-xl mb-3">{exp.toFixed(1)}</p>
              <div className="space-y-2">
                {over55 !== undefined && <ProbBar label="O 55.5" probability={over55} />}
                {over60 !== undefined && <ProbBar label="O 60.5" probability={over60} color="#a78bfa" />}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MLB F5 */}
      {isBaseball && f5Exp !== undefined && (
        <div className="card mb-5 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-semibold text-text">Erste 5 Innings (F5)</h3>
            <p className="font-display font-bold text-accent-green text-2xl">{f5Exp.toFixed(2)}</p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <ProbBar label="O 3.5 F5" probability={getEx(pred, 'prob_over_3_5_f5') ?? 0} color="#60a5fa" />
            <ProbBar label="O 4.5 F5" probability={getEx(pred, 'prob_over_4_5_f5') ?? 0} color="#a78bfa" />
            <ProbBar label="O 5.5 F5" probability={getEx(pred, 'prob_over_5_5_f5') ?? 0} color="#f59e0b" />
          </div>
        </div>
      )}

      {/* MLB Inning-Verteilung */}
      {isBaseball && inningPct && inningRuns && inningOver05 && (
        <div className="card mb-5 p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-display font-semibold text-text">Inning-Verteilung</h3>
              <p className="text-text-mute text-xs mt-0.5">Wo werden die Runs erwartet?</p>
            </div>
            <p className="text-[10px] text-text-quiet uppercase tracking-widest">9 Innings</p>
          </div>

          {/* Heatmap-Bar */}
          <div className="mb-5">
            <div className="flex items-end gap-1 h-24">
              {inningPct.map((pct, i) => {
                const maxPct = Math.max(...inningPct)
                const heightPct = (pct / maxPct) * 100
                const isPeak = pct === maxPct
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1">
                    <span className="text-[9px] text-text-mute tabular-nums font-semibold">{pct.toFixed(1)}</span>
                    <div
                      className="w-full rounded-t transition-all"
                      style={{
                        height: `${heightPct}%`,
                        background: isPeak ? '#8eff71' : '#60a5fa',
                        opacity: isPeak ? 0.95 : 0.55,
                      }}
                    />
                  </div>
                )
              })}
            </div>
            <div className="flex gap-1 mt-2">
              {inningPct.map((_, i) => (
                <div key={i} className="flex-1 text-center text-[10px] text-text-mute font-semibold">
                  {i + 1}
                </div>
              ))}
            </div>
          </div>

          {/* Tabellen-Detail */}
          <div className="space-y-1.5 border-t border-canvas-line pt-4">
            <div className="grid grid-cols-12 gap-2 text-[10px] text-text-quiet uppercase tracking-widest font-semibold pb-1">
              <span className="col-span-2">Inning</span>
              <span className="col-span-3 text-right">Runs Erw.</span>
              <span className="col-span-3 text-right">% Anteil</span>
              <span className="col-span-4 text-right">P(≥1 Run)</span>
            </div>
            {inningRuns.map((runs, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 text-xs items-center">
                <span className="col-span-2 text-text-dim font-semibold tabular-nums">#{i + 1}</span>
                <span className="col-span-3 text-right text-text tabular-nums">{runs.toFixed(2)}</span>
                <span className="col-span-3 text-right text-text-mute tabular-nums">{inningPct[i].toFixed(1)}%</span>
                <span className="col-span-4 text-right">
                  <span className="inline-block w-16">
                    <ProbBar label="" probability={inningOver05[i]} color="#8eff71" />
                  </span>
                </span>
              </div>
            ))}
          </div>

          <p className="text-text-quiet text-[11px] leading-relaxed mt-4 border-t border-canvas-line pt-3">
            Inning 1 hat höhere Scoring-Erwartung (Top-of-Order vs. Starter), Innings 7–8 wegen Bullpen-Wechsel ebenfalls erhöht.
            Empirisch über 5 MLB-Saisons gemittelt.
          </p>
        </div>
      )}

      {/* Park-Faktor / Pitcher (MLB) */}
      {isBaseball && (getEx(pred, 'park_factor') !== undefined || getEx(pred, 'pitcher_factor_home') !== undefined) && (
        <div className="card mb-5 p-5">
          <h3 className="font-display font-semibold text-text mb-3">MLB-Faktoren</h3>
          <div className="grid grid-cols-3 gap-4">
            {getEx(pred, 'park_factor') !== undefined && (
              <div>
                <p className="text-text-mute text-xs mb-1">Park-Faktor</p>
                <p className="font-display font-bold text-text text-lg tabular-nums">
                  ×{getEx(pred, 'park_factor')!.toFixed(2)}
                </p>
              </div>
            )}
            {getEx(pred, 'pitcher_factor_home') !== undefined && (
              <div>
                <p className="text-text-mute text-xs mb-1">Pitcher Heim</p>
                <p className="font-display font-bold text-text text-lg tabular-nums">
                  ×{getEx(pred, 'pitcher_factor_home')!.toFixed(2)}
                </p>
              </div>
            )}
            {getEx(pred, 'pitcher_factor_away') !== undefined && (
              <div>
                <p className="text-text-mute text-xs mb-1">Pitcher Auswärts</p>
                <p className="font-display font-bold text-text text-lg tabular-nums">
                  ×{getEx(pred, 'pitcher_factor_away')!.toFixed(2)}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* B2B (NHL) */}
      {isHockey && (pred.extra_markets?.b2b_home || pred.extra_markets?.b2b_away) && (
        <div className="card mb-5 p-5">
          <h3 className="font-display font-semibold text-text mb-3">Back-to-Back-Status</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-text-mute text-xs mb-1">{pred.home_team}</p>
              <p className={`font-display font-bold text-lg ${pred.extra_markets?.b2b_home ? 'text-warn' : 'text-text-mute'}`}>
                {pred.extra_markets?.b2b_home ? 'Müde (B2B)' : 'Ausgeruht'}
              </p>
            </div>
            <div>
              <p className="text-text-mute text-xs mb-1">{pred.away_team}</p>
              <p className={`font-display font-bold text-lg ${pred.extra_markets?.b2b_away ? 'text-warn' : 'text-text-mute'}`}>
                {pred.extra_markets?.b2b_away ? 'Müde (B2B)' : 'Ausgeruht'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Model Info */}
      <div className="card mb-5 p-5">
        <h3 className="font-display font-semibold text-text mb-4">Modell-Metriken</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-text-mute text-xs mb-1">Konfidenz</p>
            <p className="font-display font-bold text-text text-xl">{(pred.confidence_score * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-text-mute text-xs mb-1">Modell-Übereinstimmung</p>
            <p className="font-display font-bold text-text text-xl">{(pred.model_agreement_score * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-text-mute text-xs mb-1">Prognose-Stabilität</p>
            <p className="font-display font-bold text-text text-xl">{(pred.prediction_stability_score * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      {/* Explanation */}
      {pred.explanation && (
        <div className="card p-5">
          <h3 className="font-display font-semibold text-text mb-2">Prognose-Erklärung</h3>
          <p className="text-text-dim text-sm leading-relaxed">{pred.explanation}</p>
          <p className="text-text-quiet text-xs mt-3">
            {isFootball && 'Ensemble: Poisson MLE + Dixon-Coles + Elo + Rolling Form'}
            {isHockey && 'Ensemble: Poisson MLE + Elo + Rolling Form + B2B-Adjustment'}
            {isBasketball && 'Ensemble: Normal-Approximation + Pace-Adjustment + Elo'}
            {isBaseball && 'Ensemble: Poisson MLE + Park-Faktoren + Pitcher-ERA + Inning-Verteilung'}
          </p>
        </div>
      )}
    </div>
  )
}
