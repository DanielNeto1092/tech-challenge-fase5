import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
VALID_PAYLOAD = {
    "age": 35,
    "systolic_bp": 140,
    "diastolic_bp": 90,
    "blood_sugar": 13.0,
    "body_temperature": 98.0,
    "heart_rate": 70,
    "question": "O que os protocolos informam sobre a pressão arterial?",
}


def _settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "guardia_test.db",
        model_artifact_path=BACKEND_DIR / "artifacts" / "maternal_risk_model_v1.0.0.joblib",
        model_metrics_path=BACKEND_DIR / "artifacts" / "training_report_v1.0.0.json",
        knowledge_base_path=BACKEND_DIR / "data" / "knowledge_base",
        openai_api_key=None,
    )


def _client_for(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def test_complete_journey_without_paid_llm_call(tmp_path) -> None:
    async def scenario() -> None:
        app = create_app(_settings(tmp_path))
        async with app.router.lifespan_context(app), _client_for(app) as client:
            health = await client.get("/health")
            created = await client.post("/api/v1/analyses", json=VALID_PAYLOAD)

            assert health.status_code == 200
            assert health.json() == {
                "status": "ok",
                "model_loaded": True,
                "knowledge_sections": 16,
                "llm_configured": False,
            }
            assert created.status_code == 201
            result = created.json()
            assert result["risk_level"] in {"low", "mid", "high"}
            assert sum(result["probabilities"].values()) == pytest.approx(1.0)
            assert len(result["feature_contributions"]) == 6
            assert result["explanation_method"] == (
                "exact_random_forest_path_probability_decomposition"
            )
            assert result["reconstruction_error"] < 1e-12
            assert len(result["sources"]) == 4
            assert result["input_data"] == VALID_PAYLOAD
            assert result["llm_used"] is False
            assert "não foi executada" in result["explanation"]
            assert "não constitui diagnóstico" in result["disclaimer"]

            fetched = await client.get(f"/api/v1/analyses/{result['id']}")
            history = await client.get("/api/v1/analyses?limit=20")
            metrics = await client.get("/api/v1/model/metrics")

            assert fetched.status_code == 200
            assert fetched.json() == result
            assert history.status_code == 200
            assert history.json()["total"] == 1
            assert history.json()["items"][0]["id"] == result["id"]
            assert metrics.status_code == 200
            assert metrics.json()["selected_model"] == "random_forest"
            assert len(metrics.json()["candidate_models"]) == 2

    asyncio.run(scenario())


def test_api_rejects_values_outside_the_model_domain(tmp_path) -> None:
    invalid = {**VALID_PAYLOAD, "body_temperature": 37.0}

    async def scenario() -> None:
        app = create_app(_settings(tmp_path))
        async with app.router.lifespan_context(app), _client_for(app) as client:
            response = await client.post("/api/v1/analyses", json=invalid)
            assert response.status_code == 422

    asyncio.run(scenario())


def test_unknown_analysis_returns_404(tmp_path) -> None:
    async def scenario() -> None:
        app = create_app(_settings(tmp_path))
        async with app.router.lifespan_context(app), _client_for(app) as client:
            response = await client.get("/api/v1/analyses/unknown")
            assert response.status_code == 404
            assert response.json()["detail"] == "Análise não encontrada."

    asyncio.run(scenario())
