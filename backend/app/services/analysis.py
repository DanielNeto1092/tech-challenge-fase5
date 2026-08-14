from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.audit.repository import AnalysisRepository
from app.schemas import AnalysisListResponse, AnalysisRequest, AnalysisResponse
from app.services.workflow import MaternalAnalysisWorkflow


class AnalysisService:
    def __init__(
        self,
        *,
        workflow: MaternalAnalysisWorkflow,
        repository: AnalysisRepository,
        metrics_path: Path,
    ) -> None:
        self._workflow = workflow
        self._repository = repository
        self._metrics_path = metrics_path

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        result = self._workflow.invoke(request)
        response = AnalysisResponse.model_validate(
            {
                "id": str(uuid4()),
                "created_at": datetime.now(UTC),
                "input_data": request,
                **result,
            }
        )
        self._repository.save(request, response)
        return response

    def get(self, analysis_id: str) -> AnalysisResponse:
        return self._repository.get(analysis_id)

    def list(self, limit: int) -> AnalysisListResponse:
        return self._repository.list(limit)

    def model_metrics(self) -> dict:
        return json.loads(self._metrics_path.read_text(encoding="utf-8"))
