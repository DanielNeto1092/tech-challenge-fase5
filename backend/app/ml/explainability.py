"""Dependency-free, exact explanations for the two supported estimators.

SHAP is intentionally not required. Random-forest predictions are decomposed
along every tree path, while multinomial logistic-regression logits are
decomposed into their exact linear terms. Both decompositions reconstruct the
quantity produced by the fitted model (probability or logit, respectively).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def _fitted_parts(
    estimator: Pipeline,
    frame: pd.DataFrame,
) -> tuple[np.ndarray, Any]:
    if not isinstance(estimator, Pipeline):
        raise TypeError("The saved estimator must be a scikit-learn Pipeline.")
    try:
        preprocess = estimator.named_steps["preprocess"]
        classifier = estimator.named_steps["classifier"]
    except KeyError as exc:
        raise ValueError(
            "The estimator pipeline must contain 'preprocess' and 'classifier'."
        ) from exc

    transformed = np.asarray(preprocess.transform(frame), dtype=float)
    if transformed.shape[0] != 1:
        raise ValueError("A local explanation requires exactly one record.")
    return transformed, classifier


def _class_index(classes: np.ndarray, target_class: int) -> int:
    positions = np.flatnonzero(classes == target_class)
    if positions.size != 1:
        raise ValueError(f"Class {target_class!r} is not present in the fitted model.")
    return int(positions[0])


def _node_probabilities(tree: Any, node_id: int) -> np.ndarray:
    values = np.asarray(tree.value[node_id][0], dtype=float)
    total = float(values.sum())
    if total <= 0:
        return np.zeros_like(values)
    return values / total


def _forest_path_explanation(
    classifier: RandomForestClassifier,
    transformed: np.ndarray,
    feature_names: Sequence[str],
    target_class: int,
) -> dict[str, Any]:
    classes = np.asarray(classifier.classes_)
    target_index = _class_index(classes, target_class)
    contributions = np.zeros((len(feature_names), len(classes)), dtype=float)
    baseline = np.zeros(len(classes), dtype=float)

    for fitted_tree in classifier.estimators_:
        tree = fitted_tree.tree_
        node_id = 0
        parent_probability = _node_probabilities(tree, node_id)
        baseline += parent_probability

        while tree.feature[node_id] >= 0:
            feature_index = int(tree.feature[node_id])
            threshold = float(tree.threshold[node_id])
            if transformed[0, feature_index] <= threshold:
                child_id = int(tree.children_left[node_id])
            else:
                child_id = int(tree.children_right[node_id])

            child_probability = _node_probabilities(tree, child_id)
            contributions[feature_index] += child_probability - parent_probability
            node_id = child_id
            parent_probability = child_probability

    tree_count = len(classifier.estimators_)
    baseline /= tree_count
    contributions /= tree_count

    model_probability = float(classifier.predict_proba(transformed)[0, target_index])
    selected_contributions = contributions[:, target_index]
    reconstructed = float(baseline[target_index] + selected_contributions.sum())

    return {
        "method": "exact_random_forest_path_probability_decomposition",
        "explained_class": int(target_class),
        "baseline_probability": float(baseline[target_index]),
        "feature_contributions": {
            name: float(value)
            for name, value in zip(feature_names, selected_contributions, strict=True)
        },
        "model_probability": model_probability,
        "reconstructed_probability": reconstructed,
        "reconstruction_error": abs(model_probability - reconstructed),
        "interpretation": (
            "Positive values increase and negative values decrease the explained "
            "class probability relative to the average tree-root probability."
        ),
    }


def _logistic_explanation(
    classifier: LogisticRegression,
    transformed: np.ndarray,
    feature_names: Sequence[str],
    target_class: int,
) -> dict[str, Any]:
    classes = np.asarray(classifier.classes_)
    target_index = _class_index(classes, target_class)
    if classifier.coef_.shape[0] != len(classes):
        raise ValueError("Only multinomial logistic regression is supported.")

    baseline = float(classifier.intercept_[target_index])
    selected_contributions = transformed[0] * classifier.coef_[target_index]
    model_logit = float(classifier.decision_function(transformed)[0, target_index])
    reconstructed = float(baseline + selected_contributions.sum())
    model_probability = float(classifier.predict_proba(transformed)[0, target_index])

    return {
        "method": "exact_multinomial_logit_decomposition",
        "explained_class": int(target_class),
        "baseline_logit": baseline,
        "feature_contributions": {
            name: float(value)
            for name, value in zip(feature_names, selected_contributions, strict=True)
        },
        "model_logit": model_logit,
        "reconstructed_logit": reconstructed,
        "model_probability": model_probability,
        "reconstruction_error": abs(model_logit - reconstructed),
        "interpretation": (
            "Positive values increase and negative values decrease the explained "
            "class logit; multinomial probabilities also depend on the other logits."
        ),
    }


def explain_prediction(
    estimator: Pipeline,
    frame: pd.DataFrame,
    feature_names: Sequence[str],
    target_class: int | None = None,
) -> dict[str, Any]:
    """Return an exact, local explanation for one prediction."""

    transformed, classifier = _fitted_parts(estimator, frame)
    if target_class is None:
        target_class = int(classifier.predict(transformed)[0])

    if isinstance(classifier, RandomForestClassifier):
        return _forest_path_explanation(classifier, transformed, feature_names, target_class)
    if isinstance(classifier, LogisticRegression):
        return _logistic_explanation(classifier, transformed, feature_names, target_class)
    raise TypeError(f"No local explanation is implemented for {type(classifier).__name__}.")


def global_feature_importance(
    estimator: Pipeline,
    feature_names: Sequence[str],
) -> dict[str, float]:
    """Return normalized global importance for a fitted supported estimator."""

    classifier = estimator.named_steps["classifier"]
    if isinstance(classifier, RandomForestClassifier):
        values = np.asarray(classifier.feature_importances_, dtype=float)
    elif isinstance(classifier, LogisticRegression):
        # Macro aggregation avoids privileging a single risk class.
        values = np.abs(np.asarray(classifier.coef_, dtype=float)).mean(axis=0)
    else:
        raise TypeError(f"No global importance is implemented for {type(classifier).__name__}.")

    total = float(values.sum())
    if total > 0:
        values = values / total
    ordered = sorted(
        zip(feature_names, values, strict=True),
        key=lambda item: (-float(item[1]), item[0]),
    )
    return {name: float(value) for name, value in ordered}
