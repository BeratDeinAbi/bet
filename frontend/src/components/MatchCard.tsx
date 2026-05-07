import { Link } from 'react-router-dom'
import type { Prediction } from '../types'
import ConfidenceBadge from './ConfidenceBadge'
import ProbBar from './ProbBar'

interface Props {
  prediction: Prediction
}

/**
 * MatchCard im Editorial-Stil.
 *
 * Bewusste Designentscheidungen, die das Generische rausnehmen:
 *  - Keine umrandete Karte mit gerundeten Ecken — die Trennung zwischen
 *    Spielen passiert über typografische Hierarchie + horizontale Rules.
 *    So entsteht der Look einer redaktionell gesetzten Spielzusammen-
 *    fassung statt eines Tailwind-Tiles.
 *  - Liga-Tag links als kurze Vertikalmarker-Linie + smallcaps-Text.
 *  - Team-Namen groß im Serif (Fraunces), das ergibt sofort Charakter.
 *  - Erwarteter Score mittig in der Hauptzeile, Mono-Font, fest gespacet.
 *  - Sektionsblöcke nicht in eigenen Karten — nur durch sehr feine
 *    Horizontallinien getrennt, mit Smallcaps-Eyebrow.
 */

const LEAGUE_COLORS: Record<string, string> = {
  BL1: '#2d7a3e',  // Bundesliga — accent green
  BL2: '#5b8754',  // 2. BL — heller grün
  PL:  '#6b21a8',  // Premier League — purple
  PD:  '#b45309',  // La Liga — burnt orange
  SSL: '#c2410c',  // Süper Lig — red
  NHL: '#1e40af',  // NHL — deep blue
  NBA: '#b91c1c',  // NBA — basketball red
  MLB: '#0f766e',  // MLB — teal
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getExtra(p: Prediction, key: string): number | undefined {
  const v = p.extra_markets?.[key]
  return typeof v === 'number' ? v : undefined
}

/** Top 2 NBA-Quarter-Overs ≥ 80 %, sortiert nach Linie absteigend. */
function bestQuarterOvers(p: Prediction, quarter: 'q1' | 'q2' | 'q3' | 'q4') {
  const re = new RegExp(`^prob_over_(\\d+)_5_${quarter}$`)
  const overs: { line: number; prob: number }[] = []
  for (const [k, v] of Object.entries(p.extra_markets ?? {})) {
    if (typeof v !== 'number') continue
    const m = k.match(re)
    if (m && v >= 0.8) {
      overs.push({ line: parseFloat(`${m[1]}.5`), prob: v })
    }
  }
  return overs.sort((a, b) => b.line - a.line).slice(0, 2)
}

export default function MatchCard({ prediction: p }: Props) {
  const isFootball = p.sport === 'football'
  const isBasketball = p.sport === 'basketball'
  const isBaseball = p.sport === 'baseball'
  const isHockey = p.sport === 'hockey'
  const lc = LEAGUE_COLORS[p.league] ?? '#2d7a3e'

  const totalLabel = isBasketball
    ? 'Erwartete Punkte'
    : isBaseball
      ? 'Erwartete Runs'
      : 'Erwartete Tore'

  const score = isBasketball
    ? `${Math.round(p.expected_home_goals)}–${Math.round(p.expected_away_goals)}`
    : `${p.expected_home_goals.toFixed(1)}–${p.expected_away_goals.toFixed(1)}`

  return (
    <article className="card p-5 group hover:border-canvas-border transition-colors">
      {/* ────────────────────────────────────────────────
          Eyebrow: Liga-Marker + Anstoßzeit + Confidence
          ──────────────────────────────────────────────── */}
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span
            className="block w-3 h-px"
            style={{ background: lc }}
            aria-hidden
          />
          <span
            className="smallcaps text-[10px] font-medium"
            style={{ color: lc }}
          >
            {p.league}
          </span>
          <span className="text-paper-quiet text-[11px]">·</span>
          <time className="font-mono text-[11px] text-paper-mute tabular-nums">
            {formatTime(p.kickoff_time)}
          </time>
        </div>
        <ConfidenceBadge label={p.confidence_label} score={p.confidence_score} />
      </header>

      {/* ────────────────────────────────────────────────
          Match-Headline: Heim — Score — Auswärts
          ──────────────────────────────────────────────── */}
      <Link
        to={`/match/${p.match_id}`}
        className="block group/link"
      >
        <h3 className="font-display text-paper text-[22px] sm:text-[24px] leading-[1.15] tracking-tightish font-medium group-hover/link:text-paper transition-colors">
          {p.home_team}
          <span className="text-paper-quiet font-normal mx-2">vs</span>
          {p.away_team}
        </h3>
      </Link>

      <div className="flex items-baseline gap-3 mt-2.5">
        <span className="smallcaps text-[10px] text-paper-quiet">
          {totalLabel}
        </span>
        <span className="font-mono text-[14px] text-paper-dim tabular-nums">
          {score}
        </span>
        <span className="text-paper-quiet text-[11px]">→</span>
        <span className="font-display font-medium text-paper text-[18px] tabular-nums tracking-tightish">
          {p.expected_total_goals.toFixed(isBaseball ? 2 : 1)}
        </span>
      </div>

      {/* ────────────────────────────────────────────────
          Markt-Block: Total Linien
          ──────────────────────────────────────────────── */}
      <Section title={isBasketball ? 'Total · Punkte' : isBaseball ? 'Total · Runs' : 'Total · Tore'}>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          {isBasketball ? (
            <>
              <ProbBar label="Over 210.5" probability={getExtra(p, 'prob_over_210_5') ?? 0} />
              <ProbBar label="Over 220.5" probability={getExtra(p, 'prob_over_220_5') ?? 0} />
              <ProbBar label="Over 230.5" probability={getExtra(p, 'prob_over_230_5') ?? 0} color="#3fa356" />
              <ProbBar label="Under 220.5" probability={getExtra(p, 'prob_under_220_5') ?? 0} color="#0369a1" />
            </>
          ) : isBaseball ? (
            <>
              <ProbBar label="Over 7.5" probability={getExtra(p, 'prob_over_7_5') ?? 0} />
              <ProbBar label="Over 8.5" probability={getExtra(p, 'prob_over_8_5') ?? 0} />
              <ProbBar label="Over 9.5" probability={getExtra(p, 'prob_over_9_5') ?? 0} color="#3fa356" />
              <ProbBar label="Under 8.5" probability={getExtra(p, 'prob_under_8_5') ?? 0} color="#0369a1" />
            </>
          ) : (
            <>
              <ProbBar label="Over 1.5" probability={p.prob_over_1_5} />
              <ProbBar label="Over 2.5" probability={p.prob_over_2_5} />
              <ProbBar label="Over 3.5" probability={p.prob_over_3_5} color="#3fa356" />
              <ProbBar label="Under 2.5" probability={p.prob_under_2_5} color="#0369a1" />
            </>
          )}
        </div>
      </Section>

      {/* ────────────────────────────────────────────────
          Football: Halbzeiten
          ──────────────────────────────────────────────── */}
      {isFootball && p.expected_goals_h1 !== undefined && (
        <Section title="Halbzeiten">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <SegmentBlock
              label="1. Halbzeit"
              value={p.expected_goals_h1!.toFixed(2)}
              bars={[
                { label: 'Over 0.5', prob: p.prob_over_0_5_h1 ?? 0 },
                { label: 'Over 1.5', prob: p.prob_over_1_5_h1 ?? 0, color: '#0369a1' },
              ]}
            />
            <SegmentBlock
              label="2. Halbzeit"
              value={p.expected_goals_h2!.toFixed(2)}
              bars={[
                { label: 'Over 0.5', prob: p.prob_over_0_5_h2 ?? 0 },
                { label: 'Over 1.5', prob: p.prob_over_1_5_h2 ?? 0, color: '#0369a1' },
              ]}
            />
          </div>
        </Section>
      )}

      {/* ────────────────────────────────────────────────
          NHL: Drittel
          ──────────────────────────────────────────────── */}
      {isHockey && p.expected_goals_p1 !== undefined && (
        <Section title="Drittel">
          <div className="grid grid-cols-3 gap-x-5 gap-y-2">
            {[
              { lbl: 'P1', exp: p.expected_goals_p1, o05: p.prob_over_0_5_p1, o15: p.prob_over_1_5_p1 },
              { lbl: 'P2', exp: p.expected_goals_p2, o05: p.prob_over_0_5_p2, o15: p.prob_over_1_5_p2 },
              { lbl: 'P3', exp: p.expected_goals_p3, o05: p.prob_over_0_5_p3, o15: p.prob_over_1_5_p3 },
            ].map(({ lbl, exp, o05, o15 }) => (
              <SegmentBlock
                key={lbl}
                label={lbl}
                value={(exp ?? 0).toFixed(2)}
                bars={[
                  { label: 'Over 0.5', prob: o05 ?? 0 },
                  { label: 'Over 1.5', prob: o15 ?? 0, color: '#0369a1' },
                ]}
              />
            ))}
          </div>
        </Section>
      )}

      {/* ────────────────────────────────────────────────
          MLB: F5 Innings
          ──────────────────────────────────────────────── */}
      {isBaseball && (
        <Section title="F5 · Erste 5 Innings">
          <div className="grid grid-cols-[auto_1fr_1fr_1fr] items-center gap-x-5">
            <div>
              <span className="font-display font-medium text-paper text-[18px] tabular-nums tracking-tightish">
                {(getExtra(p, 'expected_runs_f5') ?? 0).toFixed(2)}
              </span>
              <p className="smallcaps text-[10px] text-paper-quiet mt-0.5">
                erw. Runs
              </p>
            </div>
            <ProbBar label="Over 3.5" probability={getExtra(p, 'prob_over_3_5_f5') ?? 0} />
            <ProbBar label="Over 4.5" probability={getExtra(p, 'prob_over_4_5_f5') ?? 0} />
            <ProbBar label="Over 5.5" probability={getExtra(p, 'prob_over_5_5_f5') ?? 0} color="#0369a1" />
          </div>
        </Section>
      )}

      {/* ────────────────────────────────────────────────
          NBA: Quarter — Top 2 Overs ≥ 80 %
          ──────────────────────────────────────────────── */}
      {isBasketball && (
        <Section title="Viertel · Top Overs ≥ 80 %">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {(['q1', 'q2', 'q3', 'q4'] as const).map(q => {
              const exp = getExtra(p, `expected_points_${q}`) ?? 0
              const top2 = bestQuarterOvers(p, q)
              return (
                <div key={q}>
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="smallcaps text-[10px] text-paper-quiet">
                      Q{q.slice(1)}
                    </span>
                    <span className="font-display font-medium text-paper text-[14px] tabular-nums">
                      {exp.toFixed(1)}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {top2.length > 0 ? (
                      top2.map(({ line, prob }, i) => (
                        <ProbBar
                          key={line}
                          label={`Over ${line}`}
                          probability={prob}
                          color={i === 0 ? '#2d7a3e' : '#0369a1'}
                        />
                      ))
                    ) : (
                      <p className="text-paper-quiet text-[10px] italic font-display">
                        keine Linie ≥ 80 %
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {/* ────────────────────────────────────────────────
          Footer: Erklärung + Detail-Link
          ──────────────────────────────────────────────── */}
      <footer className="mt-5 pt-4 rule">
        {p.explanation && (
          <p className="font-display italic text-paper-mute text-[13px] leading-relaxed mb-3">
            {p.explanation.length > 140
              ? p.explanation.slice(0, 137) + '…'
              : p.explanation}
          </p>
        )}
        <Link
          to={`/match/${p.match_id}`}
          className="text-[12px] text-text-mute hover:text-accent transition-colors underline-offset-4 hover:underline decoration-accent/60"
        >
          Detail-Analyse →
        </Link>
      </footer>
    </article>
  )
}

/* ────────────────────────────────────────────────────────
   Sektion mit Smallcaps-Eyebrow und feiner Trennlinie.
   ──────────────────────────────────────────────────────── */
function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-5 pt-4 rule">
      <p className="smallcaps text-[10px] text-paper-quiet mb-3">{title}</p>
      {children}
    </section>
  )
}

/* ────────────────────────────────────────────────────────
   Segment-Block (HZ, P1/2/3) — Label + Wert obendrüber,
   ProbBars darunter.
   ──────────────────────────────────────────────────────── */
function SegmentBlock({
  label,
  value,
  bars,
}: {
  label: string
  value: string
  bars: { label: string; prob: number; color?: string }[]
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2.5">
        <span className="smallcaps text-[10px] text-paper-quiet">{label}</span>
        <span className="font-display font-medium text-paper text-[14px] tabular-nums">
          {value}
        </span>
      </div>
      <div className="space-y-2">
        {bars.map(b => (
          <ProbBar
            key={b.label}
            label={b.label}
            probability={b.prob}
            color={b.color}
          />
        ))}
      </div>
    </div>
  )
}
