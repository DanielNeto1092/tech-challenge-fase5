from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RiskLevel = Literal["low", "mid", "high"]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int = Field(ge=10, le=70, description="Idade em anos; domínio observado no dataset.")
    systolic_bp: int = Field(
        ge=70, le=160, description="Pressão sistólica em mmHg; domínio do dataset."
    )
    diastolic_bp: int = Field(
        ge=49, le=100, description="Pressão diastólica em mmHg; domínio do dataset."
    )
    blood_sugar: float = Field(ge=6, le=19, description="Glicemia em mmol/L; domínio do dataset.")
    body_temperature: float = Field(
        ge=98, le=103, description="Temperatura corporal em °F; domínio do dataset."
    )
    heart_rate: int = Field(
        ge=7, le=90, description="Frequência cardíaca em bpm; domínio bruto do dataset."
    )
    question: str | None = Field(
        default=None,
        max_length=1_000,
        description=(
            "Pergunta opcional do profissional para consulta aos protocolos; não deve conter "
            "dados que identifiquem a pessoa atendida."
        ),
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    def clinical_features(self) -> dict[str, int | float]:
        return self.model_dump(exclude={"question"})


class ProbabilitySet(BaseModel):
    low: float = Field(ge=0, le=1)
    mid: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)


class FeatureContribution(BaseModel):
    feature: str
    label: str
    value: float
    importance: float
    direction: Literal["increases", "decreases", "neutral"]


class ProtocolSource(BaseModel):
    source_id: str
    title: str
    url: str
    reference: str
    excerpt: str
    relevance_score: float = Field(ge=0, le=1)


class ModelInfo(BaseModel):
    name: str
    version: str


class AnalysisResponse(BaseModel):
    id: str
    created_at: datetime
    input_data: AnalysisRequest
    risk_level: RiskLevel
    risk_label: str
    probabilities: ProbabilitySet
    model: ModelInfo
    feature_contributions: list[FeatureContribution]
    explanation_method: str
    reconstruction_error: float = Field(ge=0)
    explanation: str
    llm_used: bool
    llm_model: str | None = None
    sources: list[ProtocolSource]
    disclaimer: str


class AnalysisSummary(BaseModel):
    id: str
    created_at: datetime
    risk_level: RiskLevel
    risk_label: str
    model: ModelInfo
    llm_used: bool


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    total: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    knowledge_sections: int
    llm_configured: bool
