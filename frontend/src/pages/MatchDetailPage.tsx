import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { api } from '../api/client'
import ConfidenceBadge from '../components/ConfidenceBadge'
import ProbBar from '../components/ProbBar'

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
      <div className="flex items-center justify-center py-20 gap-2 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin" />
        Lade Match-Details...
      </div>
    )
  }

  if (isError || !pred) {
    return (
      <div className="flex flex-col items-center gap-3 py-16">
        <AlertCircle className="w-10 h-10 text-accent-red opacity-60" />
        <p className="text-white">Prognose nicht gefunden</p>
        <Link to="/" className="text-accent-blue text-sm hover:underline">Zurück zum Dashboard</Link>
      </div>
    )
  }

  const isFootball = pred.sport === 'football'

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="flex items-center gap-1.5 text-gray-500 hover:text-white text-sm mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Zurück
      </Link>

      {/* Match Header */}
      <div className="card mb-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-gray-500 text-xs">{pred.league} · {pred.sport === 'football' ? '⚽' : '🏒'}</p>
            <p className="text-gray-400 text-xs mt-0.5">
              {new Date(pred.kickoff_time).toLocaleString('de-DE')}
            </p>
          </div>
          <ConfidenceBadge label={pred.confidence_label} score={pred.confidence_score} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="font-display font-bold text-white text-xl">{pred.home_team}</p>
            <p className="text-gray-500 text-sm mt-1">Erwartete Tore: <span className="text-white font-semibold">{pred.expected_home_goals.toFixed(2)}</span></p>
          </div>
          <div className="text-center px-6">
            <p className="font-display font-bold text-3xl text-accent-green">{pred.expected_total_goals.toFixed(2)}</p>
            <p className="text-gray-600 text-xs">Gesamttore</p>
          </div>
          <div className="flex-1 text-right">
            <p className="font-display font-bold text-white text-xl">{pred.away_team}</p>
            <p className="text-gray-500 text-sm mt-1">Erwartete Tore: <span className="text-white font-semibold">{pred.expected_away_goals.toFixed(2)}</span></p>
          </div>
        </div>
      </div>

      {/* Full Game O/U */}
      <div className="card mb-5">
        <h3 className="font-display font-semibold text-white mb-4">Gesamttore Over/Under</h3>
        <div className="space-y-2.5">
          <ProbBar label="Over 0.5" probability={pred.prob_over_0_5} color="#8eff71" />
          <ProbBar label="Over 1.5" probability={pred.prob_over_1_5} color="#60a5fa" />
          <ProbBar label="Over 2.5" probability={pred.prob_over_2_5} color="#a78bfa" />
          <ProbBar label="Over 3.5" probability={pred.prob_over_3_5} color="#fbbf24" />
          <div className="border-t border-surface-border pt-2.5">
            <ProbBar label="Under 1.5" probability={pred.prob_under_1_5} color="#f87171" />
            <div className="mt-2">
              <ProbBar label="Under 2.5" probability={pred.prob_under_2_5} color="#f87171" />
            </div>
          </div>
        </div>
      </div>

      {/* Segments */}
      {isFootball && pred.expected_goals_h1 !== undefined && (
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div className="card">
            <h3 className="font-display font-semibold text-white mb-3">1. Halbzeit</h3>
            <p className="font-display font-bold text-accent-green text-2xl mb-3">{pred.expected_goals_h1!.toFixed(2)}</p>
            <div className="space-y-2">
              <ProbBar label="Over 0.5 H1" probability={pred.prob_over_0_5_h1 ?? 0} />
              <ProbBar label="Over 1.5 H1" probability={pred.prob_over_1_5_h1 ?? 0} color="#a78bfa" />
            </div>
          </div>
          <div className="card">
            <h3 className="font-display font-semibold text-white mb-3">2. Halbzeit</h3>
            <p className="font-display font-bold text-accent-green text-2xl mb-3">{pred.expected_goals_h2!.toFixed(2)}</p>
            <div className="space-y-2">
              <ProbBar label="Over 0.5 H2" probability={pred.prob_over_0_5_h2 ?? 0} />
              <ProbBar label="Over 1.5 H2" probability={pred.prob_over_1_5_h2 ?? 0} color="#a78bfa" />
            </div>
          </div>
        </div>
      )}

      {!isFootball && pred.expected_goals_p1 !== undefined && (
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: 'Periode 1', exp: pred.expected_goals_p1, o05: pred.prob_over_0_5_p1, o15: pred.prob_over_1_5_p1 },
            { label: 'Periode 2', exp: pred.expected_goals_p2, o05: pred.prob_over_0_5_p2, o15: pred.prob_over_1_5_p2 },
            { label: 'Periode 3', exp: pred.expected_goals_p3, o05: pred.prob_over_0_5_p3, o15: pred.prob_over_1_5_p3 },
          ].map(({ label, exp, o05, o15 }) => (
            <div key={label} className="card">
              <h3 className="font-display font-semibold text-white mb-2 text-sm">{label}</h3>
              <p className="font-display font-bold text-accent-green text-2xl mb-3">{(exp ?? 0).toFixed(2)}</p>
              <div className="space-y-2">
                <ProbBar label="O 0.5" probability={o05 ?? 0} />
                <ProbBar label="O 1.5" probability={o15 ?? 0} color="#a78bfa" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Model Info */}
      <div className="card mb-5">
        <h3 className="font-display font-semibold text-white mb-4">Modell-Metriken</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-gray-500 text-xs mb-1">Konfidenz</p>
            <p className="font-display font-bold text-white text-xl">{(pred.confidence_score * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs mb-1">Modell-Übereinstimmung</p>
            <p className="font-display font-bold text-white text-xl">{(pred.model_agreement_score * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs mb-1">Prognose-Stabilität</p>
            <p className="font-display font-bold text-white text-xl">{(pred.prediction_stability_score * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      {/* Explanation */}
      {pred.explanation && (
        <div className="card">
          <h3 className="font-display font-semibold text-white mb-2">Prognose-Erklärung</h3>
          <p className="text-gray-400 text-sm leading-relaxed">{pred.explanation}</p>
          <p className="text-gray-600 text-xs mt-3">
            Ensemble: Poisson MLE + Dixon-Coles Korrektur + Elo Rating
          </p>
        </div>
      )}
    </div>
  )
}
