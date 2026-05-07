interface Props {
  label: string
  probability: number
  /** Akzent-Override.  Default ist Terracotta (signal). */
  color?: string
}

/**
 * Schlanker Wahrscheinlichkeits-Anzeiger.  Bewusste Entscheidungen:
 *  - 2 px hoch statt 4 (weniger „Tailwind-Pillen-Look")
 *  - Track in warmem Ink-Ton statt 5%-Weiß-Overlay
 *  - Kein Rounded — flach, läuft horizontal aus
 *  - Wert in Mono mit konstanter Spaltenbreite, Label in Smallcaps
 */
export default function ProbBar({
  label,
  probability,
  color = '#d97757', // signal default
}: Props) {
  const pct = Math.round(probability * 100)
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-baseline gap-3">
        <span className="smallcaps text-[10px] text-paper-mute">{label}</span>
        <span
          className="font-mono text-[11px] font-medium tabular-nums"
          style={{ color }}
        >
          {pct}%
        </span>
      </div>
      <div className="h-[2px] bg-ink-3 overflow-hidden">
        <div
          className="h-full transition-[width] duration-300 ease-out"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
