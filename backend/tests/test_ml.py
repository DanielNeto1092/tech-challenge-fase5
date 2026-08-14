from __future__ import annotations

from pathlib import Path

import joblib
import pytest

from app.ml.constants import CLASS_LABELS, FEATURE_COLUMNS
from app.ml.predictor import MaternalRiskPredictor
from training.train import (
    MODEL_NAMES,
    build_candidate_models,
    load_and_prepare_dataset,
    select_model,
    stratified_group_holdout,
    train_and_save,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BACKEND_DIR / "data" / "raw" / "maternal_health_risk.csv"
EXPECTED_DATASET_SHA256 = "1d272d463635f9d4b94f268468253c9dbe1e78e576ee8badb1b773f4d749a752"


@pytest.fixture(scope="module")
def prepared_dataset():
    return load_and_prepare_dataset(DATASET_PATH)


@pytest.fixture(scope="module")
def trained_artifact(tmp_path_factory: pytest.TempPathFactory):
    output_dir = tmp_path_factory.mktemp("maternal-risk-artifact")
    artifact_path, report_path, report = train_and_save(
        DATASET_PATH,
        output_dir,
        model_version="9.9.9",
        random_forest_estimators=40,
    )
    return artifact_path, report_path, report


def test_dataset_integrity_and_duplicate_audit(prepared_dataset) -> None:
    audit = prepared_dataset.audit

    assert prepared_dataset.sha256 == EXPECTED_DATASET_SHA256
    # The actual file has 1,014 rows although its public description says 1,013.
    assert audit["raw_row_count"] == 1_014
    assert audit["unique_exact_row_count"] == 452
    assert audit["exact_duplicate_rows_removed"] == 562
    assert audit["raw_class_counts"] == {"low": 406, "mid": 336, "high": 272}
    assert audit["feature_vector_groups_with_conflicting_labels"] == 35
    assert audit["missing_value_counts"] == {
        **{feature: 0 for feature in FEATURE_COLUMNS},
        "risk_level": 0,
    }
    # HeartRate=7 is statistically extreme but deliberately retained.
    assert audit["statistical_outliers_retained"]["heart_rate"]["observed_minimum"] == 7


def test_grouped_holdout_prevents_duplicate_vector_leakage(prepared_dataset) -> None:
    split = stratified_group_holdout(
        prepared_dataset.features,
        prepared_dataset.target,
    )

    assert not set(split.train_groups).intersection(split.test_groups)
    assert set(split.train_target.unique()) == set(CLASS_LABELS)
    assert set(split.test_target.unique()) == set(CLASS_LABELS)

    overall_distribution = prepared_dataset.target.value_counts(normalize=True)
    test_distribution = split.test_target.value_counts(normalize=True)
    for class_id in CLASS_LABELS:
        assert abs(test_distribution[class_id] - overall_distribution[class_id]) < 0.08


def test_exactly_two_required_candidate_models_are_built() -> None:
    models = build_candidate_models(random_forest_estimators=3)

    assert tuple(models) == MODEL_NAMES
    assert len(models) == 2
    assert models[MODEL_NAMES[0]].named_steps["classifier"].__class__.__name__ == (
        "LogisticRegression"
    )
    assert models[MODEL_NAMES[1]].named_steps["classifier"].__class__.__name__ == (
        "RandomForestClassifier"
    )


def test_selection_prioritizes_high_risk_recall() -> None:
    evaluations = {
        MODEL_NAMES[0]: {
            "recall_by_class": {"high": 0.80},
            "f1_macro": 0.95,
            "accuracy": 0.95,
        },
        MODEL_NAMES[1]: {
            "recall_by_class": {"high": 0.90},
            "f1_macro": 0.70,
            "accuracy": 0.70,
        },
    }

    selected, justification = select_model(evaluations)

    assert selected == MODEL_NAMES[1]
    assert "high-risk recall first" in justification


def test_training_compares_models_and_writes_versioned_artifact(trained_artifact) -> None:
    artifact_path, report_path, report = trained_artifact

    assert artifact_path.name == "maternal_risk_model_v9.9.9.joblib"
    assert report_path.name == "training_report_v9.9.9.json"
    assert artifact_path.is_file()
    assert report_path.is_file()
    assert report["candidate_models"] == list(MODEL_NAMES)
    assert set(report["evaluations"]) == set(MODEL_NAMES)
    assert report["split"]["feature_group_overlap_count"] == 0

    required_metrics = {
        "accuracy",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "recall_by_class",
        "high_risk_false_negatives",
    }
    for metrics in report["evaluations"].values():
        assert required_metrics.issubset(metrics)
        assert set(metrics["recall_by_class"]) == set(CLASS_LABELS.values())

    payload = joblib.load(artifact_path)
    assert payload["model_version"] == "9.9.9"
    assert tuple(payload["feature_names"]) == FEATURE_COLUMNS
    assert set(payload["global_feature_importance"]) == set(FEATURE_COLUMNS)
    assert sum(payload["global_feature_importance"].values()) == pytest.approx(1.0)


def test_predictor_returns_probabilities_and_exact_local_explanation(
    trained_artifact,
) -> None:
    artifact_path, _, _ = trained_artifact
    predictor = MaternalRiskPredictor.load(artifact_path)
    record = {
        "age": 35,
        "systolic_bp": 140,
        "diastolic_bp": 90,
        "blood_sugar": 13.0,
        "body_temperature": 98.0,
        "heart_rate": 70,
    }

    prediction = predictor.predict(record)
    assert prediction["risk_level"] in CLASS_LABELS
    assert prediction["risk_label"] == CLASS_LABELS[prediction["risk_level"]]
    assert set(prediction["probabilities"]) == set(CLASS_LABELS.values())
    assert sum(prediction["probabilities"].values()) == pytest.approx(1.0)

    explanation = predictor.explain(record)
    assert explanation["explained_class"] == prediction["risk_level"]
    assert set(explanation["feature_contributions"]) == set(FEATURE_COLUMNS)
    assert explanation["reconstruction_error"] < 1e-10
    assert explanation["model_probability"] == pytest.approx(
        prediction["probabilities"][prediction["risk_label"]]
    )


def test_predictor_rejects_missing_unknown_and_non_finite_features(
    trained_artifact,
) -> None:
    artifact_path, _, _ = trained_artifact
    predictor = MaternalRiskPredictor.load(artifact_path)
    valid = {
        "age": 25,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "blood_sugar": 7,
        "body_temperature": 98,
        "heart_rate": 75,
    }

    missing = dict(valid)
    missing.pop("age")
    with pytest.raises(ValueError, match="missing"):
        predictor.predict(missing)

    unknown = {**valid, "patient_name": "not allowed"}
    with pytest.raises(ValueError, match="unknown"):
        predictor.predict(unknown)

    non_finite = {**valid, "blood_sugar": float("nan")}
    with pytest.raises(ValueError, match="finite"):
        predictor.predict(non_finite)
