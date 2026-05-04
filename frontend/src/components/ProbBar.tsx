interface Props {
  label: string
  probability: number
  color?: string
}

export default function ProbBar({ label, probability, color = '#60a5fa' }: Props) {
  const pct = Math.round(probability * 100)
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-baseline">
        <span className="text-[11px] text-gray-500 font-medium">{label}</span>
        <span className="text-[11px] font-bold tabular-nums" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: color, opacity: 0.85 }}
        />
      </div>
    </div>
  )
}
