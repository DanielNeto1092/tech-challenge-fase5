import { useEffect, useMemo, useState } from 'react'
import { getModelMetrics } from '../api'
import type { MetricsPayload } from '../types'
import { formatDate, humanizeKey } from '../utils'

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function displayScalar(key: string, value: string | number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não'
  if (typeof value === 'string') {
    if (/(_at|date|data|trained)$/i.test(key)) return formatDate(value)
    return value
  }

  const metricKey = key.toLowerCase()
  const isRate = ['accuracy', 'precision', 'recall', 'f1', 'auc', 'specificity'].some(
    (part) => metricKey.includes(part),
  )
  if (isRate && Math.abs(value) <= 1) {
    return value.toLocaleString('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 2,
    })
  }
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 4 })
}

function ScalarCards({ values }: { values: UnknownRecord }) {
  const entries = Object.entries(values).filter(
    ([, value]) => ['string', 'number', 'boolean'].includes(typeof value),
  ) as Array<[string, string | number | boolean]>

  if (!entries.length) return null

  return (
    <div className="metrics-cards">
      {entries.map(([key, value]) => (
        <article
          className={`metric-card ${typeof value === 'string' && value.length > 80 ? 'metric-card-narrative' : ''}`}
          key={key}
        >
          <span>{humanizeKey(key)}</span>
          <strong>{displayScalar(key, value)}</strong>
        </article>
      ))}
    </div>
  )
}

function MetricsTable({ title, values }: { title: string; values: UnknownRecord }) {
  const rows = Object.entries(values).filter(([, value]) => isRecord(value)) as Array<
    [string, UnknownRecord]
  >
  if (!rows.length) return null
  const columns = Array.from(
    new Set(
      rows.flatMap(([, row]) =>
        Object.keys(row).filter((key) => ['string', 'number', 'boolean'].includes(typeof row[key])),
      ),
    ),
  )
  if (!columns.length) return null

  return (
    <article className="metrics-table-panel">
      <h2>{humanizeKey(title)}</h2>
      <div className="history-table-wrap">
        <table className="history-table metrics-table">
          <thead>
            <tr>
              <th scope="col">Classe</th>
              {columns.map((column) => <th scope="col" key={column}>{humanizeKey(column)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(([rowName, row]) => (
              <tr key={rowName}>
                <th scope="row">{humanizeKey(rowName)}</th>
                {columns.map((column) => {
                  const value = row[column]
                  return (
                    <td key={column}>
                      {['string', 'number', 'boolean'].includes(typeof value)
                        ? displayScalar(column, value as string | number | boolean)
                        : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  )
}

function ConfusionMatrix({ matrix, labels }: { matrix: unknown; labels?: unknown }) {
  if (!Array.isArray(matrix) || !matrix.every((row) => Array.isArray(row))) return null
  const rows = matrix as unknown[][]
  const classLabels = Array.isArray(labels) ? labels.map(String) : []

  return (
    <article className="metrics-table-panel">
      <h2>Matriz de confusão</h2>
      <p>Valores retornados pelo backend, organizados por classe real e prevista.</p>
      <div className="matrix-wrap">
        <table className="confusion-matrix">
          <caption className="sr-only">Matriz de confusão do modelo</caption>
          {classLabels.length === rows.length && (
            <thead>
              <tr>
                <th scope="col">Real ↓ / Prevista →</th>
                {classLabels.map((label) => <th scope="col" key={label}>{humanizeKey(label)}</th>)}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {classLabels.length === rows.length && (
                  <th scope="row">{humanizeKey(classLabels[rowIndex])}</th>
                )}
                {row.map((value, columnIndex) => (
                  <td key={columnIndex}>{String(value)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  )
}

export function ModelMetrics() {
  const [metrics, setMetrics] = useState<MetricsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    getModelMetrics()
      .then((payload) => {
        if (active) setMetrics(payload)
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Não foi possível carregar as métricas.',
          )
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [reloadKey])

  const primaryMetrics = useMemo(() => {
    if (!metrics) return {}
    const nested = isRecord(metrics.metrics) ? metrics.metrics : {}
    return { ...metrics, ...nested }
  }, [metrics])

  const nestedTables = Object.entries(primaryMetrics).filter(
    ([key, value]) => key !== 'metrics' && isRecord(value),
  ) as Array<[string, UnknownRecord]>
  const evaluations = isRecord(primaryMetrics.evaluations)
    ? primaryMetrics.evaluations
    : {}
  const selectedModel =
    typeof primaryMetrics.selected_model === 'string' ? primaryMetrics.selected_model : ''
  const selectedEvaluation = isRecord(evaluations[selectedModel])
    ? evaluations[selectedModel]
    : {}
  const confusionMatrix =
    primaryMetrics.confusion_matrix ?? selectedEvaluation.confusion_matrix
  const confusionMatrixLabels =
    primaryMetrics.confusion_matrix_label_order ??
    selectedEvaluation.confusion_matrix_label_order

  return (
    <section className="workspace-section" aria-labelledby="metrics-title">
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">Transparência do modelo</span>
          <h1 id="metrics-title">Desempenho do modelo</h1>
          <p>Métricas publicadas pelo serviço para o classificador em uso.</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => setReloadKey((value) => value + 1)}
          disabled={loading}
        >
          <span aria-hidden="true">↻</span>
          Atualizar
        </button>
      </div>

      {loading && (
        <div className="state-card" role="status">
          <span className="large-spinner" aria-hidden="true" />
          <strong>Carregando métricas…</strong>
          <p>Consultando o desempenho publicado pelo backend.</p>
        </div>
      )}

      {!loading && error && (
        <div className="state-card error-state" role="alert">
          <span className="state-symbol" aria-hidden="true">!</span>
          <strong>Não foi possível carregar as métricas</strong>
          <p>{error}</p>
          <button className="secondary-button" onClick={() => setReloadKey((value) => value + 1)}>
            Tentar novamente
          </button>
        </div>
      )}

      {!loading && !error && metrics && Object.keys(metrics).length === 0 && (
        <div className="state-card">
          <span className="state-symbol empty-symbol" aria-hidden="true">○</span>
          <strong>Métricas não informadas</strong>
          <p>O serviço respondeu sem dados de desempenho.</p>
        </div>
      )}

      {!loading && !error && metrics && Object.keys(metrics).length > 0 && (
        <div className="metrics-content">
          <ScalarCards values={primaryMetrics} />
          {nestedTables.map(([key, value]) => (
            <MetricsTable title={key} values={value} key={key} />
          ))}
          <ConfusionMatrix matrix={confusionMatrix} labels={confusionMatrixLabels} />
        </div>
      )}
    </section>
  )
}
