"""Data ingestion helpers for the sample cross-sell pipeline."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

from ..config import LakehousePaths


@dataclass
class OrderRecord:
    order_id: str
    user_id: str
    product_id: str
    quantity: int
    unit_price: float
    order_ts: str
    sales_channel: str


def read_orders_csv(path: Path) -> List[OrderRecord]:
    records: List[OrderRecord] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                OrderRecord(
                    order_id=row["order_id"],
                    user_id=row["user_id"],
                    product_id=row["product_id"],
                    quantity=int(float(row["quantity"] or 0) or 0),
                    unit_price=float(row["unit_price"] or 0.0),
                    order_ts=row["order_ts"],
                    sales_channel=row["sales_channel"],
                )
            )
    return records


def _write_json(records: List[OrderRecord], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as handle:
        json.dump([asdict(record) for record in records], handle, indent=2)
    return target


def _read_json(path: Path) -> List[OrderRecord]:
    with path.open() as handle:
        raw = json.load(handle)
    return [OrderRecord(**row) for row in raw]


def write_bronze_orders(records: List[OrderRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.bronze / "orders_raw.json")


def load_bronze_orders(lakehouse: LakehousePaths) -> List[OrderRecord]:
    return _read_json(lakehouse.bronze / "orders_raw.json")


def cleanse_orders(bronze_records: List[OrderRecord]) -> List[OrderRecord]:
    seen = set()
    cleansed: List[OrderRecord] = []
    for record in bronze_records:
        key = (record.order_id, record.product_id)
        if key in seen:
            continue
        seen.add(key)
        quantity = record.quantity if record.quantity > 0 else 1
        unit_price = record.unit_price if record.unit_price >= 0 else 0.0
        if not record.user_id or not record.product_id or not record.order_ts:
            continue
        cleansed.append(
            OrderRecord(
                order_id=record.order_id,
                user_id=record.user_id,
                product_id=record.product_id,
                quantity=quantity,
                unit_price=unit_price,
                order_ts=record.order_ts,
                sales_channel=record.sales_channel or "unknown",
            )
        )
    return cleansed


def write_silver_orders(records: List[OrderRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.silver / "orders.json")


def load_silver_orders(lakehouse: LakehousePaths) -> List[OrderRecord]:
    return _read_json(lakehouse.silver / "orders.json")
