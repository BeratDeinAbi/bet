export type Sport = 'football' | 'hockey' | 'basketball' | 'baseball'
export type LeagueCode = 'BL1' | 'BL2' | 'PL' | 'PD' | 'SSL' | 'NHL' | 'NBA' | 'MLB'
export type ConfidenceLabel = 'HIGH' | 'MEDIUM' | 'LOW'

export interface Competition {
  code: string
  name: string
  sport: Sport
  country: string
}

export interface MatchSegment {
  segment_code: string
  home_score: number | null
  away_score: number | null
  total_goals: number | null
}

export interface Match {
  id: number
  external_id: string
  home_team_name: string
  away_team_name: string
  kickoff_time: string
  status: string
  sport: Sport
  home_score: number | null
  away_score: number | null
  competition: Competition | null
  segments: MatchSegment[]
}

export interface MatchListResponse {
  total: number
  matches: Match[]
}

export interface Prediction {
  id: number
  match_id: number
  sport: Sport
  league: string
  home_team: string
  away_team: string
  kickoff_time: string

  expected_total_goals: number
  expected_home_goals: number
  expected_away_goals: number

  prob_over_0_5: number
  prob_over_1_5: number
  prob_over_2_5: number
  prob_over_3_5: number
  prob_under_0_5: number
  prob_under_1_5: number
  prob_under_2_5: number
  prob_under_3_5: number

  // Football
  expected_goals_h1?: number
  expected_goals_h2?: number
  prob_over_0_5_h1?: number
  prob_over_1_5_h1?: number
  prob_over_0_5_h2?: number
  prob_over_1_5_h2?: number

  // NHL
  expected_goals_p1?: number
  expected_goals_p2?: number
  expected_goals_p3?: number
  prob_over_0_5_p1?: number
  prob_over_1_5_p1?: number
  prob_over_0_5_p2?: number
  prob_over_1_5_p2?: number
  prob_over_0_5_p3?: number
  prob_over_1_5_p3?: number

  // Sport-spezifische Erweiterungen (NBA: 200.5–240.5 Total + Q1–Q4)
  extra_markets?: Record<string, number | number[]> | null

  confidence_score: number
  confidence_label: ConfidenceLabel
  model_agreement_score: number
  prediction_stability_score: number
  explanation: string | null

  recommended_pick?: RecommendedPickInline | null
}

export interface RecommendedPickInline {
  market: string
  line: number
  direction: 'over' | 'under'
  model_probability: number
  fair_odds: number
  confidence_label: ConfidenceLabel
  /** Bookmaker-Name (z. B. „betano") wenn Quote von echtem Anbieter kommt. */
  bookmaker_name?: string | null
  /** Echte Quote des Bookmakers (z. B. 1.32). */
  bookmaker_odds?: number | null
  /** Edge = model_probability − (1 / bookmaker_odds). */
  edge?: number | null
}

export interface Top3Pick {
  match_id: number
  sport: Sport
  league: string
  home_team: string
  away_team: string
  kickoff_time: string
  market: string
  market_line: number
  market_direction: string
  model_probability: number
  fair_odds: number
  bookmaker_odds?: number
  edge?: number
  confidence_score: number
  confidence_label: ConfidenceLabel
  ranking_score: number
  explanation: string
}

export interface Top3Response {
  generated_at: string
  picks: Top3Pick[]
}

export interface BacktestSummary {
  sport: string
  league?: string
  market: string
  mae: number
  rmse: number
  brier_score: number
  calibration_error: number
  sample_size: number
  period: string
}

export interface ModelStatus {
  sport: string
  model_name: string
  model_version: string
  training_date: string | null
  active: boolean
  metrics?: Record<string, unknown>
}
