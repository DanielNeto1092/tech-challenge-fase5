import { Fragment, useEffect, useState } from 'react'
import { getAnalysis, getHistory } from '../api'
import type { Analysis, AnalysisSummary } from '../types'
import { formatDate, getRiskLabel, getRiskTone } from '../utils'
import { ClinicalData } from './ClinicalData'

export function HistoryView() {
  const [items, setItems] = useState<AnalysisSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, Analysis>>({})
  const [detailLoading, setDetailLoading] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    getHistory(20)
      .then((analyses) => {
        if (active) setItems(analyses)
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Não foi possível carregar o histórico.',
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

  async function toggleDetails(item: AnalysisSummary) {
    if (expandedId === item.id) {
      setExpandedId(null)
      return
    }

    setExpandedId(item.id)
    setDetailError(null)
    if (item.input_data || details[item.id]) return

    setDetailLoading(item.id)
    try {
      const analysis = await getAnalysis(item.id)
      setDetails((current) => ({ ...current, [item.id]: analysis }))
    } catch (requestError) {
      setDetailError(
        requestError instanceof Error
          ? requestError.message
          : 'Não foi possível carregar os dados utilizados.',
      )
    } finally {
      setDetailLoading(null)
    }
  }

  return (
    <section className="workspace-section" aria-labelledby="history-title">
      <div className="workspace-heading">
        <div>
          <span className="section-kicker">Registros recentes</span>
          <h1 id="history-title">Histórico de análises</h1>
          <p>As 20 triagens mais recentes registradas pelo serviço.</p>
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
          <strong>Carregando histórico…</strong>
          <p>Consultando as análises registradas.</p>
        </div>
      )}

      {!loading && error && (
        <div className="state-card error-state" role="alert">
          <span className="state-symbol" aria-hidden="true">!</span>
          <strong>Não foi possível carregar o histórico</strong>
          <p>{error}</p>
          <button className="secondary-button" onClick={() => setReloadKey((value) => value + 1)}>
            Tentar novamente
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="state-card">
          <span className="state-symbol empty-symbol" aria-hidden="true">○</span>
          <strong>Nenhuma análise registrada</strong>
          <p>As triagens concluídas aparecerão aqui.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="history-table-wrap">
          <table className="history-table">
            <caption className="sr-only">Últimas análises de risco materno</caption>
            <thead>
              <tr>
                <th scope="col">Data e hora</th>
                <th scope="col">Identificador</th>
                <th scope="col">Classificação</th>
                <th scope="col">Explicação IA</th>
                <th scope="col">Dados utilizados</th>
              </tr>
            </thead>
            <tbody>
              {items.map((analysis) => {
                const tone = getRiskTone(analysis.risk_level)
                const inputData = analysis.input_data ?? details[analysis.id]?.input_data
                const isExpanded = expandedId === analysis.id
                return (
                  <Fragment key={analysis.id}>
                    <tr>
                      <td>
                        <time dateTime={analysis.created_at}>{formatDate(analysis.created_at)}</time>
                      </td>
                      <td><code>{analysis.id}</code></td>
                      <td>
                        <span className={`table-risk risk-${tone}`}>
                          <span aria-hidden="true" />
                          {getRiskLabel(analysis.risk_level, analysis.risk_label)}
                        </span>
                      </td>
                      <td>
                        <span className={`llm-status ${analysis.llm_used ? 'available' : ''}`}>
                          {analysis.llm_used ? 'Disponível' : 'Indisponível'}
                        </span>
                      </td>
                      <td>
                        <button
                          className="history-data-button"
                          type="button"
                          aria-expanded={isExpanded}
                          onClick={() => void toggleDetails(analysis)}
                          disabled={detailLoading === analysis.id}
                        >
                          {detailLoading === analysis.id
                            ? 'Carregando…'
                            : isExpanded
                              ? 'Ocultar dados'
                              : 'Ver dados utilizados'}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="history-expanded-row">
                        <td colSpan={5}>
                          <div className="history-expanded-content">
                            <strong>Dados utilizados</strong>
                            {detailLoading === analysis.id && (
                              <p role="status">Carregando dados da análise…</p>
                            )}
                            {!detailLoading && inputData && (
                              <ClinicalData data={inputData} compact />
                            )}
                            {!detailLoading && detailError && (
                              <p className="history-detail-error" role="alert">{detailError}</p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
