import type { AnalysisRequest } from '../types'

interface ClinicalDataProps {
  data: AnalysisRequest
  compact?: boolean
}

const clinicalFields: Array<{
  key: Exclude<keyof AnalysisRequest, 'question'>
  label: string
  unit: string
}> = [
  { key: 'age', label: 'Idade', unit: 'anos' },
  { key: 'systolic_bp', label: 'Pressão sistólica', unit: 'mmHg' },
  { key: 'diastolic_bp', label: 'Pressão diastólica', unit: 'mmHg' },
  { key: 'blood_sugar', label: 'Glicemia', unit: 'mmol/L' },
  { key: 'body_temperature', label: 'Temperatura corporal', unit: '°F' },
  { key: 'heart_rate', label: 'Frequência cardíaca', unit: 'bpm' },
]

export function ClinicalData({ data, compact = false }: ClinicalDataProps) {
  const availableFields = clinicalFields.filter((field) => data[field.key] != null)

  return (
    <div className={`clinical-data ${compact ? 'clinical-data-compact' : ''}`}>
      <dl>
        {availableFields.map((field) => (
          <div key={field.key}>
            <dt>{field.label}</dt>
            <dd>{data[field.key]} <span>{field.unit}</span></dd>
          </div>
        ))}
      </dl>
      {data.question && (
        <div className="used-question">
          <strong>Pergunta enviada</strong>
          <p>{data.question}</p>
        </div>
      )}
    </div>
  )
}
