import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { Analysis } from '../types'

const completedAnalysis: Analysis = {
  id: 'analise-001',
  created_at: '2026-08-14T14:30:00-03:00',
  risk_level: 'high',
  risk_label: 'Alto risco',
  probabilities: { low: 0.08, medium: 0.17, high: 0.75 },
  model: { name: 'Random Forest', version: '1.0' },
  explanation_method: 'exact_random_forest_path_probability_decomposition',
  reconstruction_error: 1e-16,
  feature_contributions: [
    {
      feature: 'blood_sugar',
      label: 'Glicemia',
      value: 7.5,
      importance: 0.41,
      direction: 'increases',
    },
    {
      feature: 'systolic_bp',
      label: 'Pressão sistólica',
      value: 120,
      importance: 0.22,
      direction: 'decreases',
    },
  ],
  explanation: 'O resultado foi influenciado principalmente pela glicemia informada.',
  llm_used: true,
  llm_model: 'gpt-5.6-luna',
  sources: [{ title: 'Manual de gestação de alto risco', page: 32 }],
  disclaimer: 'Resultado de apoio à decisão; não substitui avaliação profissional.',
  input_data: {
    age: 30,
    systolic_bp: 120,
    diastolic_bp: 80,
    blood_sugar: 7.5,
    body_temperature: 98.6,
    heart_rate: 76,
    question: 'Como interpretar?',
  },
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function fillSupportedValues() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/Idade/), '30')
  await user.type(screen.getByLabelText(/Pressão sistólica/), '120')
  await user.type(screen.getByLabelText(/Pressão diastólica/), '80')
  await user.type(screen.getByLabelText(/Glicemia/), '7.5')
  await user.type(screen.getByLabelText(/Temperatura corporal/), '98.6')
  await user.type(screen.getByLabelText(/Frequência cardíaca/), '76')
  return user
}

describe('Guardiã AI', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('apresenta o formulário acessível, o aviso clínico e os limites do modelo', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /clareza para apoiar/i })).toBeInTheDocument()
    expect(screen.getByText('Apoio à decisão, não diagnóstico')).toBeInTheDocument()
    expect(screen.getByText(/faixa suportada: 10–70 anos/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Frequência cardíaca/)).toHaveAttribute('min', '7')
    expect(screen.getByLabelText(/Frequência cardíaca/)).toHaveAttribute('max', '90')
    expect(screen.getByText(/não inclua dados identificáveis/i)).toBeInTheDocument()
  })

  it('envia o contrato esperado e exibe resultado, explicação, fatores e fontes', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(completedAnalysis))
    render(<App />)
    const user = await fillSupportedValues()
    await user.type(screen.getByLabelText(/Pergunta para a assistente/), 'Como interpretar?')
    await user.click(screen.getByRole('button', { name: /analisar risco materno/i }))

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe('/api/v1/analyses')
    expect(options?.method).toBe('POST')
    expect(JSON.parse(String(options?.body))).toEqual({
      age: 30,
      systolic_bp: 120,
      diastolic_bp: 80,
      blood_sugar: 7.5,
      body_temperature: 98.6,
      heart_rate: 76,
      question: 'Como interpretar?',
    })

    expect(await screen.findByRole('heading', { name: 'Resultado da triagem' })).toBeInTheDocument()
    expect(screen.getAllByText('Alto risco').length).toBeGreaterThan(0)
    expect(screen.getByText('75,0%')).toBeInTheDocument()
    expect(screen.getByText(completedAnalysis.explanation!)).toBeInTheDocument()
    expect(screen.getByText('Manual de gestação de alto risco')).toBeInTheDocument()
    expect(screen.getAllByText('Glicemia').length).toBeGreaterThan(0)
    expect(screen.getByText(/erro de reconstrução/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dados utilizados' })).toBeInTheDocument()
  })

  it('bloqueia valores fora da faixa suportada antes de chamar o backend', async () => {
    render(<App />)
    const user = await fillSupportedValues()
    const heartRate = screen.getByLabelText(/Frequência cardíaca/)
    await user.clear(heartRate)
    await user.type(heartRate, '6')
    await user.click(screen.getByRole('button', { name: /analisar risco materno/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /frequência cardíaca: informe um valor entre 7 e 90 bpm/i,
    )
    expect(fetch).not.toHaveBeenCalled()
  })

  it('informa claramente quando a chave da LLM não está configurada', async () => {
    const noLlmExplanation =
      'A explicação por LLM não foi executada porque GUARDIA_OPENAI_API_KEY não está configurada.'
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        ...completedAnalysis,
        explanation: noLlmExplanation,
        llm_used: false,
      }),
    )
    render(<App />)
    const user = await fillSupportedValues()
    await user.click(screen.getByRole('button', { name: /analisar risco materno/i }))

    expect(await screen.findByText('Explicação por LLM não executada')).toBeInTheDocument()
    expect(screen.getByText(noLlmExplanation)).toBeInTheDocument()
    expect(screen.getByText('Manual de gestação de alto risco')).toBeInTheDocument()
  })

  it('consulta e apresenta o histórico das últimas vinte análises', async () => {
    const summary = {
      id: completedAnalysis.id,
      created_at: completedAnalysis.created_at,
      risk_level: completedAnalysis.risk_level,
      risk_label: completedAnalysis.risk_label,
      model: completedAnalysis.model,
      llm_used: completedAnalysis.llm_used,
    }
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ items: [summary], total: 1 }))
      .mockResolvedValueOnce(jsonResponse(completedAnalysis))
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Histórico' }))

    expect(await screen.findByText('analise-001')).toBeInTheDocument()
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      '/api/v1/analyses?limit=20',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
    await user.click(screen.getByRole('button', { name: 'Ver dados utilizados' }))
    expect(await screen.findByText('Pergunta enviada')).toBeInTheDocument()
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      '/api/v1/analyses/analise-001',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
  })

  it('consulta e apresenta as métricas publicadas pelo backend', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        model_version: '1.0.0',
        selected_model: 'Random Forest',
        evaluations: {
          'Random Forest': {
            accuracy: 0.91,
            f1_macro: 0.89,
            confusion_matrix: [[10, 1], [2, 9]],
            confusion_matrix_label_order: ['low', 'high'],
          },
          'Logistic Regression': {
            accuracy: 0.87,
            f1_macro: 0.84,
          },
        },
      }),
    )
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Desempenho' }))

    expect(await screen.findByText('91,0%')).toBeInTheDocument()
    expect(screen.getByText('89,0%')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Matriz de confusão' })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/model/metrics',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
  })
})
