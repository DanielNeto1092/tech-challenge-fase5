import type { Analysis, RagSource } from '../types'
import { ClinicalData } from './ClinicalData'
import {
  analysisModelLabel,
  DEFAULT_DISCLAIMER,
  explanationMethodLabel,
  formatDate,
  formatPercent,
  getRiskLabel,
  getRiskTone,
  normalizeContributions,
  toPercent,
} from '../utils'

interface AnalysisResultProps {
  analysis: Analysis
}

function SourceCard({ source, index }: { source: RagSource | string; index: number }) {
  if (typeof source === 'string') {
    return (
      <li className="source-card">
        <span className="source-index">{index + 1}</span>
        <div>
          <strong>{source}</strong>
        </div>
      </li>
    )
  }

  const title = source.title ?? source.name ?? source.source ?? `Fonte ${index + 1}`
  const excerpt = source.excerpt ?? source.content

  return (
    <li className="source-card">
      <span className="source-index">{index + 1}</span>
      <div>
        {source.url ? (
          <a href={source.url} target="_blank" rel="noreferrer">
            {title}
            <span className="sr-only"> (abre em nova aba)</span>
          </a>
        ) : (
          <strong>{title}</strong>
        )}
        {source.page != null && <span className="source-page">Página {source.page}</span>}
        {source.reference && <span className="source-reference">{source.reference}</span>}
        {excerpt && <p>{excerpt}</p>}
      </div>
    </li>
  )
}

export function AnalysisResult({ analysis }: AnalysisResultProps) {
  const riskTone = getRiskTone(analysis.risk_level)
  const probabilities = Object.entries(analysis.probabilities ?? {})
  const contributions = normalizeContributions(analysis.feature_contributions)
  const numericContributions = contributions
    .map((item) => Math.abs(item.contribution ?? 0))
    .filter((value) => value > 0)
  const maximumContribution = Math.max(...numericContributions, 0)

  return (
    <section className="result-section" aria-labelledby="result-title" aria-live="polite">
      <div className="result-heading">
        <div>
          <span className="section-kicker">Análise concluída</span>
          <h2 id="result-title">Resultado da triagem</h2>
        </div>
        <div className="analysis-identity">
          <span>ID {analysis.id}</span>
          <time dateTime={analysis.created_at}>{formatDate(analysis.created_at)}</time>
        </div>
      </div>

      <div className="result-overview">
        <article className={`risk-summary risk-${riskTone}`}>
          <span className="risk-caption">Classificação estimada</span>
          <div className="risk-value-row">
            <span className="risk-dot" aria-hidden="true" />
            <strong>{getRiskLabel(analysis.risk_level, analysis.risk_label)}</strong>
          </div>
          <p>{analysisModelLabel(analysis.model)}</p>
        </article>

        <article className="probability-card">
          <h3>Probabilidades por classe</h3>
          {probabilities.length ? (
            <ul className="probability-list">
              {probabilities.map(([label, value]) => (
                <li key={label}>
                  <div>
                    <span>{getRiskLabel(label)}</span>
                    <strong>{formatPercent(value)}</strong>
                  </div>
                  <div
                    className="probability-track"
                    role="progressbar"
                    aria-label={`Probabilidade de ${getRiskLabel(label)}`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(toPercent(value))}
                  >
                    <span style={{ width: `${toPercent(value)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-inline">Probabilidades não informadas pelo modelo.</p>
          )}
        </article>
      </div>

      <div className="result-details-grid">
        <article className="detail-card explanation-card">
          <div className="detail-card-heading">
            <span className="detail-icon ai-icon" aria-hidden="true">AI</span>
            <div>
              <span className="section-kicker">Interpretação assistida</span>
              <h3>Explicação da IA</h3>
            </div>
          </div>
          {analysis.llm_used && analysis.explanation ? (
            <p className="explanation-text">{analysis.explanation}</p>
          ) : (
            <div className="llm-unavailable" role="status">
              <strong>Explicação por LLM não executada</strong>
              <p>{analysis.explanation || (
                'A causa não foi informada pelo serviço. A classificação permanece disponível, '
                + 'e as fontes recuperadas pelo RAG podem ser consultadas abaixo.'
              )}</p>
            </div>
          )}
        </article>

        <article className="detail-card contribution-card">
          <div className="detail-card-heading">
            <span className="detail-icon chart-icon" aria-hidden="true">↗</span>
            <div>
              <span className="section-kicker">Explicabilidade</span>
              <h3>Contribuição dos fatores</h3>
            </div>
          </div>
          {contributions.length ? (
            <ul className="contribution-list">
              {contributions.map((item) => {
                const width =
                  item.contribution != null && maximumContribution
                    ? (Math.abs(item.contribution) / maximumContribution) * 100
                    : 0
                return (
                  <li key={item.key}>
                    <div className="contribution-label">
                      <span>{item.label}</span>
                      <strong>
                        {item.impactText ??
                          (item.contribution != null
                            ? item.contribution.toLocaleString('pt-BR', {
                                maximumFractionDigits: 4,
                                signDisplay: 'exceptZero',
                              })
                            : 'Informativo')}
                        {item.direction && (
                          <span className="direction-label">
                            {item.direction === 'increases'
                              ? ' aumenta'
                              : item.direction === 'decreases'
                                ? ' reduz'
                                : item.direction === 'neutral'
                                  ? ' neutro'
                                  : ` ${item.direction}`}
                          </span>
                        )}
                      </strong>
                    </div>
                    {item.contribution != null && (
                      <div className="contribution-track" aria-hidden="true">
                        <span style={{ width: `${width}%` }} />
                      </div>
                    )}
                    {item.value != null && (
                      <small>Valor analisado: {String(item.value)}</small>
                    )}
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="empty-inline">Contribuições não informadas pelo modelo.</p>
          )}
          <p className="explanation-metadata">
            Método: {explanationMethodLabel(analysis.explanation_method)} · erro de reconstrução:{' '}
            {analysis.reconstruction_error.toExponential(2)}
          </p>
        </article>
      </div>

      {analysis.input_data && (
        <article className="used-data-panel">
          <div className="detail-card-heading">
            <span className="detail-icon data-icon" aria-hidden="true">#</span>
            <div>
              <span className="section-kicker">Rastreabilidade</span>
              <h3>Dados utilizados</h3>
            </div>
          </div>
          <ClinicalData data={analysis.input_data} />
        </article>
      )}

      <article className="sources-panel">
        <div className="detail-card-heading">
          <span className="detail-icon document-icon" aria-hidden="true">≡</span>
          <div>
            <span className="section-kicker">Base de conhecimento</span>
            <h3>Fontes consultadas</h3>
          </div>
        </div>
        {analysis.sources?.length ? (
          <ol className="sources-list">
            {analysis.sources.map((source, index) => (
              <SourceCard
                key={`${typeof source === 'string' ? source : source.url ?? source.title}-${index}`}
                source={source}
                index={index}
              />
            ))}
          </ol>
        ) : (
          <p className="empty-inline">
            {analysis.llm_used
              ? 'Nenhuma fonte foi retornada para esta explicação.'
              : 'Nenhuma fonte foi recuperada pelo RAG para esta análise.'}
          </p>
        )}
      </article>

      <div className="result-disclaimer" role="note">
        <span aria-hidden="true">i</span>
        <p>{analysis.disclaimer || DEFAULT_DISCLAIMER}</p>
      </div>
    </section>
  )
}
