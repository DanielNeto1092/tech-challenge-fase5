import type {
  Analysis,
  AnalysisRequest,
  AnalysisSummary,
  HistoryPayload,
  MetricsPayload,
} from './types'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>
      message?: string
    }

    if (typeof payload.detail === 'string') return payload.detail
    if (Array.isArray(payload.detail)) {
      const messages = payload.detail.map((item) => item.msg).filter(Boolean)
      if (messages.length) return messages.join(' • ')
    }
    if (payload.message) return payload.message
  } catch {
    // The API can return an empty or non-JSON error response.
  }

  return 'Não foi possível concluir a solicitação.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(
      'Não foi possível conectar ao serviço. Verifique se o backend está disponível.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status)
  }

  return (await response.json()) as T
}

export function createAnalysis(payload: AnalysisRequest): Promise<Analysis> {
  return request<Analysis>('/api/v1/analyses', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getAnalysis(id: string): Promise<Analysis> {
  return request<Analysis>(`/api/v1/analyses/${encodeURIComponent(id)}`)
}

export async function getHistory(limit = 20): Promise<AnalysisSummary[]> {
  const payload = await request<AnalysisSummary[] | HistoryPayload>(
    `/api/v1/analyses?limit=${encodeURIComponent(limit)}`,
  )

  if (Array.isArray(payload)) return payload
  return payload.items ?? payload.analyses ?? payload.results ?? []
}

export function getModelMetrics(): Promise<MetricsPayload> {
  return request<MetricsPayload>('/api/v1/model/metrics')
}
