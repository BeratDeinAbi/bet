interface Props {
  label: string
  probability: number
  /** Akzent-Override.  Default ist accent-grün. */
  color?: string
}

/**
 * Schlanker Wahrscheinlichkeits-Anzeiger für helles Theme:
 *  - 3 px hoch (auf hell muss sie etwas dicker sein um sichtbar zu sein)
 *  - Track in canvas-3 (sichtbar aber nicht aufdringlich)
 *  - Wert in Mono mit konstanter Spaltenbreite
 */
export default function ProbBar({
  label,
  probability,
  color = '#2d7a3e', // accent green default
}: Props) {
  const pct = Math.round(probability * 100)
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-baseline gap-3">
        <span className="smallcaps text-[10px] text-text-mute">{label}</span>
        <span
          className="font-mono text-[11px] font-semibold tabular-nums"
          style={{ color }}
        >
          {pct}%
        </span>
      </div>
      <div className="h-[3px] bg-canvas-3 rounded-full overflow-hidden">
        <div
          className="h-full transition-[width] duration-300 ease-out rounded-full"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
