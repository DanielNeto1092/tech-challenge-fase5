from typing import Final

RISK_LABELS: Final[dict[str, str]] = {
    "low": "Baixo",
    "mid": "Médio",
    "high": "Alto",
}

FEATURE_LABELS: Final[dict[str, str]] = {
    "age": "Idade",
    "systolic_bp": "Pressão arterial sistólica",
    "diastolic_bp": "Pressão arterial diastólica",
    "blood_sugar": "Glicemia",
    "body_temperature": "Temperatura corporal",
    "heart_rate": "Frequência cardíaca",
}

FEATURE_UNITS: Final[dict[str, str]] = {
    "age": "anos",
    "systolic_bp": "mmHg",
    "diastolic_bp": "mmHg",
    "blood_sugar": "mmol/L",
    "body_temperature": "°F",
    "heart_rate": "bpm",
}

SUPPORT_DISCLAIMER: Final[str] = (
    "Este resultado é um apoio à triagem profissional, não constitui diagnóstico, "
    "prescrição ou decisão clínica automática. A decisão final e a avaliação do contexto "
    "completo permanecem sob responsabilidade do profissional de saúde."
)
