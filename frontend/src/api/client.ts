import type {
  MatchListResponse,
  Prediction,
  Top3Response,
  BacktestSummary,
  ModelStatus,
} from '../types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  health: () => get<{ status: string }>('/health'),

  matches: {
    today: (params?: { sport?: string; league?: string }) => {
      const qs = new URLSearchParams()
      if (params?.sport) qs.set('sport', params.sport)
      if (params?.league) qs.set('league', params.league)
      const query = qs.toString() ? `?${qs}` : ''
      return get<MatchListResponse>(`/matches/today${query}`)
    },
    byId: (id: number) => get<MatchListResponse['matches'][0]>(`/matches/${id}`),
  },

  predictions: {
    today: (params?: { sport?: string; league?: string }) => {
      const qs = new URLSearchParams()
      if (params?.sport) qs.set('sport', params.sport)
      if (params?.league) qs.set('league', params.league)
      const query = qs.toString() ? `?${qs}` : ''
      return get<Prediction[]>(`/predictions/today${query}`)
    },
    /** Historische Predictions, die an dem angegebenen Tag erstellt wurden. */
    byDate: (date: string, params?: { sport?: string; league?: string }) => {
      const qs = new URLSearchParams({ date })
      if (params?.sport) qs.set('sport', params.sport)
      if (params?.league) qs.set('league', params.league)
      return get<Prediction[]>(`/predictions/by-date?${qs}`)
    },
    /** Verfügbare Snapshot-Tage (für Date-Picker). */
    historyDates: (limit = 60) =>
      get<string[]>(`/predictions/history/dates?limit=${limit}`),
    /** Top 3.  Ohne Datum live, mit Datum historisch. */
    top3: (date?: string | null) => {
      const query = date ? `?date=${encodeURIComponent(date)}` : ''
      return get<Top3Response>(`/predictions/top3${query}`)
    },
    forMatch: (matchId: number) => get<Prediction>(`/predictions/${matchId}`),
  },

  admin: {
    refresh: () => post<{ status: string }>('/admin/refresh'),
    train: () => post<{ status: string }>('/admin/train'),
    seed: () => post<{ status: string; matches_ingested: number; predictions_generated: number }>('/admin/seed'),
  },

  backtests: {
    summary: () => get<BacktestSummary[]>('/backtests/summary'),
    modelStatus: () => get<ModelStatus[]>('/backtests/models/status'),
    recent: (limit = 25, sport?: string) => {
      const qs = new URLSearchParams({ limit: String(limit) })
      if (sport) qs.set('sport', sport)
      return get<RecentOutcome[]>(`/backtests/recent?${qs}`)
    },
    accuracy: (days = 30) => get<AccuracySummary>(`/backtests/accuracy?days=${days}`),
    recommended: (sport?: string, onlyEvaluated = false, limit = 200) => {
      const qs = new URLSearchParams({ limit: String(limit) })
      if (sport) qs.set('sport', sport)
      if (onlyEvaluated) qs.set('only_evaluated', 'true')
      return get<RecommendedPick[]>(`/backtests/recommended?${qs}`)
    },
    recommendedAccuracy: () =>
      get<RecommendedAccuracy>('/backtests/recommended/accuracy'),
  },
}

export interface RecommendedPick {
  id: number
  match_id: number
  sport: string
  league: string
  home_team: string
  away_team: string
  kickoff_time: string | null
  market: string
  line: number
  direction: 'over' | 'under'
  model_probability: number
  fair_odds: number
  ranking_score: number
  confidence_label: string
  actual_total: number | null
  actual_hit: boolean | null
  evaluated_at: string | null
  match_status: string
}

export interface RecommendedAccuracy {
  n: number
  hits: number
  hit_rate: number
  by_sport: Record<string, {
    n: number
    hits: number
    hit_rate: number
    avg_prob: number
    avg_odds: number
  }>
}

export interface RecentOutcome {
  id: number
  match_id: number
  sport: string
  league: string
  home_team: string
  away_team: string
  kickoff_time: string | null
  actual_home: number
  actual_away: number
  actual_total: number
  expected_total: number
  total_abs_error: number
  primary_market: string | null
  primary_prob: number | null
  primary_hit: boolean | null
}

export interface AccuracySummary {
  days: number
  n: number
  hit_rate: number
  mae_total: number
  by_sport: Record<string, { n: number; hit_rate: number; mae: number }>
}
