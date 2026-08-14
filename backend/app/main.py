from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.audit.repository import AnalysisRepository
from app.core.config import Settings, get_settings
from app.ml import MaternalRiskPredictor
from app.rag.explainer import ProtocolExplainer
from app.rag.retriever import ProtocolRetriever
from app.schemas import HealthResponse
from app.services.analysis import AnalysisService
from app.services.workflow import MaternalAnalysisWorkflow


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repository = AnalysisRepository(resolved_settings.resolved_database_path)
        repository.initialize()
        predictor = MaternalRiskPredictor.load(resolved_settings.resolved_model_artifact_path)
        retriever = ProtocolRetriever(resolved_settings.resolved_knowledge_base_path)
        explainer = ProtocolExplainer(resolved_settings)
        workflow = MaternalAnalysisWorkflow(
            predictor=predictor,
            retriever=retriever,
            explainer=explainer,
            settings=resolved_settings,
        )
        app.state.analysis_service = AnalysisService(
            workflow=workflow,
            repository=repository,
            metrics_path=resolved_settings.resolved_model_metrics_path,
        )
        app.state.predictor = predictor
        app.state.retriever = retriever
        app.state.explainer = explainer
        yield

    app = FastAPI(
        title=resolved_settings.app_name,
        version="1.0.0",
        description=(
            "Sistema de apoio profissional à triagem de risco materno. "
            "Não realiza diagnóstico nem decisão clínica automática."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router, prefix=resolved_settings.api_prefix)

    @app.get("/health", response_model=HealthResponse, tags=["infraestrutura"])
    async def health(request: Request) -> HealthResponse:
        return HealthResponse(
            status="ok",
            model_loaded=hasattr(request.app.state, "predictor"),
            knowledge_sections=request.app.state.retriever.section_count,
            llm_configured=request.app.state.explainer.is_configured,
        )

    return app


app = create_app()
