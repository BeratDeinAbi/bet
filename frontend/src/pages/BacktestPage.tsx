import { useQuery } from '@tanstack/react-query'
import { Loader2, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import { api } from '../api/client'

export default function BacktestPage() {
  const { data: summaries, isLoading: loadSummaries } = useQuery({
    queryKey: ['backtests'],
    queryFn: api.backtests.summary,
  })

  const { data: models, isLoading: loadModels } = useQuery({
    queryKey: ['models'],
    queryFn: api.backtests.modelStatus,
  })

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-white text-2xl">Backtesting & Modell-Status</h1>
        <p className="text-gray-500 text-sm mt-0.5">Walk-forward Validierung · 60/40 Split</p>
      </div>

      {/* Model Status */}
      <div className="card mb-6">
        <h2 className="font-display font-semibold text-white mb-4">Modell-Status</h2>
        {loadModels ? (
          <div className="flex gap-2 text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /> Laden...</div>
        ) : (
          <div className="space-y-2">
            {models?.map(m => (
              <div key={m.model_name} className="flex items-center justify-between py-2 border-b border-surface-border last:border-0">
                <div className="flex items-center gap-3">
                  {m.active
                    ? <CheckCircle className="w-4 h-4 text-accent-green" />
                    : <XCircle className="w-4 h-4 text-accent-red" />
                  }
                  <div>
                    <p className="text-white text-sm font-medium">{m.model_name}</p>
                    <p className="text-gray-500 text-xs">{m.sport} · v{m.model_version}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${m.active ? 'bg-accent-green/20 text-accent-green' : 'bg-gray-800 text-gray-500'}`}>
                    {m.active ? 'Trainiert' : 'Nicht trainiert'}
                  </span>
                  {m.training_date && (
                    <p className="text-gray-600 text-xs mt-0.5">
                      {new Date(m.training_date).toLocaleDateString('de-DE')}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Backtest Results */}
      <div className="card">
        <h2 className="font-display font-semibold text-white mb-4">Backtest-Ergebnisse</h2>
        {loadSummaries ? (
          <div className="flex gap-2 text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /> Laden...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-surface-border">
                  <th className="text-left py-2 pr-4">Sport</th>
                  <th className="text-left py-2 pr-4">Liga</th>
                  <th className="text-left py-2 pr-4">Markt</th>
                  <th className="text-right py-2 pr-4">MAE</th>
                  <th className="text-right py-2 pr-4">RMSE</th>
                  <th className="text-right py-2 pr-4">Brier</th>
                  <th className="text-right py-2 pr-4">Kalibrierung</th>
                  <th className="text-right py-2">N</th>
                </tr>
              </thead>
              <tbody>
                {summaries?.map((s, i) => (
                  <tr key={i} className="border-b border-surface-border last:border-0">
                    <td className="py-2.5 pr-4 text-white">{s.sport === 'football' ? '⚽' : '🏒'} {s.sport}</td>
                    <td className="py-2.5 pr-4 text-gray-300">{s.league || '-'}</td>
                    <td className="py-2.5 pr-4 text-gray-300 font-mono text-xs">{s.market}</td>
                    <td className="py-2.5 pr-4 text-right font-mono text-accent-blue">{s.mae.toFixed(3)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono text-accent-blue">{s.rmse.toFixed(3)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">{s.brier_score.toFixed(3)}</td>
                    <td className="py-2.5 pr-4 text-right font-mono text-xs text-accent-green">{s.calibration_error.toFixed(3)}</td>
                    <td className="py-2.5 text-right text-gray-500">{s.sample_size}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
