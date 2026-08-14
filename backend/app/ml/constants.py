"""Shared constants for the maternal-risk machine-learning pipeline."""

from __future__ import annotations

from typing import Final

FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "age",
    "systolic_bp",
    "diastolic_bp",
    "blood_sugar",
    "body_temperature",
    "heart_rate",
)

TARGET_COLUMN: Final[str] = "risk_level"

# Both blood-glucose spellings are documented variants of the selected dataset.
# The checked-in CSV uses ``Blood glucose``.
RAW_COLUMN_ALIASES: Final[dict[str, str]] = {
    "Age": "age",
    "SystolicBP": "systolic_bp",
    "DiastolicBP": "diastolic_bp",
    "Blood glucose": "blood_sugar",
    "BS": "blood_sugar",
    "BodyTemp": "body_temperature",
    "HeartRate": "heart_rate",
    "RiskLevel": TARGET_COLUMN,
}

CLASS_LABELS: Final[dict[int, str]] = {
    0: "low",
    1: "mid",
    2: "high",
}

STRING_TARGET_ALIASES: Final[dict[str, int]] = {
    "0": 0,
    "low": 0,
    "low risk": 0,
    "1": 1,
    "mid": 1,
    "medium": 1,
    "mid risk": 1,
    "medium risk": 1,
    "2": 2,
    "high": 2,
    "high risk": 2,
}

ARTIFACT_SCHEMA_VERSION: Final[str] = "1.0"
DEFAULT_MODEL_VERSION: Final[str] = "1.0.0"
ARTIFACT_FILENAME_PREFIX: Final[str] = "maternal_risk_model_v"
