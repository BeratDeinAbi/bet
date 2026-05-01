import { Link } from 'react-router-dom'
import { Clock, ChevronRight } from 'lucide-react'
import type { Prediction } from '../types'
import ConfidenceBadge from './ConfidenceBadge'
import ProbBar from './ProbBar'

interface Props {
  prediction: Prediction
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

const SPORT_EMOJI: Record<string, string> = {
  football: '⚽',
  hockey: '🏒',
}

const LEAGUE_COLORS: Record<string, string> = {
  BL1: '#e4002b',
  PL: '#3d195b',
  PD: '#ee8707',
  SSL: '#E30A17',
  NHL: '#003087',
}

export default function MatchCard({ prediction: p }: Props) {
  const isFootball = p.sport === 'football'
  const leagueColor = LEAGUE_COLORS[p.league] || '#444'

  return (
    <div className="card hover:border-gray-600 transition-all duration-200 group">
      {/* Header Row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">{SPORT_EMOJI[p.sport]}</span>
          <span
            className="text-xs font-bold px-2 py-0.5 rounded-md text-white"
            style={{ background: leagueColor }}
          >
            {p.league}
          </span>
          <div className="flex items-center gap-1 text-gray-500 text-xs">
            <Clock className="w-3 h-3" />
            <span>{formatTime(p.kickoff_time)}</span>
          </div>
        </div>
        <ConfidenceBadge label={p.confidence_label} score={p.confidence_score} />
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex-1">
          <p className="font-display font-semibold text-white text-sm leading-tight">{p.home_team}</p>
          <p className="text-gray-500 text-xs mt-0.5">Heim</p>
        </div>
        <div className="text-center px-3">
          <p className="font-display font-bold text-xl text-white">
            {p.expected_home_goals.toFixed(1)}
            <span className="text-gray-500 mx-1 text-base">-</span>
            {p.expected_away_goals.toFixed(1)}
          </p>
          <p className="text-gray-600 text-xs">erw. Tore</p>
        </div>
        <div className="flex-1 text-right">
          <p className="font-display font-semibold text-white text-sm leading-tight">{p.away_team}</p>
          <p className="text-gray-500 text-xs mt-0.5">Auswärts</p>
        </div>
      </div>

      {/* Total Goals */}
      <div className="bg-surface-low rounded-lg p-3 mb-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-400 font-medium">Gesamt erwartet</span>
          <span className="font-display font-bold text-accent-green text-lg">
            {p.expected_total_goals.toFixed(2)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <ProbBar label="Over 1.5" probability={p.prob_over_1_5} />
          <ProbBar label="Over 2.5" probability={p.prob_over_2_5} color="#8eff71" />
          <ProbBar label="Over 3.5" probability={p.prob_over_3_5} color="#fbbf24" />
          <ProbBar label="Under 2.5" probability={p.prob_under_2_5} color="#f87171" />
        </div>
      </div>

      {/* Segments */}
      {isFootball && p.expected_goals_h1 !== undefined && (
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="bg-surface-low rounded-lg p-2.5">
            <p className="text-gray-500 text-xs mb-1">1. Halbzeit</p>
            <p className="font-display font-bold text-white text-base">{p.expected_goals_h1!.toFixed(2)}</p>
            <div className="mt-1.5 space-y-1">
              <ProbBar label="O 0.5" probability={p.prob_over_0_5_h1 ?? 0} color="#60a5fa" />
              <ProbBar label="O 1.5" probability={p.prob_over_1_5_h1 ?? 0} color="#a78bfa" />
            </div>
          </div>
          <div className="bg-surface-low rounded-lg p-2.5">
            <p className="text-gray-500 text-xs mb-1">2. Halbzeit</p>
            <p className="font-display font-bold text-white text-base">{p.expected_goals_h2!.toFixed(2)}</p>
            <div className="mt-1.5 space-y-1">
              <ProbBar label="O 0.5" probability={p.prob_over_0_5_h2 ?? 0} color="#60a5fa" />
              <ProbBar label="O 1.5" probability={p.prob_over_1_5_h2 ?? 0} color="#a78bfa" />
            </div>
          </div>
        </div>
      )}

      {!isFootball && p.expected_goals_p1 !== undefined && (
        <div className="grid grid-cols-3 gap-2 mb-3">
          {[
            { label: 'P1', exp: p.expected_goals_p1, o05: p.prob_over_0_5_p1, o15: p.prob_over_1_5_p1 },
            { label: 'P2', exp: p.expected_goals_p2, o05: p.prob_over_0_5_p2, o15: p.prob_over_1_5_p2 },
            { label: 'P3', exp: p.expected_goals_p3, o05: p.prob_over_0_5_p3, o15: p.prob_over_1_5_p3 },
          ].map(({ label, exp, o05, o15 }) => (
            <div key={label} className="bg-surface-low rounded-lg p-2">
              <p className="text-gray-500 text-xs mb-1">{label}</p>
              <p className="font-display font-bold text-white">{(exp ?? 0).toFixed(2)}</p>
              <div className="mt-1 space-y-1">
                <ProbBar label="O 0.5" probability={o05 ?? 0} color="#60a5fa" />
                <ProbBar label="O 1.5" probability={o15 ?? 0} color="#a78bfa" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Explanation */}
      {p.explanation && (
        <p className="text-gray-500 text-xs leading-relaxed mb-3 border-t border-surface-border pt-3">
          {p.explanation}
        </p>
      )}

      {/* Link */}
      <Link
        to={`/match/${p.match_id}`}
        className="flex items-center justify-end gap-1 text-xs text-gray-500 hover:text-accent-blue transition-colors group-hover:text-accent-blue"
      >
        Details ansehen
        <ChevronRight className="w-3 h-3" />
      </Link>
    </div>
  )
}
