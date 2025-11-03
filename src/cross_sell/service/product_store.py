"""Utilities for persisting product catalog updates from interactive UIs."""
from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List

from ..data.ingestion import ProductRecord, read_products_csv


class ProductStore:
    """Simple CSV-backed product catalog store used by the demo UI."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def list_products(self) -> List[ProductRecord]:
        if not self.path.exists():
            return []
        return read_products_csv(self.path)

    def upsert(self, record: ProductRecord) -> ProductRecord:
        """Insert or update a product by ID.

        The backing file is rewritten on every call to keep the implementation
        straightforward and avoid partial writes.
        """

        with self._lock:
            current: Dict[str, ProductRecord] = {
                product.product_id: product for product in self.list_products()
            }
            current[record.product_id] = record
            self._write_all(current.values())
        return record

    def _write_all(self, records: Iterable[ProductRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "product_id",
                    "name",
                    "category",
                    "subcategory",
                    "brand",
                    "base_price",
                ],
            )
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))
