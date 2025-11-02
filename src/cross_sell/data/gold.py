"""Utilities for producing gold-zone analytical outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ..config import LakehousePaths


GOLD_TABLES = {
    "assoc_rules": "assoc_rules.json",
    "item_similarity": "item_similarity.json",
    "user_recs": "user_recommendations.json",
}


def write_gold_table(rows: List[Dict[str, object]], lakehouse: LakehousePaths, table_name: str) -> Path:
    if table_name not in GOLD_TABLES:
        raise KeyError(f"Unsupported gold table: {table_name}")
    target = lakehouse.gold / GOLD_TABLES[table_name]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as handle:
        json.dump(rows, handle, indent=2)
    return target


def load_gold_table(lakehouse: LakehousePaths, table_name: str) -> List[Dict[str, object]]:
    if table_name not in GOLD_TABLES:
        raise KeyError(f"Unsupported gold table: {table_name}")
    with (lakehouse.gold / GOLD_TABLES[table_name]).open() as handle:
        return json.load(handle)


def summarize_for_serving(lakehouse: LakehousePaths) -> Dict[str, List[Dict[str, object]]]:
    return {name: load_gold_table(lakehouse, name) for name in GOLD_TABLES}
