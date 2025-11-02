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

    gold_dir = config.lakehouse.gold
    assert (gold_dir / "assoc_rules.json").exists()
    assert (gold_dir / "item_similarity.json").exists()
    assert (gold_dir / "user_recommendations.json").exists()
