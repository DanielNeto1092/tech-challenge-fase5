from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.schemas import AnalysisListResponse, AnalysisRequest, AnalysisResponse, AnalysisSummary


class AnalysisNotFoundError(LookupError):
    pass


class AnalysisRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_label TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    llm_used INTEGER NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC)"
            )

    def save(self, request: AnalysisRequest, response: AnalysisResponse) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO analyses (
                    id, created_at, risk_level, risk_label, model_name, model_version,
                    llm_used, request_json, response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.id,
                    response.created_at.isoformat(),
                    response.risk_level,
                    response.risk_label,
                    response.model.name,
                    response.model.version,
                    int(response.llm_used),
                    request.model_dump_json(),
                    response.model_dump_json(),
                ),
            )

    def get(self, analysis_id: str) -> AnalysisResponse:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT response_json FROM analyses WHERE id = ?", (analysis_id,)
            ).fetchone()
        if row is None:
            raise AnalysisNotFoundError(analysis_id)
        return AnalysisResponse.model_validate(json.loads(row["response_json"]))

    def list(self, limit: int) -> AnalysisListResponse:
        with self._connection() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0])
            rows = connection.execute(
                """
                SELECT id, created_at, risk_level, risk_label, model_name, model_version, llm_used
                FROM analyses
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        items = [
            AnalysisSummary.model_validate(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "risk_level": row["risk_level"],
                    "risk_label": row["risk_label"],
                    "model": {
                        "name": row["model_name"],
                        "version": row["model_version"],
                    },
                    "llm_used": bool(row["llm_used"]),
                }
            )
            for row in rows
        ]
        return AnalysisListResponse(items=items, total=total)
