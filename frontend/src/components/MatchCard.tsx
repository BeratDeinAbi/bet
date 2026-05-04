import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import type { Prediction } from '../types'
import ConfidenceBadge from './ConfidenceBadge'
import ProbBar from './ProbBar'

interface Props { prediction: Prediction }

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

const LEAGUE_COLORS: Record<string, string> = {
  BL1: '#e4002b',
  BL2: '#1f8a3a',
  PL:  '#7B2D8B',
  PD:  '#ee8707',
  SSL: '#E30A17',
  NHL: '#1560bd',
  NBA: '#c8102e',
  MLB: '#01696f',
}

function getNbaProb(p: Prediction, key: string): number | undefined {
  const v = p.extra_markets?.[key]
  return typeof v === 'number' ? v : undefined
}

function bestQuarterOvers(p: Prediction, quarter: 'q1' | 'q2' | 'q3' | 'q4') {
  const re = new RegExp(`^prob_over_(\\d+)_5_${quarter}$`)
  const overs: { line: number; prob: number }[] = []
  for (const [k, v] of Object.entries(p.extra_markets ?? {})) {
    if (typeof v !== 'number') continue
    const m = k.match(re)
    if (m && v >= 0.80) overs.push({ line: parseFloat(`${m[1]}.5`), prob: v })
  }
  return overs.sort((a, b) => b.line - a.line).slice(0, 2)
}

export default function MatchCard({ prediction: p }: Props) {
  const isFootball   = p.sport === 'football'
  const isBasketball = p.sport === 'basketball'
  const isBaseball   = p.sport === 'baseball'
  const isHockey     = p.sport === 'hockey'
  const lc = LEAGUE_COLORS[p.league] ?? '#555'

  return (
    <div
      className="rounded-xl border border-surface-border bg-surface-mid overflow-hidden hover:border-gray-700 transition-colors duration-150 flex flex-col"
      style={{ borderTop: `2px solid ${lc}` }}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 pt-3.5 pb-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold tracking-wider" style={{ color: lc }}>
            {p.league}
          </span>
          <span className="text-gray-700 text-xs">·</span>
          <span className="text-gray-500 text-[11px] tabular-nums">{formatTime(p.kickoff_time)}</span>
        </div>
        <ConfidenceBadge label={p.confidence_label} score={p.confidence_score} />
      </div>

      {/* ── Teams ── */}
      <div className="flex items-center gap-2 px-4 py-3.5">
        <p className="flex-1 font-display font-semibold text-white text-sm leading-snug">{p.home_team}</p>
        <div className="shrink-0 text-center min-w-[72px]">
          <p className="font-display font-bold text-white tabular-nums" style={{ fontSize: '1.1rem', letterSpacing: '-0.02em' }}>
            {isBasketball
              ? `${Math.round(p.expected_home_goals)}–${Math.round(p.expected_away_goals)}`
              : `${p.expected_home_goals.toFixed(1)}–${p.expected_away_goals.toFixed(1)}`}
          </p>
        </div>
        <p className="flex-1 font-display font-semibold text-white text-sm leading-snug text-right">{p.away_team}</p>
      </div>

      {/* ── Totals ── */}
      <div className="px-4 pb-4 border-t border-surface-border/60 pt-3.5">
        <div className="flex justify-between items-center mb-3">
          <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">
            {isBasketball ? 'Total Pts' : isBaseball ? 'Total Runs' : 'Total Goals'}
          </span>
          <span className="font-display font-bold tabular-nums text-[15px]" style={{ color: lc }}>
            {p.expected_total_goals.toFixed(isBaseball ? 2 : 1)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          {isBasketball ? (<>
            <ProbBar label="O 210.5" probability={getNbaProb(p, 'prob_over_210_5') ?? 0} />
            <ProbBar label="O 220.5" probability={getNbaProb(p, 'prob_over_220_5') ?? 0} color="#8eff71" />
            <ProbBar label="O 230.5" probability={getNbaProb(p, 'prob_over_230_5') ?? 0} color="#fbbf24" />
            <ProbBar label="U 220.5" probability={getNbaProb(p, 'prob_under_220_5') ?? 0} color="#f87171" />
          </>) : isBaseball ? (<>
            <ProbBar label="O 7.5"  probability={getNbaProb(p, 'prob_over_7_5')  ?? 0} />
            <ProbBar label="O 8.5"  probability={getNbaProb(p, 'prob_over_8_5')  ?? 0} color="#8eff71" />
            <ProbBar label="O 9.5"  probability={getNbaProb(p, 'prob_over_9_5')  ?? 0} color="#fbbf24" />
            <ProbBar label="U 8.5"  probability={getNbaProb(p, 'prob_under_8_5') ?? 0} color="#f87171" />
          </>) : (<>
            <ProbBar label="O 1.5"  probability={p.prob_over_1_5} />
            <ProbBar label="O 2.5"  probability={p.prob_over_2_5}  color="#8eff71" />
            <ProbBar label="O 3.5"  probability={p.prob_over_3_5}  color="#fbbf24" />
            <ProbBar label="U 2.5"  probability={p.prob_under_2_5} color="#f87171" />
          </>)}
        </div>
      </div>

      {/* ── Football halves ── */}
      {isFootball && p.expected_goals_h1 !== undefined && (
        <div className="px-4 pb-4 border-t border-surface-border/60 pt-3.5">
          <div className="grid grid-cols-2 gap-4">
            {[
              { lbl: '1. HZ', exp: p.expected_goals_h1!, o05: p.prob_over_0_5_h1, o15: p.prob_over_1_5_h1 },
              { lbl: '2. HZ', exp: p.expected_goals_h2!, o05: p.prob_over_0_5_h2, o15: p.prob_over_1_5_h2 },
            ].map(({ lbl, exp, o05, o15 }) => (
              <div key={lbl}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">{lbl}</span>
                  <span className="text-white font-display font-bold text-sm tabular-nums">{exp.toFixed(2)}</span>
                </div>
                <div className="space-y-1.5">
                  <ProbBar label="O 0.5" probability={o05 ?? 0} color="#60a5fa" />
                  <ProbBar label="O 1.5" probability={o15 ?? 0} color="#a78bfa" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Hockey periods ── */}
      {isHockey && p.expected_goals_p1 !== undefined && (
        <div className="px-4 pb-4 border-t border-surface-border/60 pt-3.5">
          <div className="grid grid-cols-3 gap-3">
            {[
              { lbl: 'P1', exp: p.expected_goals_p1, o05: p.prob_over_0_5_p1, o15: p.prob_over_1_5_p1 },
              { lbl: 'P2', exp: p.expected_goals_p2, o05: p.prob_over_0_5_p2, o15: p.prob_over_1_5_p2 },
              { lbl: 'P3', exp: p.expected_goals_p3, o05: p.prob_over_0_5_p3, o15: p.prob_over_1_5_p3 },
            ].map(({ lbl, exp, o05, o15 }) => (
              <div key={lbl}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">{lbl}</span>
                  <span className="text-white font-display font-bold text-sm tabular-nums">{(exp ?? 0).toFixed(2)}</span>
                </div>
                <div className="space-y-1.5">
                  <ProbBar label="O 0.5" probability={o05 ?? 0} color="#60a5fa" />
                  <ProbBar label="O 1.5" probability={o15 ?? 0} color="#a78bfa" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Baseball F5 ── */}
      {isBaseball && (
        <div className="px-4 pb-4 border-t border-surface-border/60 pt-3.5">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">F5 Innings</span>
            <span className="text-white font-display font-bold text-sm tabular-nums">
              {(getNbaProb(p, 'expected_runs_f5') ?? 0).toFixed(2)}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5">
            <ProbBar label="O 3.5" probability={getNbaProb(p, 'prob_over_3_5_f5') ?? 0} color="#60a5fa" />
            <ProbBar label="O 4.5" probability={getNbaProb(p, 'prob_over_4_5_f5') ?? 0} color="#a78bfa" />
            <ProbBar label="O 5.5" probability={getNbaProb(p, 'prob_over_5_5_f5') ?? 0} color="#f59e0b" />
          </div>
        </div>
      )}

      {/* ── NBA quarters ── */}
      {isBasketball && (
        <div className="px-4 pb-4 border-t border-surface-border/60 pt-3.5">
          <div className="grid grid-cols-2 gap-4">
            {(['q1', 'q2', 'q3', 'q4'] as const).map(q => {
              const exp  = getNbaProb(p, `expected_points_${q}`) ?? 0
              const top2 = bestQuarterOvers(p, q)
              return (
                <div key={q}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold">Q{q.slice(1)}</span>
                    <span className="text-white font-display font-bold text-sm tabular-nums">{exp.toFixed(1)}</span>
                  </div>
                  <div className="space-y-1.5">
                    {top2.length > 0
                      ? top2.map(({ line, prob }, i) => (
                          <ProbBar key={line} label={`O ${line}`} probability={prob} color={i === 0 ? '#8eff71' : '#60a5fa'} />
                        ))
                      : <p className="text-gray-700 text-[10px]">kein O ≥ 80%</p>
                    }
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Footer ── */}
      <div className="mt-auto px-4 pt-3 pb-3.5 border-t border-surface-border/60">
        {p.explanation && (
          <p className="text-gray-600 text-[11px] leading-relaxed mb-2.5">
            {p.explanation.length > 110 ? p.explanation.slice(0, 107) + '…' : p.explanation}
          </p>
        )}
        <Link
          to={`/match/${p.match_id}`}
          className="flex items-center gap-0.5 text-[11px] text-gray-600 hover:text-gray-300 transition-colors"
        >
          Details <ChevronRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  )
}
