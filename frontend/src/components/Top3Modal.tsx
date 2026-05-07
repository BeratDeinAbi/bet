import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { X, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../api/client'
import type { Top3Pick } from '../types'
import ConfidenceBadge from './ConfidenceBadge'

interface Props {
  onClose: () => void
}

/**
 * Top-3-Modal als „Notiz" — kein Trophy-Icon, keine Trophäen-Farben
 * (Gold/Silber/Bronze).  Stattdessen redaktionelle Nummerierung
 * (große Serif-Ziffer) und ruhige Tabellen-Sektionen.
 */
export default function Top3Modal({ onClose }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['top3'],
    queryFn: api.predictions.top3,
  })

  // ESC schließt das Modal — kleine Geste, aber vom UX gehört's dazu.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 sm:p-8 overflow-y-auto bg-ink/85 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl surface rounded-md mt-8 sm:mt-16 mb-8"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 sm:px-8 pt-6 pb-5 border-b border-ink-line">
          <div>
            <p className="smallcaps text-[10px] text-paper-mute mb-1.5">
              Tagesbriefing
            </p>
            <h2 className="font-display font-medium text-paper text-[28px] tracking-tighter2 leading-none">
              Drei <span className="italic font-normal">Picks</span> für heute
            </h2>
            <p className="text-paper-mute text-[12px] mt-2 max-w-md">
              Verschiedene Spiele, faire Quote ≥ 1,24 — keine trivialen
              Lock-Picks, sondern Vorschläge mit Wettwert.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 -mt-1 -mr-2 text-paper-mute hover:text-paper transition-colors"
            aria-label="Schließen"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 sm:px-8 py-6">
          {isLoading && (
            <div className="flex items-center gap-2 py-12 text-paper-mute">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-[13px]">Berechne Picks…</span>
            </div>
          )}

          {isError && (
            <div className="flex items-start gap-3 py-8">
              <AlertCircle className="w-5 h-5 text-neg shrink-0 mt-0.5" />
              <p className="text-paper-dim text-[13px]">
                Fehler beim Laden. Ist das Backend erreichbar?
              </p>
            </div>
          )}

          {data && data.picks.length === 0 && (
            <div className="py-10">
              <p className="font-display italic text-paper-dim text-base">
                Heute keine Picks mit ausreichend Wert.
              </p>
              <p className="text-paper-mute text-[12px] mt-2">
                Führe{' '}
                <code className="font-mono text-signal-high">
                  POST /admin/seed
                </code>{' '}
                aus oder prüfe, ob Spiele für heute vorhanden sind.
              </p>
            </div>
          )}

          {data &&
            data.picks.map((pick, i) => (
              <PickRow key={i} pick={pick} rank={i + 1} />
            ))}

          {data && data.picks.length > 0 && (
            <p className="text-paper-quiet text-[11px] mt-6 pt-4 rule font-mono">
              {new Date(data.generated_at).toLocaleString('de-DE', {
                hour: '2-digit',
                minute: '2-digit',
                day: '2-digit',
                month: '2-digit',
              })}
              {' · '}
              ranking_score = 0.55·prob + 0.35·trust + 0.10·info
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function PickRow({ pick, rank }: { pick: Top3Pick; rank: number }) {
  return (
    <article className="grid grid-cols-[40px_1fr] gap-5 py-5 border-b border-ink-line last:border-b-0">
      {/* Große Serif-Nummer als Marker */}
      <div className="font-display font-medium text-paper-quiet text-[40px] leading-none tracking-tighter2 italic">
        {rank}
      </div>

      <div>
        <header className="flex items-center justify-between mb-2 gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="smallcaps text-[10px] text-signal font-medium shrink-0">
              {pick.league}
            </span>
            <span className="text-paper-quiet text-[10px] shrink-0">·</span>
            <span className="font-display text-paper text-[15px] truncate">
              {pick.market}
            </span>
          </div>
          <ConfidenceBadge label={pick.confidence_label} score={pick.confidence_score} />
        </header>

        <p className="font-display text-paper-dim text-[14px] mb-3">
          {pick.home_team}
          <span className="text-paper-quiet font-normal mx-1.5">vs</span>
          {pick.away_team}
        </p>

        <div className="flex items-baseline gap-x-6 gap-y-2 flex-wrap text-[12px]">
          <Stat label="Modell-P" value={`${(pick.model_probability * 100).toFixed(1)} %`} accent />
          <Stat label="Faire Quote" value={pick.fair_odds.toFixed(2)} mono />
          <Stat label="Score" value={(pick.ranking_score * 100).toFixed(0)} mono />
          {pick.bookmaker_odds && (
            <Stat label="Buchmacher" value={pick.bookmaker_odds.toFixed(2)} mono />
          )}
          {pick.edge !== undefined && (
            <Stat
              label="Edge"
              value={`${(pick.edge * 100 >= 0 ? '+' : '')}${(pick.edge * 100).toFixed(1)} %`}
              tone={pick.edge >= 0 ? 'pos' : 'neg'}
            />
          )}
        </div>

        {pick.explanation && (
          <p className="font-display italic text-paper-mute text-[12px] leading-relaxed mt-3">
            {pick.explanation}
          </p>
        )}
      </div>
    </article>
  )
}

function Stat({
  label,
  value,
  mono,
  accent,
  tone,
}: {
  label: string
  value: string
  mono?: boolean
  accent?: boolean
  tone?: 'pos' | 'neg'
}) {
  const valueClass = [
    mono ? 'font-mono' : 'font-display',
    'tabular-nums font-medium',
    accent ? 'text-signal-high' : '',
    tone === 'pos' ? 'text-pos' : '',
    tone === 'neg' ? 'text-neg' : '',
    !accent && !tone ? 'text-paper' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div>
      <p className="smallcaps text-[9px] text-paper-quiet">{label}</p>
      <p className={valueClass + ' text-[14px] leading-tight mt-0.5'}>{value}</p>
    </div>
  )
}
