"""Configuration models for the cross-sell recommendation pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LakehousePaths:
    """Local directory layout that mimics a bronze/silver/gold lakehouse."""

    root: Path
    bronze: Path = field(init=False)
    silver: Path = field(init=False)
    gold: Path = field(init=False)

    def __post_init__(self) -> None:
        self.bronze = self.root / "bronze"
        self.silver = self.root / "silver"
        self.gold = self.root / "gold"
        for path in (self.bronze, self.silver, self.gold):
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelConfig:
    """Hyper-parameters used by the recommendation models."""

    min_support: float = 0.1
    min_confidence: float = 0.3
    min_lift: float = 1.0
    top_k: int = 5
    als_factors: int = 8
    als_regularization: float = 0.1
    als_iterations: int = 10


@dataclass
class PipelineConfig:
    """Aggregate configuration for the sample pipeline run."""

    lakehouse_root: Path
    orders_source: Path
    model: ModelConfig = field(default_factory=ModelConfig)

    @property
    def lakehouse(self) -> LakehousePaths:
        return LakehousePaths(self.lakehouse_root)
