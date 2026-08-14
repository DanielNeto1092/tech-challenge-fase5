import type { Analysis, FeatureContributionItem, FeatureContributions } from './types'

export const DEFAULT_DISCLAIMER =
  'Esta análise oferece apoio à decisão e não substitui avaliação, diagnóstico ou conduta de um profissional de saúde.'

const riskLabels: Record<string, string> = {
  low: 'Baixo risco',
  'low risk': 'Baixo risco',
  baixo: 'Baixo risco',
  medium: 'Risco moderado',
  mid: 'Risco moderado',
  'mid risk': 'Risco moderado',
  moderate: 'Risco moderado',
  medio: 'Risco moderado',
  médio: 'Risco moderado',
  high: 'Alto risco',
  'high risk': 'Alto risco',
  alto: 'Alto risco',
}

const featureLabels: Record<string, string> = {
  age: 'Idade',
  systolic_bp: 'Pressão sistólica',
  systolicbp: 'Pressão sistólica',
  diastolic_bp: 'Pressão diastólica',
  diastolicbp: 'Pressão diastólica',
  blood_sugar: 'Glicemia',
  bs: 'Glicemia',
  body_temperature: 'Temperatura corporal',
  bodytemp: 'Temperatura corporal',
  heart_rate: 'Frequência cardíaca',
  heartrate: 'Frequência cardíaca',
}

export function humanizeKey(value: string): string {
  const normalized = value.toLowerCase().replaceAll('-', '_').replaceAll(' ', '_')
  if (featureLabels[normalized]) return featureLabels[normalized]
  if (riskLabels[normalized]) return riskLabels[normalized]

  return value
    .replaceAll('_', ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/^./, (character) => character.toUpperCase())
}

export function getRiskLabel(level?: string, suppliedLabel?: string): string {
  if (suppliedLabel?.trim()) {
    return riskLabels[suppliedLabel.toLowerCase().trim()] ?? suppliedLabel
  }
  const normalized = (level ?? '').toLowerCase().trim()
  return riskLabels[normalized] ?? humanizeKey(level || 'Não informado')
}

export function getRiskTone(level?: string): 'low' | 'medium' | 'high' | 'neutral' {
  const normalized = (level ?? '').toLowerCase()
  if (normalized.includes('high') || normalized.includes('alto')) return 'high'
  if (
    normalized.includes('medium') ||
    normalized.includes('moderate') ||
    normalized.includes('mid') ||
    normalized.includes('médio') ||
    normalized.includes('medio')
  ) {
    return 'medium'
  }
  if (normalized.includes('low') || normalized.includes('baixo')) return 'low'
  return 'neutral'
}

export function toPercent(value: number): number {
  const percentage = Math.abs(value) <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, percentage))
}

export function formatPercent(value: number): string {
  return `${toPercent(value).toLocaleString('pt-BR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`
}

export function formatDate(value?: string): string {
  if (!value) return 'Data não informada'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

export interface NormalizedContribution {
  key: string
  label: string
  contribution: number | null
  value?: string | number
  impactText?: string
  direction?: string
}

export function normalizeContributions(
  contributions: FeatureContributions,
): NormalizedContribution[] {
  if (!contributions) return []

  if (!Array.isArray(contributions)) {
    return Object.entries(contributions).map(([key, contribution]) => ({
      key,
      label: humanizeKey(key),
      contribution,
    }))
  }

  return contributions.map((item: FeatureContributionItem, index) => {
    const key = item.feature ?? item.name ?? item.label ?? `fator_${index + 1}`
    let numericImpact =
      typeof item.contribution === 'number'
        ? item.contribution
        : typeof item.impact === 'number'
          ? item.impact
          : typeof item.importance === 'number'
            ? item.importance
            : null

    if (numericImpact != null && item.importance != null) {
      if (item.direction === 'decreases') numericImpact = -Math.abs(numericImpact)
      if (item.direction === 'neutral') numericImpact = 0
    }

    return {
      key,
      label: item.label ?? humanizeKey(key),
      contribution: numericImpact,
      value: item.value,
      impactText: typeof item.impact === 'string' ? item.impact : undefined,
      direction: item.direction,
    }
  })
}

export function analysisModelLabel(model: Analysis['model']): string {
  return `${model.name} · ${model.version}`
}

export function explanationMethodLabel(method: string): string {
  const labels: Record<string, string> = {
    exact_random_forest_path_probability_decomposition:
      'Decomposição exata dos caminhos da random forest',
    exact_multinomial_logit_decomposition:
      'Decomposição exata dos logits da regressão multinomial',
  }
  return labels[method] ?? humanizeKey(method)
}
