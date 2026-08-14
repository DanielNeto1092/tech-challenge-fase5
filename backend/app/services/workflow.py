from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableLambda

from app.core.config import Settings
from app.core.constants import FEATURE_LABELS, FEATURE_UNITS, RISK_LABELS, SUPPORT_DISCLAIMER
from app.ml import MaternalRiskPredictor
from app.rag.explainer import ExplanationResult, ProtocolExplainer
from app.rag.retriever import ProtocolRetriever
from app.schemas import (
    AnalysisRequest,
    FeatureContribution,
    ModelInfo,
    ProbabilitySet,
)

logger = logging.getLogger(__name__)


class MaternalAnalysisWorkflow:
    """Fluxo principal ML → recuperação → explicação, orquestrado por LangChain."""

    def __init__(
        self,
        *,
        predictor: MaternalRiskPredictor,
        retriever: ProtocolRetriever,
        explainer: ProtocolExplainer,
        settings: Settings,
    ) -> None:
        self._predictor = predictor
        self._retriever = retriever
        self._explainer = explainer
        self._settings = settings
        self._chain = (
            RunnableLambda(self._run_prediction).with_config(run_name="maternal_ml_prediction")
            | RunnableLambda(self._retrieve_protocols).with_config(run_name="protocol_retrieval")
            | RunnableLambda(self._generate_explanation).with_config(
                run_name="responsible_llm_explanation"
            )
        ).with_config(run_name="guardia_ai_maternal_analysis")

    def invoke(self, request: AnalysisRequest) -> dict[str, Any]:
        return self._chain.invoke({"request": request})

    def _run_prediction(self, state: dict[str, Any]) -> dict[str, Any]:
        request: AnalysisRequest = state["request"]
        features = request.clinical_features()
        prediction = self._predictor.predict(features)
        raw_explanation = self._predictor.explain(
            features, target_class=int(prediction["risk_level"])
        )

        contributions = []
        for feature, signed_contribution in raw_explanation["feature_contributions"].items():
            contribution = float(signed_contribution)
            if contribution > 1e-12:
                direction = "increases"
            elif contribution < -1e-12:
                direction = "decreases"
            else:
                direction = "neutral"
            contributions.append(
                FeatureContribution(
                    feature=feature,
                    label=FEATURE_LABELS[feature],
                    value=float(raw_explanation["feature_values"][feature]),
                    importance=abs(contribution),
                    direction=direction,
                )
            )
        contributions.sort(key=lambda item: (-item.importance, item.feature))
        return {
            **state,
            "prediction": prediction,
            "feature_contributions": contributions,
            "explanation_method": raw_explanation["method"],
            "reconstruction_error": float(raw_explanation["reconstruction_error"]),
        }

    def _retrieve_protocols(self, state: dict[str, Any]) -> dict[str, Any]:
        request: AnalysisRequest = state["request"]
        prediction: dict[str, Any] = state["prediction"]
        top_factors = ", ".join(
            contribution.label for contribution in state["feature_contributions"][:3]
        )
        query = " ".join(
            part
            for part in (
                request.question,
                f"risco materno {RISK_LABELS[prediction['risk_label']]} gestação",
                top_factors,
            )
            if part
        )
        return {
            **state,
            "sources": self._retriever.retrieve(query, top_k=self._settings.rag_top_k),
        }

    def _generate_explanation(self, state: dict[str, Any]) -> dict[str, Any]:
        request: AnalysisRequest = state["request"]
        prediction: dict[str, Any] = state["prediction"]
        probabilities = prediction["probabilities"]
        prediction_text = (
            f"Classificação estatística: risco {RISK_LABELS[prediction['risk_label']]}. "
            f"Probabilidades do modelo: baixo={probabilities['low']:.1%}, "
            f"médio={probabilities['mid']:.1%}, alto={probabilities['high']:.1%}."
        )
        factors_text = "\n".join(
            f"- {item.label}: {self._format_measurement(item)}; "
            f"contribuição {item.importance:.4f} "
            f"({item.direction})"
            for item in state["feature_contributions"]
        )
        try:
            llm_result = self._explainer.explain(
                prediction=prediction_text,
                factors=factors_text,
                question=request.question,
                sources=state["sources"],
            )
        except Exception:
            if not self._settings.allow_llm_fallback:
                raise
            logger.exception("Falha na explicação LLM; retornando fallback seguro.")
            llm_result = ExplanationResult(
                text=(
                    "A classificação de apoio e a recuperação documental foram concluídas, "
                    "mas a explicação por LLM está temporariamente indisponível. Consulte as "
                    "fontes recuperadas e mantenha a decisão com o profissional responsável."
                ),
                llm_used=False,
                llm_model=None,
            )

        metadata = self._predictor.metadata
        return {
            "risk_level": prediction["risk_label"],
            "risk_label": RISK_LABELS[prediction["risk_label"]],
            "probabilities": ProbabilitySet.model_validate(probabilities),
            "model": ModelInfo(
                name=str(metadata["selected_model"]),
                version=str(prediction["model_version"]),
            ),
            "feature_contributions": state["feature_contributions"],
            "explanation_method": state["explanation_method"],
            "reconstruction_error": state["reconstruction_error"],
            "explanation": llm_result.text,
            "llm_used": llm_result.llm_used,
            "llm_model": llm_result.llm_model,
            "sources": state["sources"],
            "disclaimer": SUPPORT_DISCLAIMER,
        }

    @staticmethod
    def _format_measurement(item: FeatureContribution) -> str:
        if item.feature == "body_temperature":
            celsius = (item.value - 32) * 5 / 9
            return f"{item.value:g} °F ({celsius:.1f} °C)"
        return f"{item.value:g} {FEATURE_UNITS[item.feature]}"
