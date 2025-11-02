"""Collaborative filtering via a pure Python Alternating Least Squares implementation."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..config import ModelConfig
from ..data.ingestion import OrderRecord


@dataclass
class ALSArtifacts:
    user_factors: List[List[float]]
    item_factors: List[List[float]]
    user_mapping: Dict[str, int]
    item_mapping: Dict[str, int]


def build_interaction_matrix(
    orders: List[OrderRecord],
) -> Tuple[List[List[float]], Dict[str, int], Dict[str, int]]:
    users = sorted({record.user_id for record in orders})
    items = sorted({record.product_id for record in orders})
    user_index = {u: idx for idx, u in enumerate(users)}
    item_index = {i: idx for idx, i in enumerate(items)}
    matrix = [[0.0 for _ in items] for _ in users]
    for record in orders:
        matrix[user_index[record.user_id]][item_index[record.product_id]] += float(record.quantity)
    return matrix, user_index, item_index


def _transpose_multiply(matrix: List[List[float]]) -> List[List[float]]:
    factors = len(matrix[0])
    result = [[0.0 for _ in range(factors)] for _ in range(factors)]
    for row in matrix:
        for i in range(factors):
            for j in range(factors):
                result[i][j] += row[i] * row[j]
    return result


def _vector_multiply(transpose: List[List[float]], vector: List[float]) -> List[float]:
    return [sum(transpose[i][j] * vector[j] for j in range(len(vector))) for i in range(len(transpose))]


def _add_regularization(matrix: List[List[float]], reg: float) -> List[List[float]]:
    size = len(matrix)
    return [[matrix[i][j] + (reg if i == j else 0.0) for j in range(size)] for i in range(size)]


def _solve_linear_system(matrix: List[List[float]], vector: List[float]) -> List[float]:
    n = len(matrix)
    # Build augmented matrix
    aug = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for i in range(n):
        # Pivot selection
        pivot_row = max(range(i, n), key=lambda r: abs(aug[r][i]))
        if abs(aug[pivot_row][i]) < 1e-9:
            continue
        if pivot_row != i:
            aug[i], aug[pivot_row] = aug[pivot_row], aug[i]
        pivot = aug[i][i]
        # Normalize pivot row
        for j in range(i, n + 1):
            aug[i][j] /= pivot
        # Eliminate other rows
        for r in range(n):
            if r == i:
                continue
            factor = aug[r][i]
            for c in range(i, n + 1):
                aug[r][c] -= factor * aug[i][c]
    return [aug[i][n] for i in range(n)]


def train_als(orders: List[OrderRecord], config: ModelConfig) -> ALSArtifacts:
    interactions, user_index, item_index = build_interaction_matrix(orders)
    num_users = len(interactions)
    num_items = len(interactions[0]) if interactions else 0
    num_factors = config.als_factors
    if num_users == 0 or num_items == 0:
        return ALSArtifacts([], [], user_index, item_index)

    random.seed(42)
    user_factors = [[random.uniform(-0.1, 0.1) for _ in range(num_factors)] for _ in range(num_users)]
    item_factors = [[random.uniform(-0.1, 0.1) for _ in range(num_factors)] for _ in range(num_items)]

    reg = config.als_regularization

    for _ in range(config.als_iterations):
        item_gram = _transpose_multiply(item_factors)
        regularized_item_gram = _add_regularization(item_gram, reg)
        for u in range(num_users):
            user_interactions = interactions[u]
            rhs = _vector_multiply([list(col) for col in zip(*item_factors)], user_interactions)
            user_factors[u] = _solve_linear_system(regularized_item_gram, rhs)
        user_gram = _transpose_multiply(user_factors)
        regularized_user_gram = _add_regularization(user_gram, reg)
        for i in range(num_items):
            item_interactions = [interactions[u][i] for u in range(num_users)]
            rhs = _vector_multiply([list(col) for col in zip(*user_factors)], item_interactions)
            item_factors[i] = _solve_linear_system(regularized_user_gram, rhs)

    return ALSArtifacts(
        user_factors=user_factors,
        item_factors=item_factors,
        user_mapping=user_index,
        item_mapping=item_index,
    )


def recommend_for_user(artifacts: ALSArtifacts, user_id: str, top_k: int) -> List[Dict[str, object]]:
    if user_id not in artifacts.user_mapping or not artifacts.item_factors:
        return []
    user_idx = artifacts.user_mapping[user_id]
    user_vector = artifacts.user_factors[user_idx]
    scores = []
    inv_item_mapping = {idx: item for item, idx in artifacts.item_mapping.items()}
    for idx, item_vector in enumerate(artifacts.item_factors):
        score = sum(u * v for u, v in zip(user_vector, item_vector))
        scores.append((inv_item_mapping[idx], score))
    scores.sort(key=lambda pair: pair[1], reverse=True)
    return [
        {"user_id": user_id, "product_id": product_id, "score": score}
        for product_id, score in scores[:top_k]
    ]


def similar_items(artifacts: ALSArtifacts, product_id: str, top_k: int) -> List[Dict[str, object]]:
    if product_id not in artifacts.item_mapping or not artifacts.item_factors:
        return []
    item_idx = artifacts.item_mapping[product_id]
    target_vector = artifacts.item_factors[item_idx]
    inv_item_mapping = {idx: item for item, idx in artifacts.item_mapping.items()}

    def cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    similarities = []
    for idx, vector in enumerate(artifacts.item_factors):
        if idx == item_idx:
            continue
        similarities.append((inv_item_mapping[idx], cosine_similarity(target_vector, vector)))
    similarities.sort(key=lambda pair: pair[1], reverse=True)
    return [
        {"product_id": product_id, "similar_product_id": other, "score": score}
        for other, score in similarities[:top_k]
    ]
