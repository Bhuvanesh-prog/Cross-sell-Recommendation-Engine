"""Sample end-to-end workflow orchestrating ingestion, modeling, and gold outputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..config import PipelineConfig
from ..data import gold
from ..data.ingestion import (
    OrderRecord,
    cleanse_orders,
    load_bronze_orders,
    load_silver_orders,
    read_orders_csv,
    write_bronze_orders,
    write_silver_orders,
)
from ..models.association_rules import AssociationRuleResult, mine_rules
from ..models.collaborative_filter import ALSArtifacts, recommend_for_user, similar_items, train_als


@dataclass
class PipelineArtifacts:
    bronze_orders: List[OrderRecord]
    silver_orders: List[OrderRecord]
    assoc_rules: List[Dict[str, object]]
    item_similarity: List[Dict[str, object]]
    user_recommendations: List[Dict[str, object]]

    def __getitem__(self, item: str):
        return {
            "bronze_orders": self.bronze_orders,
            "silver_orders": self.silver_orders,
            "assoc_rules": self.assoc_rules,
            "item_similarity": self.item_similarity,
            "user_recommendations": self.user_recommendations,
        }[item]


def run_pipeline(config: PipelineConfig) -> PipelineArtifacts:
    lakehouse = config.lakehouse

    raw_orders = read_orders_csv(config.orders_source)
    write_bronze_orders(raw_orders, lakehouse)
    bronze_orders = load_bronze_orders(lakehouse)

    cleansed_orders = cleanse_orders(bronze_orders)
    write_silver_orders(cleansed_orders, lakehouse)
    silver_orders = load_silver_orders(lakehouse)

    assoc_result: AssociationRuleResult = mine_rules(silver_orders, config.model)
    gold.write_gold_table(assoc_result.rules, lakehouse, "assoc_rules")

    als_artifacts: ALSArtifacts = train_als(silver_orders, config.model)
    item_similarity = []
    for product_id in sorted(als_artifacts.item_mapping.keys()):
        item_similarity.extend(similar_items(als_artifacts, product_id, config.model.top_k))
    gold.write_gold_table(item_similarity, lakehouse, "item_similarity")

    user_recommendations = []
    for user_id in sorted(als_artifacts.user_mapping.keys()):
        user_recommendations.extend(recommend_for_user(als_artifacts, user_id, config.model.top_k))
    gold.write_gold_table(user_recommendations, lakehouse, "user_recs")

    return PipelineArtifacts(
        bronze_orders=bronze_orders,
        silver_orders=silver_orders,
        assoc_rules=assoc_result.rules,
        item_similarity=item_similarity,
        user_recommendations=user_recommendations,
    )
