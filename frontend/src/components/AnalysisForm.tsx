import { type FormEvent, useState } from 'react'
import { createAnalysis } from '../api'
import type { Analysis, AnalysisRequest } from '../types'
import { DEFAULT_DISCLAIMER } from '../utils'

interface FormValues {
  age: string
  systolic_bp: string
  diastolic_bp: string
  blood_sugar: string
  body_temperature: string
  heart_rate: string
  question: string
}

interface AnalysisFormProps {
  onCreated: (analysis: Analysis) => void
}

const initialValues: FormValues = {
  age: '',
  systolic_bp: '',
  diastolic_bp: '',
  blood_sugar: '',
  body_temperature: '',
  heart_rate: '',
  question: '',
}

interface FieldDefinition {
  key: Exclude<keyof FormValues, 'question'>
  label: string
  hint: string
  unit: string
  step: string
  min: number
  max: number
}

const fields: FieldDefinition[] = [
  { key: 'age', label: 'Idade', hint: 'Age', unit: 'anos', step: '1', min: 10, max: 70 },
  {
    key: 'systolic_bp',
    label: 'Pressão sistólica',
    hint: 'SystolicBP',
    unit: 'mmHg',
    step: '1',
    min: 70,
    max: 160,
  },
  {
    key: 'diastolic_bp',
    label: 'Pressão diastólica',
    hint: 'DiastolicBP',
    unit: 'mmHg',
    step: '1',
    min: 49,
    max: 100,
  },
  {
    key: 'blood_sugar',
    label: 'Glicemia',
    hint: 'BS',
    unit: 'mmol/L',
    step: '0.1',
    min: 6,
    max: 19,
  },
  {
    key: 'body_temperature',
    label: 'Temperatura corporal',
    hint: 'BodyTemp',
    unit: '°F',
    step: '0.1',
    min: 98,
    max: 103,
  },
  {
    key: 'heart_rate',
    label: 'Frequência cardíaca',
    hint: 'HeartRate',
    unit: 'bpm',
    step: '1',
    min: 7,
    max: 90,
  },
]

export function AnalysisForm({ onCreated }: AnalysisFormProps) {
  const [values, setValues] = useState<FormValues>(initialValues)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function updateValue(key: keyof FormValues, value: string) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    const payload: AnalysisRequest = {
      age: Number(values.age),
      systolic_bp: Number(values.systolic_bp),
      diastolic_bp: Number(values.diastolic_bp),
      blood_sugar: Number(values.blood_sugar),
      body_temperature: Number(values.body_temperature),
      heart_rate: Number(values.heart_rate),
      ...(values.question.trim() ? { question: values.question.trim() } : {}),
    }

    const invalidField = fields.find((field) => {
      const value = payload[field.key]
      return !Number.isFinite(value) || value < field.min || value > field.max
    })
    if (invalidField) {
      setError(
        `${invalidField.label}: informe um valor entre ${invalidField.min} e ${invalidField.max} ${invalidField.unit} (faixa suportada pelo modelo).`,
      )
      return
    }

    setLoading(true)
    try {
      const analysis = await createAnalysis(payload)
      onCreated(analysis)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Não foi possível realizar a análise.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="form-card" aria-labelledby="form-title">
      <div className="card-heading">
        <div>
          <span className="section-kicker">Dados da triagem</span>
          <h2 id="form-title">Sinais clínicos</h2>
          <p>Informe as seis variáveis utilizadas pelo modelo.</p>
        </div>
        <span className="required-note">* Campos obrigatórios</span>
      </div>

      <div className="clinical-notice" role="note" aria-label="Aviso importante">
        <span className="notice-icon" aria-hidden="true">!</span>
        <div>
          <strong>Apoio à decisão, não diagnóstico</strong>
          <p>{DEFAULT_DISCLAIMER}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <div className="fields-grid">
          {fields.map((field) => {
            const inputId = `field-${field.key}`
            const hintId = `${inputId}-hint`
            return (
              <div className="field" key={field.key}>
                <label htmlFor={inputId}>
                  {field.label} <span aria-hidden="true">*</span>
                </label>
                <div className="field-meta" id={hintId}>
                  <span>{field.hint}</span>
                  <span>Faixa suportada: {field.min}–{field.max} {field.unit}</span>
                </div>
                <div className="input-with-unit">
                  <input
                    id={inputId}
                    name={field.key}
                    type="number"
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    inputMode={field.step === '1' ? 'numeric' : 'decimal'}
                    value={values[field.key]}
                    onChange={(event) => updateValue(field.key, event.target.value)}
                    aria-describedby={hintId}
                    required
                    disabled={loading}
                  />
                  <span aria-hidden="true">{field.unit}</span>
                </div>
              </div>
            )
          })}
        </div>

        <div className="field question-field">
          <div className="question-label-row">
            <label htmlFor="field-question">Pergunta para a assistente</label>
            <span id="question-guidance">Opcional · não inclua dados identificáveis</span>
          </div>
          <textarea
            id="field-question"
            name="question"
            rows={3}
            maxLength={1000}
            placeholder="Ex.: Quais informações dos protocolos ajudam a interpretar este resultado?"
            value={values.question}
            onChange={(event) => updateValue('question', event.target.value)}
            aria-describedby="question-guidance"
            disabled={loading}
          />
          <span className="character-count" aria-live="polite">
            {values.question.length}/1000
          </span>
        </div>

        {error && (
          <div className="error-message" role="alert">
            <span aria-hidden="true">!</span>
            <p>{error}</p>
          </div>
        )}

        <div className="form-actions">
          <p>Os dados serão enviados ao modelo para classificação de risco.</p>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading && <span className="button-spinner" aria-hidden="true" />}
            {loading ? 'Analisando dados…' : 'Analisar risco materno'}
          </button>
        </div>
      </form>
    </section>
  )
}
