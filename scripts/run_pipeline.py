"""Execute the local cross-sell recommendation pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cross_sell.config import ModelConfig, PipelineConfig
from cross_sell.workflows.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--orders",
        type=Path,
        default=Path("data/sample_orders.csv"),
        help="Path to the raw orders CSV file.",
    )
    parser.add_argument(
        "--lakehouse-root",
        type=Path,
        default=Path(".lakehouse"),
        help="Directory used to persist bronze/silver/gold tables.",
    )
    parser.add_argument("--min-support", type=float, default=0.1)
    parser.add_argument("--min-confidence", type=float, default=0.3)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--als-factors", type=int, default=8)
    parser.add_argument("--als-regularization", type=float, default=0.1)
    parser.add_argument("--als-iterations", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PipelineConfig(
        lakehouse_root=args.lakehouse_root,
        orders_source=args.orders,
        model=ModelConfig(
            min_support=args.min_support,
            min_confidence=args.min_confidence,
            top_k=args.top_k,
            als_factors=args.als_factors,
            als_regularization=args.als_regularization,
            als_iterations=args.als_iterations,
        ),
    )

    artifacts = run_pipeline(config)
    print("Pipeline completed successfully. Gold tables saved under:", config.lakehouse_root / "gold")
    print("Sample user recommendations:")
    for row in artifacts["user_recommendations"][:5]:
        print(row)


if __name__ == "__main__":
    main()
