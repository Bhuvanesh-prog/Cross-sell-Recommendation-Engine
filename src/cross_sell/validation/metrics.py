"""Metric utilities used for validating recommendation quality."""
from __future__ import annotations

from typing import Dict, Sequence, Set


def precision_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    """Compute Precision@K for a single user."""
    if k <= 0:
        return 0.0
    top_k = recommended[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(top_k)


def recall_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    """Compute Recall@K for a single user."""
    if not relevant:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def average_precision_at_k(recommended: Sequence[str], relevant: Set[str], k: int) -> float:
    """Compute average precision at K for a single user."""
    if not relevant:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for idx, item in enumerate(recommended[:k], start=1):
        if item in relevant:
            hits += 1
            precision_sum += hits / idx
    if hits == 0:
        return 0.0
    return precision_sum / len(relevant)


def map_at_k(
    recommendations: Dict[str, Sequence[str]],
    ground_truth: Dict[str, Set[str]],
    k: int,
) -> float:
    """Compute MAP@K across all users."""
    if not ground_truth:
        return 0.0
    total = 0.0
    count = 0
    for user, relevant in ground_truth.items():
        recs = recommendations.get(user, [])
        total += average_precision_at_k(recs, relevant, k)
        count += 1
    return total / count if count else 0.0


def mean_metric(
    metric_fn,
    recommendations: Dict[str, Sequence[str]],
    ground_truth: Dict[str, Set[str]],
    k: int,
) -> float:
    if not ground_truth:
        return 0.0
    total = 0.0
    count = 0
    for user, relevant in ground_truth.items():
        recs = recommendations.get(user, [])
        total += metric_fn(recs, relevant, k)
        count += 1
    return total / count if count else 0.0


def precision_mean_at_k(
    recommendations: Dict[str, Sequence[str]],
    ground_truth: Dict[str, Set[str]],
    k: int,
) -> float:
    return mean_metric(precision_at_k, recommendations, ground_truth, k)


def recall_mean_at_k(
    recommendations: Dict[str, Sequence[str]],
    ground_truth: Dict[str, Set[str]],
    k: int,
) -> float:
    return mean_metric(recall_at_k, recommendations, ground_truth, k)
