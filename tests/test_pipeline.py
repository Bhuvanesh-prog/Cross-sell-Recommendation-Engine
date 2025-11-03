from pathlib import Path

from cross_sell.config import PipelineConfig
from cross_sell.workflows.pipeline import run_pipeline


def test_pipeline_produces_gold_tables(tmp_path: Path) -> None:
    config = PipelineConfig(
        lakehouse_root=tmp_path / "lakehouse",
        orders_source=Path("data/sample_orders.csv"),
    )
    artifacts = run_pipeline(config)

    assert artifacts["assoc_rules"], "Expected association rules"
    assert artifacts["item_similarity"], "Expected item similarity rows"
    assert artifacts["user_recommendations"], "Expected user recommendations"
    assert artifacts["silver_products"], "Expected enriched product catalog"
    assert artifacts["silver_customers"], "Expected enriched customer dimension"

    first_rule = artifacts["assoc_rules"][0]
    assert "lhs_details" in first_rule and first_rule["lhs_details"], "Association rules should include product context"

    first_user_rec = artifacts["user_recommendations"][0]
    assert "product_name" in first_user_rec and first_user_rec["product_name"], "User recs should include product metadata"
    assert "user_segment" in first_user_rec and first_user_rec["user_segment"], "User recs should include customer metadata"

    gold_dir = config.lakehouse.gold
    assert (gold_dir / "assoc_rules.json").exists()
    assert (gold_dir / "item_similarity.json").exists()
    assert (gold_dir / "user_recommendations.json").exists()
