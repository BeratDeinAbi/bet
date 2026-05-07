import type { ConfidenceLabel } from '../types'
import clsx from 'clsx'

interface Props {
  label: ConfidenceLabel
  score?: number
}

/**
 * Confidence-Anzeige als kleiner Punkt + Smallcaps-Label.  Keine Pill,
 * kein Neon — die Ampelfarbe steckt nur im 6×6-Punkt davor, das Label
 * bleibt im Paper-Ton.
 */
const TONE: Record<ConfidenceLabel, string> = {
  HIGH: 'bg-pos',
  MEDIUM: 'bg-warn',
  LOW: 'bg-text-quiet',
}

const TEXT: Record<ConfidenceLabel, string> = {
  HIGH: 'Hoch',
  MEDIUM: 'Mittel',
  LOW: 'Niedrig',
}

export default function ConfidenceBadge({ label, score }: Props) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', TONE[label])} />
      <span className="smallcaps text-[10px] text-text-dim">
        {TEXT[label]}
        {score !== undefined && (
          <span className="font-mono text-text-mute ml-1.5 normal-case tracking-normal">
            {Math.round(score * 100)}
          </span>
        )}
      </span>
    </span>
  )
}
