"""Validated loading and inference for the maternal-risk model artifact."""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .constants import (
    ARTIFACT_FILENAME_PREFIX,
    ARTIFACT_SCHEMA_VERSION,
    CLASS_LABELS,
    FEATURE_COLUMNS,
)
from .explainability import explain_prediction


class ArtifactNotFoundError(FileNotFoundError):
    """Raised when no trained, versioned model artifact is available."""


class InvalidArtifactError(ValueError):
    """Raised when an artifact does not satisfy the expected contract."""


def _version_key(path: Path) -> tuple[int, ...]:
    match = re.search(r"_v(\d+(?:\.\d+)*)\.joblib$", path.name)
    if not match:
        return (-1,)
    return tuple(int(part) for part in match.group(1).split("."))


def find_latest_artifact(artifact_dir: Path | None = None) -> Path:
    """Resolve an explicit environment path or the highest semantic version."""

    configured_path = os.getenv("MODEL_ARTIFACT_PATH")
    if configured_path:
        path = Path(configured_path).expanduser().resolve()
        if not path.is_file():
            raise ArtifactNotFoundError(f"MODEL_ARTIFACT_PATH does not point to a file: {path}")
        return path

    if artifact_dir is None:
        artifact_dir = Path(__file__).resolve().parents[2] / "artifacts"
    candidates = list(artifact_dir.glob(f"{ARTIFACT_FILENAME_PREFIX}*.joblib"))
    if not candidates:
        raise ArtifactNotFoundError(
            f"No versioned maternal-risk artifact found in {artifact_dir}. "
            "Run the training command documented in backend/data/README.md."
        )
    return max(candidates, key=_version_key)


def _validate_artifact(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvalidArtifactError("The artifact root must be a dictionary.")
    required = {
        "artifact_schema_version",
        "model_version",
        "feature_names",
        "class_labels",
        "estimator",
        "selected_model",
        "evaluation",
        "global_feature_importance",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise InvalidArtifactError(f"Artifact fields are missing: {missing}")
    if payload["artifact_schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise InvalidArtifactError(
            f"Unsupported artifact schema version: {payload['artifact_schema_version']!r}"
        )
    if tuple(payload["feature_names"]) != FEATURE_COLUMNS:
        raise InvalidArtifactError("Artifact feature order does not match the API contract.")
    artifact_labels = {int(key): value for key, value in payload["class_labels"].items()}
    if artifact_labels != CLASS_LABELS:
        raise InvalidArtifactError("Artifact class labels do not match the API contract.")
    return payload


def _coerce_record(features: Mapping[str, Any]) -> pd.DataFrame:
    missing = [name for name in FEATURE_COLUMNS if name not in features]
    unknown = sorted(set(features).difference(FEATURE_COLUMNS))
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unknown:
            details.append(f"unknown={unknown}")
        raise ValueError("Invalid model features: " + ", ".join(details))

    normalized: dict[str, float] = {}
    for name in FEATURE_COLUMNS:
        value = features[name]
        if isinstance(value, bool):
            raise ValueError(f"Feature {name!r} must be numeric, not boolean.")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Feature {name!r} must be numeric.") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"Feature {name!r} must be finite.")
        normalized[name] = numeric_value
    return pd.DataFrame([normalized], columns=FEATURE_COLUMNS)


class MaternalRiskPredictor:
    """Small facade around the persisted estimator and its metadata."""

    def __init__(self, artifact: dict[str, Any], artifact_path: Path | None = None):
        self._artifact = _validate_artifact(artifact)
        self.artifact_path = artifact_path

    @classmethod
    def load(cls, path: str | Path | None = None) -> MaternalRiskPredictor:
        """Load a trusted joblib artifact from disk.

        Joblib uses pickle internally; callers must never load user-supplied files.
        """

        artifact_path = Path(path).resolve() if path is not None else find_latest_artifact()
        if not artifact_path.is_file():
            raise ArtifactNotFoundError(f"Model artifact not found: {artifact_path}")
        return cls(joblib.load(artifact_path), artifact_path=artifact_path)

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "model_version": self._artifact["model_version"],
            "selected_model": self._artifact["selected_model"],
            "evaluation": self._artifact["evaluation"],
            "global_feature_importance": self._artifact["global_feature_importance"],
        }

    def predict(self, features: Mapping[str, Any]) -> dict[str, Any]:
        frame = _coerce_record(features)
        estimator = self._artifact["estimator"]
        predicted_class = int(estimator.predict(frame)[0])
        class_order = [int(value) for value in estimator.classes_]
        probability_values = estimator.predict_proba(frame)[0]
        probabilities = {
            CLASS_LABELS[class_id]: float(probability)
            for class_id, probability in zip(class_order, probability_values, strict=True)
        }
        return {
            "risk_level": predicted_class,
            "risk_label": CLASS_LABELS[predicted_class],
            "probabilities": probabilities,
            "model_version": self._artifact["model_version"],
        }

    def predict_proba(self, features: Mapping[str, Any]) -> dict[str, float]:
        return self.predict(features)["probabilities"]

    def explain(
        self,
        features: Mapping[str, Any],
        target_class: int | None = None,
    ) -> dict[str, Any]:
        if target_class is not None and target_class not in CLASS_LABELS:
            raise ValueError("target_class must be 0 (low), 1 (mid), or 2 (high).")
        frame = _coerce_record(features)
        explanation = explain_prediction(
            self._artifact["estimator"],
            frame,
            FEATURE_COLUMNS,
            target_class=target_class,
        )
        explanation["explained_label"] = CLASS_LABELS[explanation["explained_class"]]
        explanation["feature_values"] = {
            name: float(frame.iloc[0][name]) for name in FEATURE_COLUMNS
        }
        return explanation
