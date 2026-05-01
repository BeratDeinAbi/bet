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
    top3: () => get<Top3Response>('/predictions/top3'),
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
  },
}
