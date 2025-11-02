"""Data ingestion helpers for the sample cross-sell pipeline."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Sequence, Type, TypeVar

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


@dataclass
class ProductRecord:
    product_id: str
    name: str
    category: str
    subcategory: str
    brand: str
    base_price: float


@dataclass
class CustomerRecord:
    user_id: str
    segment: str
    region: str
    loyalty_tier: str
    join_date: str


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


def read_products_csv(path: Path) -> List[ProductRecord]:
    records: List[ProductRecord] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                ProductRecord(
                    product_id=row["product_id"],
                    name=row["name"],
                    category=row["category"],
                    subcategory=row["subcategory"],
                    brand=row.get("brand", ""),
                    base_price=float(row.get("base_price", 0.0) or 0.0),
                )
            )
    return records


def read_customers_csv(path: Path) -> List[CustomerRecord]:
    records: List[CustomerRecord] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                CustomerRecord(
                    user_id=row["user_id"],
                    segment=row["segment"],
                    region=row.get("region", ""),
                    loyalty_tier=row.get("loyalty_tier", ""),
                    join_date=row.get("join_date", ""),
                )
            )
    return records


TRecord = TypeVar("TRecord")


def _write_json(records: Sequence[TRecord], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as handle:
        json.dump([asdict(record) for record in records], handle, indent=2)
    return target


def _read_json(path: Path, record_type: Type[TRecord]) -> List[TRecord]:
    with path.open() as handle:
        raw = json.load(handle)
    return [record_type(**row) for row in raw]


def write_bronze_orders(records: List[OrderRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.bronze / "orders_raw.json")


def load_bronze_orders(lakehouse: LakehousePaths) -> List[OrderRecord]:
    return _read_json(lakehouse.bronze / "orders_raw.json", OrderRecord)


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
    return _read_json(lakehouse.silver / "orders.json", OrderRecord)


def cleanse_products(bronze_records: Sequence[ProductRecord]) -> List[ProductRecord]:
    seen = set()
    cleansed: List[ProductRecord] = []
    for record in bronze_records:
        if not record.product_id:
            continue
        if record.product_id in seen:
            continue
        seen.add(record.product_id)
        base_price = record.base_price if record.base_price >= 0 else 0.0
        cleansed.append(
            ProductRecord(
                product_id=record.product_id,
                name=record.name or record.product_id,
                category=record.category or "uncategorized",
                subcategory=record.subcategory or "uncategorized",
                brand=record.brand or "unknown",
                base_price=base_price,
            )
        )
    return cleansed


def write_bronze_products(records: List[ProductRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.bronze / "products_raw.json")


def load_bronze_products(lakehouse: LakehousePaths) -> List[ProductRecord]:
    return _read_json(lakehouse.bronze / "products_raw.json", ProductRecord)


def write_silver_products(records: List[ProductRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.silver / "products.json")


def load_silver_products(lakehouse: LakehousePaths) -> List[ProductRecord]:
    return _read_json(lakehouse.silver / "products.json", ProductRecord)


def cleanse_customers(bronze_records: Sequence[CustomerRecord]) -> List[CustomerRecord]:
    seen = set()
    cleansed: List[CustomerRecord] = []
    for record in bronze_records:
        if not record.user_id:
            continue
        if record.user_id in seen:
            continue
        seen.add(record.user_id)
        cleansed.append(
            CustomerRecord(
                user_id=record.user_id,
                segment=record.segment or "unassigned",
                region=record.region or "unknown",
                loyalty_tier=record.loyalty_tier or "standard",
                join_date=record.join_date or "",
            )
        )
    return cleansed


def write_bronze_customers(records: List[CustomerRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.bronze / "customers_raw.json")


def load_bronze_customers(lakehouse: LakehousePaths) -> List[CustomerRecord]:
    return _read_json(lakehouse.bronze / "customers_raw.json", CustomerRecord)


def write_silver_customers(records: List[CustomerRecord], lakehouse: LakehousePaths) -> Path:
    return _write_json(records, lakehouse.silver / "customers.json")


def load_silver_customers(lakehouse: LakehousePaths) -> List[CustomerRecord]:
    return _read_json(lakehouse.silver / "customers.json", CustomerRecord)
