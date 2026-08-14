from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_analysis_service
from app.audit.repository import AnalysisNotFoundError
from app.schemas import AnalysisListResponse, AnalysisRequest, AnalysisResponse
from app.services.analysis import AnalysisService

router = APIRouter()
ServiceDependency = Annotated[AnalysisService, Depends(get_analysis_service)]


@router.post(
    "/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executa a jornada completa de análise de risco materno",
)
async def create_analysis(payload: AnalysisRequest, service: ServiceDependency) -> AnalysisResponse:
    return service.analyze(payload)


@router.get(
    "/analyses",
    response_model=AnalysisListResponse,
    summary="Lista o histórico auditável de análises",
)
async def list_analyses(
    service: ServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AnalysisListResponse:
    return service.list(limit)


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResponse,
    summary="Consulta uma análise auditada",
)
async def get_analysis(analysis_id: str, service: ServiceDependency) -> AnalysisResponse:
    try:
        return service.get(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Análise não encontrada.") from exc


@router.get(
    "/model/metrics",
    response_model=dict[str, Any],
    summary="Expõe comparação e métricas dos modelos treinados",
)
async def get_model_metrics(service: ServiceDependency) -> dict[str, Any]:
    return service.model_metrics()
