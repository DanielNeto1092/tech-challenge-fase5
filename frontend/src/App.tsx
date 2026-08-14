import { useState } from 'react'
import { AnalysisForm } from './components/AnalysisForm'
import { AnalysisResult } from './components/AnalysisResult'
import { HistoryView } from './components/HistoryView'
import { ModelMetrics } from './components/ModelMetrics'
import type { Analysis } from './types'
import './styles.css'

type Page = 'analysis' | 'history' | 'metrics'

const navigation: Array<{ id: Page; label: string }> = [
  { id: 'analysis', label: 'Nova análise' },
  { id: 'history', label: 'Histórico' },
  { id: 'metrics', label: 'Desempenho' },
]

export default function App() {
  const [page, setPage] = useState<Page>('analysis')
  const [latestAnalysis, setLatestAnalysis] = useState<Analysis | null>(null)

  function navigate(nextPage: Page) {
    setPage(nextPage)
    window.scrollTo?.({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Pular para o conteúdo</a>
      <header className="site-header">
        <div className="header-inner">
          <button className="brand" type="button" onClick={() => navigate('analysis')}>
            <span className="brand-mark" aria-hidden="true">
              <span>G</span>
            </span>
            <span className="brand-copy">
              <strong>Guardiã AI</strong>
              <small>Saúde materna</small>
            </span>
          </button>

          <nav aria-label="Navegação principal">
            {navigation.map((item) => (
              <button
                type="button"
                key={item.id}
                className={page === item.id ? 'active' : ''}
                aria-current={page === item.id ? 'page' : undefined}
                onClick={() => navigate(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <span className="support-badge">
            <span aria-hidden="true" />
            Apoio clínico
          </span>
        </div>
      </header>

      <main id="main-content">
        {page === 'analysis' && (
          <>
            <section className="hero" aria-labelledby="hero-title">
              <div className="hero-copy">
                <span className="hero-kicker"><span aria-hidden="true" /> Triagem responsável</span>
                <h1 id="hero-title">Clareza para apoiar o cuidado materno.</h1>
                <p>
                  Analise sinais clínicos, compreenda os fatores relevantes e consulte
                  informações de protocolos com rastreabilidade.
                </p>
              </div>
              <div className="hero-principles" aria-label="Princípios da análise">
                <div><strong>6</strong><span>sinais clínicos</span></div>
                <div><strong>ML</strong><span>classificação de risco</span></div>
                <div><strong>RAG</strong><span>fontes consultadas</span></div>
              </div>
            </section>

            <div className="analysis-layout">
              <AnalysisForm onCreated={setLatestAnalysis} />
              <aside className="process-card" aria-labelledby="process-title">
                <span className="section-kicker">Como funciona</span>
                <h2 id="process-title">Da informação à interpretação</h2>
                <ol>
                  <li>
                    <span>01</span>
                    <div><strong>Dados clínicos</strong><p>Seis sinais são enviados para análise.</p></div>
                  </li>
                  <li>
                    <span>02</span>
                    <div><strong>Classificação</strong><p>O modelo estima o nível e as probabilidades.</p></div>
                  </li>
                  <li>
                    <span>03</span>
                    <div><strong>Explicação</strong><p>A IA contextualiza o resultado com fontes.</p></div>
                  </li>
                </ol>
                <div className="privacy-note">
                  <span aria-hidden="true">✓</span>
                  <p>O resultado identifica o modelo e o momento da análise.</p>
                </div>
              </aside>
            </div>

            {latestAnalysis && <AnalysisResult analysis={latestAnalysis} />}
          </>
        )}
        {page === 'history' && <HistoryView />}
        {page === 'metrics' && <ModelMetrics />}
      </main>

      <footer>
        <div>
          <span className="footer-brand">Guardiã AI</span>
          <p>Ferramenta de apoio à triagem de risco materno.</p>
        </div>
        <p>Não substitui avaliação ou diagnóstico profissional.</p>
      </footer>
    </div>
  )
}
