from pathlib import Path

from cross_sell.data.ingestion import ProductRecord
from cross_sell.service.product_store import ProductStore


def test_product_store_roundtrip(tmp_path: Path) -> None:
    store = ProductStore(tmp_path / "products.csv")

    record = ProductRecord(
        product_id="sku-1",
        name="Widget",
        category="Accessories",
        subcategory="Cables",
        brand="Contoso",
        base_price=12.34,
    )

    store.upsert(record)
    stored = store.list_products()

    assert len(stored) == 1
    assert stored[0] == record


def test_product_store_upsert_overwrites(tmp_path: Path) -> None:
    store = ProductStore(tmp_path / "products.csv")

    first = ProductRecord(
        product_id="sku-1",
        name="Widget",
        category="Accessories",
        subcategory="Cables",
        brand="Contoso",
        base_price=12.34,
    )
    updated = ProductRecord(
        product_id="sku-1",
        name="Widget Plus",
        category="Accessories",
        subcategory="Adapters",
        brand="Fabrikam",
        base_price=15.0,
    )

    store.upsert(first)
    store.upsert(updated)

    stored = store.list_products()
    assert len(stored) == 1
    assert stored[0] == updated
