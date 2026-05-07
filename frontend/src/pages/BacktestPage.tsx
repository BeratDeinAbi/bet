import { useQuery } from '@tanstack/react-query'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'
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
    <div className="space-y-8 max-w-5xl mx-auto">
      <header>
        <p className="smallcaps text-text-mute text-[11px] mb-1.5">
          Walk-forward · 60/40 Split
        </p>
        <h1 className="font-display font-medium text-text text-[36px] leading-[0.95] tracking-tighter2">
          Backtest-<span className="italic font-normal text-accent">Details</span>.
        </h1>
        <p className="text-text-mute text-[14px] mt-2 max-w-xl">
          Trainings-/Test-Aufteilung und Modell-Status für jede Liga.
        </p>
      </header>

      {/* Modell-Status */}
      <div className="card p-5">
        <h2 className="font-display text-text text-[20px] mb-4">Modell-Status</h2>
        {loadModels ? (
          <div className="flex gap-2 text-text-mute text-[13px]">
            <Loader2 className="w-4 h-4 animate-spin" /> Laden…
          </div>
        ) : (
          <div className="divide-y divide-canvas-line">
            {models?.map(m => (
              <div
                key={m.model_name}
                className="flex items-center justify-between py-2.5"
              >
                <div className="flex items-center gap-3">
                  {m.active ? (
                    <CheckCircle className="w-4 h-4 text-pos" />
                  ) : (
                    <XCircle className="w-4 h-4 text-neg" />
                  )}
                  <div>
                    <p className="text-text text-[13px] font-medium">
                      {m.model_name}
                    </p>
                    <p className="text-text-mute text-[11px]">
                      {m.sport} · v{m.model_version}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={
                      'text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded ' +
                      (m.active
                        ? 'bg-accent-soft text-accent-dim'
                        : 'bg-canvas-3 text-text-mute')
                    }
                  >
                    {m.active ? 'Trainiert' : 'Nicht trainiert'}
                  </span>
                  {m.training_date && (
                    <p className="text-text-quiet text-[11px] mt-0.5 font-mono">
                      {new Date(m.training_date).toLocaleDateString('de-DE')}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Backtest-Ergebnisse */}
      <div className="card p-5">
        <h2 className="font-display text-text text-[20px] mb-4">
          Backtest-Ergebnisse
        </h2>
        {loadSummaries ? (
          <div className="flex gap-2 text-text-mute text-[13px]">
            <Loader2 className="w-4 h-4 animate-spin" /> Laden…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-text-quiet text-[10px] uppercase tracking-wider border-b border-canvas-line">
                  <th className="text-left py-2 pr-4">Sport</th>
                  <th className="text-left py-2 pr-4">Liga</th>
                  <th className="text-left py-2 pr-4">Markt</th>
                  <th className="text-right py-2 pr-4">MAE</th>
                  <th className="text-right py-2 pr-4">RMSE</th>
                  <th className="text-right py-2 pr-4">Brier</th>
                  <th className="text-right py-2 pr-4">Kalibr.</th>
                  <th className="text-right py-2">N</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-canvas-line">
                {summaries?.map((s, i) => (
                  <tr key={i}>
                    <td className="py-2.5 pr-4 text-text capitalize">
                      {s.sport}
                    </td>
                    <td className="py-2.5 pr-4 text-text-dim">
                      {s.league || '-'}
                    </td>
                    <td className="py-2.5 pr-4 text-text-dim font-mono text-[11px]">
                      {s.market}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-accent-dim tabular-nums">
                      {s.mae.toFixed(3)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-accent-dim tabular-nums">
                      {s.rmse.toFixed(3)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-text-dim tabular-nums">
                      {s.brier_score.toFixed(3)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-pos tabular-nums">
                      {s.calibration_error.toFixed(3)}
                    </td>
                    <td className="py-2.5 text-right text-text-mute font-mono">
                      {s.sample_size}
                    </td>
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
