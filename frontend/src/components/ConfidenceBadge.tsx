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
      'text-xs font-semibold px-2 py-0.5 rounded-full',
      label === 'HIGH' && 'bg-accent-green/20 text-accent-green',
      label === 'MEDIUM' && 'bg-accent-amber/20 text-accent-amber',
      label === 'LOW' && 'bg-accent-red/20 text-accent-red',
    )}>
      {LABELS[label]}{score !== undefined ? ` ${Math.round(score * 100)}%` : ''}
    </span>
  )
}
