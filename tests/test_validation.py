from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import pytest

from cross_sell.config import ModelConfig, PipelineConfig
from cross_sell.data.ingestion import OrderRecord, read_orders_csv
from cross_sell.models.collaborative_filter import recommend_for_user, train_als
from cross_sell.validation.metrics import (
    map_at_k,
    precision_mean_at_k,
    recall_mean_at_k,
)
from cross_sell.workflows.pipeline import PipelineArtifacts, run_pipeline


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory: pytest.TempPathFactory) -> Tuple[PipelineConfig, PipelineArtifacts]:
    lakehouse_root = tmp_path_factory.mktemp("lakehouse")
    config = PipelineConfig(
        lakehouse_root=lakehouse_root,
        orders_source=Path("data/sample_orders.csv"),
        model=ModelConfig(min_support=0.1, min_confidence=0.3, min_lift=1.1, top_k=5),
    )
    artifacts = run_pipeline(config)
    return config, artifacts


def _assert_order_record_schema(records: Sequence[OrderRecord]) -> None:
    for record in records:
        assert record.order_id
        assert record.user_id
        assert record.product_id
        assert record.quantity > 0
        assert record.unit_price >= 0
        assert record.order_ts
        assert record.sales_channel


def test_bronze_and_silver_quality(pipeline_run: Tuple[PipelineConfig, PipelineArtifacts]) -> None:
    _, artifacts = pipeline_run
    _assert_order_record_schema(artifacts.bronze_orders)
    _assert_order_record_schema(artifacts.silver_orders)

    dedup_keys = {(row.order_id, row.product_id) for row in artifacts.silver_orders}
    assert len(dedup_keys) == len(artifacts.silver_orders)


def test_association_rules_quality(pipeline_run: Tuple[PipelineConfig, PipelineArtifacts]) -> None:
    config, artifacts = pipeline_run
    rules = artifacts.assoc_rules
    assert rules, "Expected association rules to be generated"

    for rule in rules:
        assert rule["support"] >= config.model.min_support - 1e-6
        assert 0.0 < rule["confidence"] <= 1.0
        assert rule["lift"] >= config.model.min_lift


def _build_holdout_sets(orders: Sequence[OrderRecord]) -> Tuple[List[OrderRecord], Dict[str, Set[str]]]:
    per_user: Dict[str, List[OrderRecord]] = defaultdict(list)
    for record in orders:
        per_user[record.user_id].append(record)

    train_records: List[OrderRecord] = []
    holdout: Dict[str, Set[str]] = {}
    for user_id, user_orders in per_user.items():
        sorted_orders = sorted(user_orders, key=lambda r: r.order_ts)
        if len(sorted_orders) <= 1:
            train_records.extend(sorted_orders)
            continue
        holdout_record = sorted_orders[-1]
        train_records.extend(sorted_orders[:-1])
        holdout[user_id] = {holdout_record.product_id}
    return train_records, holdout


def test_collaborative_filter_metrics(pipeline_run: Tuple[PipelineConfig, PipelineArtifacts]) -> None:
    config, _ = pipeline_run
    orders = read_orders_csv(config.orders_source)
    train_records, holdout = _build_holdout_sets(orders)
    als_model = train_als(train_records, config.model)

    recommendations: Dict[str, List[str]] = {}
    for user_id in holdout.keys():
        recs = recommend_for_user(als_model, user_id, config.model.top_k)
        recommendations[user_id] = [row["product_id"] for row in recs]

    precision = precision_mean_at_k(recommendations, holdout, config.model.top_k)
    recall = recall_mean_at_k(recommendations, holdout, config.model.top_k)
    map_score = map_at_k(recommendations, holdout, config.model.top_k)

    assert 0.1 <= precision <= 1.0
    assert 0.5 <= recall <= 1.0
    assert 0.2 <= map_score <= 1.0


def test_gold_outputs_align_with_serving_tables(
    pipeline_run: Tuple[PipelineConfig, PipelineArtifacts]
) -> None:
    config, _ = pipeline_run
    gold_dir = config.lakehouse.gold
    for name in ["assoc_rules.json", "item_similarity.json", "user_recommendations.json"]:
        path = gold_dir / name
        assert path.exists(), f"Missing gold table {name}"
        data = path.read_text().strip()
        assert data.startswith("[") and data.endswith("]"), f"Unexpected format for {name}"
