"""Sample end-to-end workflow orchestrating ingestion, modeling, and gold outputs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..config import PipelineConfig
from ..data import gold
from ..data.ingestion import (
    CustomerRecord,
    OrderRecord,
    ProductRecord,
    cleanse_customers,
    cleanse_orders,
    cleanse_products,
    load_bronze_customers,
    load_bronze_orders,
    load_bronze_products,
    load_silver_customers,
    load_silver_orders,
    load_silver_products,
    read_customers_csv,
    read_orders_csv,
    read_products_csv,
    write_bronze_customers,
    write_bronze_orders,
    write_bronze_products,
    write_silver_customers,
    write_silver_orders,
    write_silver_products,
)
from ..models.association_rules import AssociationRuleResult, mine_rules
from ..models.collaborative_filter import ALSArtifacts, recommend_for_user, similar_items, train_als


@dataclass
class PipelineArtifacts:
    bronze_orders: List[OrderRecord]
    silver_orders: List[OrderRecord]
    bronze_products: List[ProductRecord]
    silver_products: List[ProductRecord]
    bronze_customers: List[CustomerRecord]
    silver_customers: List[CustomerRecord]
    assoc_rules: List[Dict[str, object]]
    item_similarity: List[Dict[str, object]]
    user_recommendations: List[Dict[str, object]]

    def __getitem__(self, item: str):
        return {
            "bronze_orders": self.bronze_orders,
            "silver_orders": self.silver_orders,
            "bronze_products": self.bronze_products,
            "silver_products": self.silver_products,
            "bronze_customers": self.bronze_customers,
            "silver_customers": self.silver_customers,
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

    if config.products_source:
        raw_products = read_products_csv(config.products_source)
        write_bronze_products(raw_products, lakehouse)
        bronze_products = load_bronze_products(lakehouse)
        cleansed_products = cleanse_products(bronze_products)
        write_silver_products(cleansed_products, lakehouse)
        silver_products = load_silver_products(lakehouse)
    else:
        bronze_products = []
        silver_products = []

    if config.customers_source:
        raw_customers = read_customers_csv(config.customers_source)
        write_bronze_customers(raw_customers, lakehouse)
        bronze_customers = load_bronze_customers(lakehouse)
        cleansed_customers = cleanse_customers(bronze_customers)
        write_silver_customers(cleansed_customers, lakehouse)
        silver_customers = load_silver_customers(lakehouse)
    else:
        bronze_customers = []
        silver_customers = []

    product_lookup = {product.product_id: product for product in silver_products}
    customer_lookup = {customer.user_id: customer for customer in silver_customers}

    assoc_result: AssociationRuleResult = mine_rules(silver_orders, config.model)
    enriched_rules: List[Dict[str, object]] = []
    for rule in assoc_result.rules:
        lhs_details = [
            {
                "product_id": product_id,
                "name": product_lookup[product_id].name if product_id in product_lookup else None,
                "category": product_lookup[product_id].category if product_id in product_lookup else None,
                "brand": product_lookup[product_id].brand if product_id in product_lookup else None,
            }
            for product_id in rule["lhs"]
        ]
        rhs_details = [
            {
                "product_id": product_id,
                "name": product_lookup[product_id].name if product_id in product_lookup else None,
                "category": product_lookup[product_id].category if product_id in product_lookup else None,
                "brand": product_lookup[product_id].brand if product_id in product_lookup else None,
            }
            for product_id in rule["rhs"]
        ]
        enriched_rule = dict(rule)
        enriched_rule["lhs_details"] = lhs_details
        enriched_rule["rhs_details"] = rhs_details
        enriched_rules.append(enriched_rule)
    gold.write_gold_table(enriched_rules, lakehouse, "assoc_rules")

    als_artifacts: ALSArtifacts = train_als(silver_orders, config.model)
    item_similarity: List[Dict[str, object]] = []
    for product_id in sorted(als_artifacts.item_mapping.keys()):
        for row in similar_items(als_artifacts, product_id, config.model.top_k):
            base_product = product_lookup.get(row["product_id"])
            similar_product = product_lookup.get(row["similar_product_id"])
            enriched_row = dict(row)
            if base_product:
                enriched_row.update(
                    {
                        "product_name": base_product.name,
                        "product_category": base_product.category,
                        "product_brand": base_product.brand,
                    }
                )
            if similar_product:
                enriched_row.update(
                    {
                        "similar_product_name": similar_product.name,
                        "similar_product_category": similar_product.category,
                        "similar_product_brand": similar_product.brand,
                    }
                )
            item_similarity.append(enriched_row)
    gold.write_gold_table(item_similarity, lakehouse, "item_similarity")

    user_recommendations: List[Dict[str, object]] = []
    for user_id in sorted(als_artifacts.user_mapping.keys()):
        for row in recommend_for_user(als_artifacts, user_id, config.model.top_k):
            enriched_row = dict(row)
            product = product_lookup.get(row["product_id"])
            customer = customer_lookup.get(row["user_id"])
            if product:
                enriched_row.update(
                    {
                        "product_name": product.name,
                        "product_category": product.category,
                        "product_brand": product.brand,
                    }
                )
            if customer:
                enriched_row.update(
                    {
                        "user_segment": customer.segment,
                        "user_region": customer.region,
                        "loyalty_tier": customer.loyalty_tier,
                    }
                )
            user_recommendations.append(enriched_row)
    gold.write_gold_table(user_recommendations, lakehouse, "user_recs")

    return PipelineArtifacts(
        bronze_orders=bronze_orders,
        silver_orders=silver_orders,
        bronze_products=bronze_products,
        silver_products=silver_products,
        bronze_customers=bronze_customers,
        silver_customers=silver_customers,
        assoc_rules=enriched_rules,
        item_similarity=item_similarity,
        user_recommendations=user_recommendations,
    )

