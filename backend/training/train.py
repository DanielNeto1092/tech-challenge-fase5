"""Train, compare and persist the maternal-health risk classifier.

Run from the backend directory with::

    python -m training.train
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.constants import (
    ARTIFACT_FILENAME_PREFIX,
    ARTIFACT_SCHEMA_VERSION,
    CLASS_LABELS,
    DEFAULT_MODEL_VERSION,
    FEATURE_COLUMNS,
    RAW_COLUMN_ALIASES,
    STRING_TARGET_ALIASES,
    TARGET_COLUMN,
)
from app.ml.explainability import global_feature_importance

RANDOM_STATE = 42
TEST_SIZE = 0.20
MODEL_NAMES = ("multinomial_logistic_regression", "random_forest")


@dataclass(frozen=True)
class PreparedDataset:
    features: pd.DataFrame
    target: pd.Series
    audit: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class HoldoutSplit:
    train_features: pd.DataFrame
    test_features: pd.DataFrame
    train_target: pd.Series
    test_target: pd.Series
    train_groups: np.ndarray
    test_groups: np.ndarray


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _normalize_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    recognized_sources = [name for name in frame.columns if name in RAW_COLUMN_ALIASES]
    normalized_names = [RAW_COLUMN_ALIASES[name] for name in recognized_sources]
    duplicates = sorted(name for name in set(normalized_names) if normalized_names.count(name) > 1)
    if duplicates:
        raise ValueError(f"Multiple source columns map to the same model feature: {duplicates}")
    frame = frame.rename(columns=RAW_COLUMN_ALIASES)
    required = set(FEATURE_COLUMNS) | {TARGET_COLUMN}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Dataset columns are missing after normalization: {missing}")
    ignored = [column for column in frame.columns if column not in required]
    return frame.loc[:, [*FEATURE_COLUMNS, TARGET_COLUMN]], ignored


def _normalize_target(series: pd.Series) -> pd.Series:
    normalized = series.copy()
    if not pd.api.types.is_numeric_dtype(normalized):
        strings = normalized.astype("string").str.strip().str.lower()
        normalized = strings.map(STRING_TARGET_ALIASES)
    numeric = pd.to_numeric(normalized, errors="coerce")
    if numeric.isna().any():
        invalid = sorted({str(value) for value in series[numeric.isna()].tolist()})
        raise ValueError(f"RiskLevel contains unsupported values: {invalid}")
    if not np.allclose(numeric.to_numpy(), numeric.astype(int).to_numpy()):
        raise ValueError("RiskLevel must contain integer class codes 0, 1, or 2.")
    numeric = numeric.astype(int)
    unexpected = sorted(set(numeric.unique()).difference(CLASS_LABELS))
    if unexpected:
        raise ValueError(f"RiskLevel contains unsupported class codes: {unexpected}")
    return numeric.rename(TARGET_COLUMN)


def _class_counts(target: pd.Series) -> dict[str, int]:
    counts = target.value_counts().reindex(CLASS_LABELS, fill_value=0)
    return {CLASS_LABELS[class_id]: int(counts[class_id]) for class_id in CLASS_LABELS}


def _iqr_audit(features: pd.DataFrame) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for feature in FEATURE_COLUMNS:
        values = features[feature].dropna()
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = values[(values < lower) | (values > upper)]
        report[feature] = {
            "lower_fence": lower,
            "upper_fence": upper,
            "row_count_outside_fences": int(outliers.shape[0]),
            "observed_minimum": float(values.min()),
            "observed_maximum": float(values.max()),
        }
    return report


def load_and_prepare_dataset(csv_path: str | Path) -> PreparedDataset:
    """Load the selected CSV, audit it and remove exact repeated records."""

    path = Path(csv_path)
    raw_bytes = path.read_bytes()
    frame, ignored_columns = _normalize_columns(pd.read_csv(path))
    raw_rows = int(frame.shape[0])

    numeric_features = frame.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    numeric_features = numeric_features.replace([np.inf, -np.inf], np.nan)
    target = _normalize_target(frame[TARGET_COLUMN])
    normalized = numeric_features.assign(**{TARGET_COLUMN: target})

    missing_counts = {column: int(count) for column, count in normalized.isna().sum().items()}
    exact_duplicate_mask = normalized.duplicated(keep="first")
    exact_duplicate_rows = int(exact_duplicate_mask.sum())
    cleaned = normalized.loc[~exact_duplicate_mask].reset_index(drop=True)

    feature_group_sizes = cleaned.groupby(list(FEATURE_COLUMNS), dropna=False, sort=False).size()
    labels_per_feature_group = cleaned.groupby(list(FEATURE_COLUMNS), dropna=False, sort=False)[
        TARGET_COLUMN
    ].nunique()
    duplicate_feature_groups = int((feature_group_sizes > 1).sum())
    conflicting_feature_groups = int((labels_per_feature_group > 1).sum())

    raw_target = normalized[TARGET_COLUMN]
    clean_target = cleaned[TARGET_COLUMN].astype(int)
    audit = {
        "raw_row_count": raw_rows,
        "unique_exact_row_count": int(cleaned.shape[0]),
        "exact_duplicate_rows_removed": exact_duplicate_rows,
        "raw_class_counts": _class_counts(raw_target),
        "clean_class_counts": _class_counts(clean_target),
        "missing_value_counts": missing_counts,
        "ignored_columns": ignored_columns,
        "unique_feature_vector_count": int(feature_group_sizes.shape[0]),
        "duplicate_feature_vector_groups_after_exact_deduplication": (duplicate_feature_groups),
        "feature_vector_groups_with_conflicting_labels": conflicting_feature_groups,
        "statistical_outliers_retained": _iqr_audit(numeric_features),
        "descriptive_statistics_after_exact_deduplication": _jsonable(
            cleaned.loc[:, FEATURE_COLUMNS].describe().to_dict()
        ),
        "duplicate_policy": (
            "Exact repeated rows are removed before splitting. Remaining equal "
            "feature vectors (including conflicting labels) are assigned as groups "
            "so no feature vector crosses train and test."
        ),
    }
    return PreparedDataset(
        features=cleaned.loc[:, FEATURE_COLUMNS].copy(),
        target=clean_target.copy(),
        audit=audit,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _feature_groups(features: pd.DataFrame) -> np.ndarray:
    # Factorizing the complete MultiIndex avoids relying on a lossy hash.
    multi_index = pd.MultiIndex.from_frame(features.loc[:, FEATURE_COLUMNS])
    groups, _ = pd.factorize(multi_index, sort=False)
    return groups


def stratified_group_holdout(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> HoldoutSplit:
    """Create an approximately stratified holdout with zero group overlap."""

    if not 0 < test_size < 1:
        raise ValueError("test_size must be between zero and one.")
    groups = _feature_groups(features)
    split_count = max(2, int(round(1 / test_size)))
    group_counts_by_class = (
        pd.DataFrame({"target": target.to_numpy(), "group": groups})
        .groupby("target")["group"]
        .nunique()
    )
    if any(group_counts_by_class.get(class_id, 0) < split_count for class_id in CLASS_LABELS):
        raise ValueError(f"At least {split_count} distinct feature groups per class are required.")

    splitter = StratifiedGroupKFold(
        n_splits=split_count,
        shuffle=True,
        random_state=random_state,
    )
    overall_distribution = target.value_counts(normalize=True).reindex(CLASS_LABELS, fill_value=0.0)
    candidates: list[tuple[float, np.ndarray, np.ndarray]] = []
    for train_index, test_index in splitter.split(features, target, groups):
        train_classes = set(target.iloc[train_index].unique())
        test_classes = set(target.iloc[test_index].unique())
        if train_classes != set(CLASS_LABELS) or test_classes != set(CLASS_LABELS):
            continue
        test_distribution = (
            target.iloc[test_index]
            .value_counts(normalize=True)
            .reindex(CLASS_LABELS, fill_value=0.0)
        )
        size_error = abs((len(test_index) / len(target)) - test_size)
        distribution_error = float(np.abs(test_distribution - overall_distribution).sum())
        candidates.append((size_error + distribution_error, train_index, test_index))
    if not candidates:
        raise ValueError("Unable to create a grouped holdout containing every class.")

    _, train_index, test_index = min(candidates, key=lambda candidate: candidate[0])
    train_groups = groups[train_index]
    test_groups = groups[test_index]
    if set(train_groups).intersection(test_groups):
        raise RuntimeError("Feature-group leakage detected in the holdout split.")

    return HoldoutSplit(
        train_features=features.iloc[train_index].reset_index(drop=True),
        test_features=features.iloc[test_index].reset_index(drop=True),
        train_target=target.iloc[train_index].reset_index(drop=True),
        test_target=target.iloc[test_index].reset_index(drop=True),
        train_groups=train_groups,
        test_groups=test_groups,
    )


def build_candidate_models(
    *,
    random_state: int = RANDOM_STATE,
    random_forest_estimators: int = 300,
) -> OrderedDict[str, Pipeline]:
    """Build exactly the two models required by the project specification."""

    if random_forest_estimators < 1:
        raise ValueError("random_forest_estimators must be positive.")
    return OrderedDict(
        (
            (
                MODEL_NAMES[0],
                Pipeline(
                    steps=(
                        (
                            "preprocess",
                            Pipeline(
                                steps=(
                                    ("imputer", SimpleImputer(strategy="median")),
                                    ("scaler", StandardScaler()),
                                )
                            ),
                        ),
                        (
                            "classifier",
                            LogisticRegression(
                                class_weight="balanced",
                                max_iter=3_000,
                                random_state=random_state,
                                solver="lbfgs",
                            ),
                        ),
                    )
                ),
            ),
            (
                MODEL_NAMES[1],
                Pipeline(
                    steps=(
                        (
                            "preprocess",
                            SimpleImputer(strategy="median"),
                        ),
                        (
                            "classifier",
                            RandomForestClassifier(
                                n_estimators=random_forest_estimators,
                                min_samples_leaf=2,
                                class_weight="balanced",
                                random_state=random_state,
                                n_jobs=-1,
                            ),
                        ),
                    )
                ),
            ),
        )
    )


def evaluate_classifier(
    estimator: Pipeline,
    features: pd.DataFrame,
    target: pd.Series,
) -> dict[str, Any]:
    prediction = estimator.predict(features)
    labels = list(CLASS_LABELS)
    recalls = recall_score(target, prediction, labels=labels, average=None, zero_division=0)
    high_mask = target.to_numpy() == 2
    high_false_negatives = int(np.sum(high_mask & (prediction != 2)))
    return {
        "accuracy": float(accuracy_score(target, prediction)),
        "precision_macro": float(
            precision_score(target, prediction, labels=labels, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            recall_score(target, prediction, labels=labels, average="macro", zero_division=0)
        ),
        "f1_macro": float(
            f1_score(target, prediction, labels=labels, average="macro", zero_division=0)
        ),
        "recall_by_class": {
            CLASS_LABELS[class_id]: float(value)
            for class_id, value in zip(labels, recalls, strict=True)
        },
        "high_risk_false_negatives": high_false_negatives,
        "confusion_matrix": confusion_matrix(target, prediction, labels=labels)
        .astype(int)
        .tolist(),
        "confusion_matrix_label_order": [CLASS_LABELS[class_id] for class_id in labels],
    }


def select_model(evaluations: dict[str, dict[str, Any]]) -> tuple[str, str]:
    if set(evaluations) != set(MODEL_NAMES):
        raise ValueError(f"Evaluations must contain exactly these models: {MODEL_NAMES}")
    selected_name = max(
        MODEL_NAMES,
        key=lambda name: (
            evaluations[name]["recall_by_class"]["high"],
            evaluations[name]["f1_macro"],
            evaluations[name]["accuracy"],
            -MODEL_NAMES.index(name),
        ),
    )
    justification = (
        f"Selected {selected_name} by the predefined lexicographic rule: maximize "
        "high-risk recall first (reducing high-risk false negatives), then macro F1, "
        "then accuracy. The holdout was not used for hyperparameter tuning."
    )
    return selected_name, justification


def _validate_model_version(model_version: str) -> str:
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", model_version):
        raise ValueError("model_version must contain one to three numeric components.")
    return model_version


def train_and_save(
    csv_path: str | Path,
    output_dir: str | Path,
    *,
    model_version: str = DEFAULT_MODEL_VERSION,
    random_state: int = RANDOM_STATE,
    random_forest_estimators: int = 300,
) -> tuple[Path, Path, dict[str, Any]]:
    """Run the full deterministic comparison, final fit and serialization."""

    model_version = _validate_model_version(model_version)
    prepared = load_and_prepare_dataset(csv_path)
    split = stratified_group_holdout(
        prepared.features,
        prepared.target,
        random_state=random_state,
    )
    candidates = build_candidate_models(
        random_state=random_state,
        random_forest_estimators=random_forest_estimators,
    )

    evaluations: dict[str, dict[str, Any]] = {}
    for name, estimator in candidates.items():
        estimator.fit(split.train_features, split.train_target)
        evaluations[name] = evaluate_classifier(estimator, split.test_features, split.test_target)

    selected_name, selection_justification = select_model(evaluations)
    # Evaluation remains strictly holdout-based; the deployable estimator is then
    # refitted on all cleaned data after model selection.
    final_estimator = clone(candidates[selected_name])
    final_estimator.fit(prepared.features, prepared.target)
    importance = global_feature_importance(final_estimator, FEATURE_COLUMNS)

    train_groups = set(int(value) for value in split.train_groups)
    test_groups = set(int(value) for value in split.test_groups)
    report: dict[str, Any] = {
        "model_version": model_version,
        "random_state": random_state,
        "dataset": {
            "path": str(Path(csv_path)),
            "sha256": prepared.sha256,
            "audit": prepared.audit,
        },
        "split": {
            "strategy": "best-balanced fold from StratifiedGroupKFold",
            "test_size_requested": TEST_SIZE,
            "train_row_count": int(len(split.train_target)),
            "test_row_count": int(len(split.test_target)),
            "train_class_counts": _class_counts(split.train_target),
            "test_class_counts": _class_counts(split.test_target),
            "train_feature_group_count": len(train_groups),
            "test_feature_group_count": len(test_groups),
            "feature_group_overlap_count": len(train_groups.intersection(test_groups)),
            "preprocessing_fitted_on_training_partition_only": True,
        },
        "candidate_models": list(candidates),
        "evaluations": evaluations,
        "selected_model": selected_name,
        "selection_justification": selection_justification,
        "global_feature_importance": importance,
        "local_explanation_method": (
            "Exact tree-path probability decomposition for random forest or exact "
            "linear-logit decomposition for multinomial logistic regression."
        ),
        "final_fit": "Selected model refitted on every exact-deduplicated row.",
    }

    created_at = datetime.now(UTC).isoformat()
    artifact = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_version": model_version,
        "created_at_utc": created_at,
        "dataset_sha256": prepared.sha256,
        "feature_names": FEATURE_COLUMNS,
        "target_name": TARGET_COLUMN,
        "class_labels": CLASS_LABELS,
        "selected_model": selected_name,
        "estimator": final_estimator,
        "evaluation": evaluations[selected_name],
        "all_model_evaluations": evaluations,
        "selection_justification": selection_justification,
        "global_feature_importance": importance,
        "training_audit": prepared.audit,
        "library_versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    artifact_path = destination / (f"{ARTIFACT_FILENAME_PREFIX}{model_version}.joblib")
    report_path = destination / f"training_report_v{model_version}.json"
    joblib.dump(artifact, artifact_path, compress=3)
    report_path.write_text(
        json.dumps(_jsonable(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifact_path, report_path, report


def parse_args() -> argparse.Namespace:
    backend_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Train and compare the two maternal-risk classifiers."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=backend_dir / "data" / "raw" / "maternal_health_risk.csv",
        help="Path to the selected Kaggle CSV (never downloaded by this script).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=backend_dir / "artifacts",
        help="Directory for the versioned joblib artifact and JSON report.",
    )
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact_path, report_path, report = train_and_save(
        args.data,
        args.output_dir,
        model_version=args.model_version,
        random_state=args.random_state,
    )
    summary = {
        "artifact": str(artifact_path),
        "report": str(report_path),
        "selected_model": report["selected_model"],
        "selection_justification": report["selection_justification"],
        "evaluations": report["evaluations"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
