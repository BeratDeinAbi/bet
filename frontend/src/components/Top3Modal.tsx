import { useQuery } from '@tanstack/react-query'
import { X, Trophy, TrendingUp, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import type { Top3Pick } from '../types'
import ConfidenceBadge from './ConfidenceBadge'

interface Props {
  onClose: () => void
}

function PickCard({ pick, rank }: { pick: Top3Pick; rank: number }) {
  const rankColors = ['#ffd700', '#c0c0c0', '#cd7f32']
  const color = rankColors[rank - 1] || '#888'

  return (
    <div className="card relative overflow-hidden">
      <div
        className="absolute top-0 left-0 w-1 h-full rounded-l-xl"
        style={{ background: color }}
      />
      <div className="pl-3">
        {/* Rank + Market */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-display font-bold text-2xl" style={{ color }}>#{rank}</span>
            <div>
              <p className="font-semibold text-white text-sm">{pick.market}</p>
              <p className="text-gray-500 text-xs">{pick.league} · {pick.sport === 'football' ? '⚽' : '🏒'}</p>
            </div>
          </div>
          <ConfidenceBadge label={pick.confidence_label} score={pick.confidence_score} />
        </div>

        {/* Teams */}
        <p className="text-gray-300 text-sm font-medium mb-3">
          {pick.home_team} <span className="text-gray-600">vs</span> {pick.away_team}
        </p>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="bg-surface-low rounded-lg p-2 text-center">
            <p className="text-gray-500 text-xs">Modell P</p>
            <p className="font-display font-bold text-accent-green text-base">
              {(pick.model_probability * 100).toFixed(1)}%
            </p>
          </div>
          <div className="bg-surface-low rounded-lg p-2 text-center">
            <p className="text-gray-500 text-xs">Faire Quote</p>
            <p className="font-display font-bold text-accent-blue text-base">
              {pick.fair_odds.toFixed(2)}
            </p>
          </div>
          <div className="bg-surface-low rounded-lg p-2 text-center">
            <p className="text-gray-500 text-xs">Score</p>
            <p className="font-display font-bold text-white text-base">
              {(pick.ranking_score * 100).toFixed(0)}
            </p>
          </div>
        </div>

        {pick.edge !== undefined && pick.bookmaker_odds && (
          <div className="flex items-center gap-1.5 text-xs mb-2">
            <TrendingUp className="w-3 h-3 text-accent-green" />
            <span className="text-gray-400">
              Buchmacher: <span className="text-white font-mono">{pick.bookmaker_odds.toFixed(2)}</span>
            </span>
            <span className={`font-semibold ${pick.edge > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
              Edge: {(pick.edge * 100).toFixed(1)}%
            </span>
          </div>
        )}

        {pick.explanation && (
          <p className="text-gray-500 text-xs leading-relaxed border-t border-surface-border pt-2">
            {pick.explanation}
          </p>
        )}
      </div>
    </div>
  )
}

export default function Top3Modal({ onClose }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['top3'],
    queryFn: api.predictions.top3,
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(0,0,0,0.8)' }}>
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl border border-surface-border" style={{ background: '#111111' }}>
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-surface-border sticky top-0 z-10" style={{ background: '#111111' }}>
          <div className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-accent-green" />
            <h2 className="font-display font-bold text-white text-lg">Top 3 Picks heute</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-surface-high transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-12 text-gray-500">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Berechne beste Picks...</span>
            </div>
          )}

          {isError && (
            <div className="flex items-center gap-2 text-accent-red py-8 justify-center">
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm">Fehler beim Laden. Backend erreichbar?</span>
            </div>
          )}

          {data && data.picks.length === 0 && (
            <div className="text-center text-gray-500 py-12">
              <Trophy className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>Keine Picks für heute verfügbar.</p>
              <p className="text-xs mt-1">Führe zuerst <code className="text-accent-blue">/admin/seed</code> aus.</p>
            </div>
          )}

          {data && data.picks.map((pick, i) => (
            <PickCard key={i} pick={pick} rank={i + 1} />
          ))}

          {data && (
            <p className="text-center text-gray-600 text-xs">
              Generiert: {new Date(data.generated_at).toLocaleTimeString('de-DE')}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
