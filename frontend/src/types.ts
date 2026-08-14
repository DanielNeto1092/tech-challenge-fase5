export interface AnalysisRequest {
  age: number
  systolic_bp: number
  diastolic_bp: number
  blood_sugar: number
  body_temperature: number
  heart_rate: number
  question?: string | null
}

export type ProbabilityMap = Record<string, number>

export interface ModelInfo {
  name: string
  version: string
}

export interface FeatureContributionItem {
  feature?: string
  name?: string
  label?: string
  value?: number | string
  contribution?: number
  impact?: number | string
  importance?: number
  direction?: 'increases' | 'decreases' | 'neutral' | string
}

export type FeatureContributions =
  | Record<string, number>
  | FeatureContributionItem[]
  | null

export interface RagSource {
  title?: string
  name?: string
  source?: string
  url?: string
  excerpt?: string
  content?: string
  page?: string | number
  reference?: string
  relevance_score?: number
}

export interface Analysis {
  id: string
  created_at: string
  risk_level: string
  risk_label: string
  probabilities: ProbabilityMap
  model: ModelInfo
  feature_contributions: FeatureContributions
  explanation_method: string
  reconstruction_error: number
  explanation: string | null
  llm_used: boolean
  llm_model: string | null
  sources: Array<RagSource | string>
  disclaimer: string
  input_data?: AnalysisRequest | null
}

export interface HistoryPayload {
  items?: AnalysisSummary[]
  analyses?: AnalysisSummary[]
  results?: AnalysisSummary[]
}

export type AnalysisSummary = Pick<
  Analysis,
  'id' | 'created_at' | 'risk_level' | 'risk_label' | 'model' | 'llm_used' | 'input_data'
>

export type MetricsPayload = Record<string, unknown>
