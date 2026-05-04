import type { ConfidenceLabel } from '../types'
import clsx from 'clsx'

interface Props {
  label: ConfidenceLabel
  score?: number
}

const LABELS: Record<ConfidenceLabel, string> = {
  HIGH: 'Hoch',
  MEDIUM: 'Mittel',
  LOW: 'Niedrig',
}

export default function ConfidenceBadge({ label, score }: Props) {
  return (
    <span className={clsx(
      'text-[10px] font-bold px-2 py-0.5 rounded tracking-wider uppercase',
      label === 'HIGH' && 'bg-accent-green/15 text-accent-green',
      label === 'MEDIUM' && 'bg-accent-amber/15 text-accent-amber',
      label === 'LOW' && 'bg-white/5 text-gray-500',
    )}>
      {LABELS[label]}{score !== undefined ? ` · ${Math.round(score * 100)}%` : ''}
    </span>
  )
}
