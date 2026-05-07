import clsx from 'clsx'

export interface SportSelection {
  league: string
  sport: string
}

interface Props {
  selected: SportSelection
  onChange: (s: SportSelection) => void
  counts?: Record<string, number>  // Liga-Code → Anzahl Predictions
}

interface LeagueItem {
  code: string
  sport: string
  label: string
  comingSoon?: boolean
}

interface Section {
  title: string
  items: LeagueItem[]
}

const SECTIONS: Section[] = [
  {
    title: 'Fußball',
    items: [
      { code: 'BL1', sport: 'football', label: 'Bundesliga' },
      { code: 'BL2', sport: 'football', label: '2. Bundesliga' },
      { code: 'PL', sport: 'football', label: 'Premier League' },
      { code: 'PD', sport: 'football', label: 'La Liga' },
      { code: 'SSL', sport: 'football', label: 'Süper Lig' },
    ],
  },
  {
    title: 'US-Sport',
    items: [
      { code: 'NHL', sport: 'hockey', label: 'NHL' },
      { code: 'NBA', sport: 'basketball', label: 'NBA' },
      { code: 'MLB', sport: 'baseball', label: 'MLB' },
    ],
  },
  {
    title: 'Bald verfügbar',
    items: [
      { code: 'TENNIS', sport: 'tennis', label: 'Tennis', comingSoon: true },
    ],
  },
]

export default function SportSidebar({ selected, onChange, counts }: Props) {
  return (
    <nav className="space-y-7">
      {/* All */}
      <button
        onClick={() => onChange({ league: '', sport: '' })}
        className={clsx(
          'w-full text-left px-3 py-2 rounded-md transition-colors flex items-center justify-between text-[13px]',
          selected.league === ''
            ? 'bg-accent-soft text-accent-dim font-semibold'
            : 'text-text-dim hover:bg-canvas-2 hover:text-text',
        )}
      >
        <span>Alle Spiele</span>
        {counts && counts.__total !== undefined && (
          <span className="font-mono text-[11px] text-text-mute tabular-nums">
            {counts.__total}
          </span>
        )}
      </button>

      {SECTIONS.map(section => (
        <div key={section.title}>
          <p className="smallcaps text-[10px] text-text-quiet px-3 mb-2">
            {section.title}
          </p>
          <ul className="space-y-0.5">
            {section.items.map(item => {
              const isActive = selected.league === item.code
              const count = counts?.[item.code]
              const disabled = item.comingSoon
              return (
                <li key={item.code}>
                  <button
                    disabled={disabled}
                    onClick={() => !disabled && onChange({
                      league: item.code,
                      sport: item.sport,
                    })}
                    className={clsx(
                      'w-full text-left px-3 py-1.5 rounded-md transition-colors flex items-center justify-between text-[13px]',
                      isActive && !disabled
                        ? 'bg-accent-soft text-accent-dim font-semibold'
                        : disabled
                          ? 'text-text-quiet cursor-not-allowed'
                          : 'text-text-dim hover:bg-canvas-2 hover:text-text',
                    )}
                  >
                    <span className="flex items-center gap-2">
                      {item.label}
                      {disabled && (
                        <span className="text-[9px] uppercase tracking-wider font-semibold bg-canvas-3 text-text-mute px-1.5 py-0.5 rounded">
                          Bald
                        </span>
                      )}
                    </span>
                    {count !== undefined && count > 0 && !disabled && (
                      <span className={clsx(
                        'font-mono text-[11px] tabular-nums',
                        isActive ? 'text-accent-dim' : 'text-text-mute',
                      )}>
                        {count}
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}
