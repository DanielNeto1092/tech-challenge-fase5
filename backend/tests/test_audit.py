from datetime import UTC, datetime

import pytest

from app.audit.repository import AnalysisNotFoundError, AnalysisRepository
from app.schemas import AnalysisRequest, AnalysisResponse


def _request() -> AnalysisRequest:
    return AnalysisRequest(
        age=25,
        systolic_bp=130,
        diastolic_bp=80,
        blood_sugar=15,
        body_temperature=98,
        heart_rate=86,
        question="Como interpretar os fatores?",
    )


def _response(request: AnalysisRequest) -> AnalysisResponse:
    return AnalysisResponse.model_validate(
        {
            "id": "analysis-1",
            "created_at": datetime(2026, 8, 14, tzinfo=UTC),
            "input_data": request,
            "risk_level": "high",
            "risk_label": "Alto",
            "probabilities": {"low": 0.05, "mid": 0.15, "high": 0.8},
            "model": {"name": "random_forest", "version": "1.0.0"},
            "feature_contributions": [],
            "explanation_method": "exact_random_forest_path_probability_decomposition",
            "reconstruction_error": 0.0,
            "explanation": "Explicação de apoio.",
            "llm_used": False,
            "sources": [],
            "disclaimer": "Apoio profissional, não diagnóstico.",
        }
    )


def test_repository_persists_inputs_and_results_for_audit(tmp_path) -> None:
    repository = AnalysisRepository(tmp_path / "audit.db")
    repository.initialize()
    request = _request()
    response = _response(request)

    repository.save(request, response)

    stored = repository.get(response.id)
    history = repository.list(limit=20)
    assert stored == response
    assert stored.input_data == request
    assert history.total == 1
    assert history.items[0].id == response.id


def test_repository_rejects_unknown_analysis(tmp_path) -> None:
    repository = AnalysisRepository(tmp_path / "audit.db")
    repository.initialize()

    with pytest.raises(AnalysisNotFoundError):
        repository.get("missing")
