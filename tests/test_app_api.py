import json
from importlib import reload

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    product_path = tmp_path / "products.csv"
    lakehouse_root = tmp_path / "lakehouse"
    gold_dir = lakehouse_root / "gold"
    gold_dir.mkdir(parents=True)
    sample_similarity = [
        {
            "product_id": "SKU-1",
            "similar_product_id": "SKU-2",
            "similar_product_name": "Cable",
            "similar_product_category": "Accessories",
            "similar_product_brand": "Fabrikam",
            "score": 0.42,
        },
        {
            "product_id": "SKU-1",
            "similar_product_id": "SKU-3",
            "similar_product_name": "Charger",
            "similar_product_category": "Power",
            "similar_product_brand": "Contoso",
            "score": 0.37,
        },
    ]
    with (gold_dir / "item_similarity.json").open("w") as handle:
        json.dump(sample_similarity, handle)

    monkeypatch.setenv("PRODUCT_STORE_PATH", str(product_path))
    monkeypatch.setenv("LAKEHOUSE_ROOT", str(lakehouse_root))

    from app import main

    reload(main)
    client = TestClient(main.app)

    yield client

    client.close()


def test_api_product_crud_and_recommendations(api_client: TestClient):
    create_response = api_client.post(
        "/api/products",
        json={
            "product_id": "SKU-1",
            "name": "Wireless Mouse",
            "category": "Accessories",
            "subcategory": "Peripherals",
            "brand": "Contoso",
            "base_price": 49.99,
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["product_id"] == "SKU-1"
    assert body["name"] == "Wireless Mouse"

    list_response = api_client.get("/api/products")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["product_id"] == "SKU-1"

    rec_response = api_client.get("/api/recommendations/SKU-1", params={"limit": 1})
    assert rec_response.status_code == 200
    payload = rec_response.json()
    assert payload["product_id"] == "SKU-1"
    assert len(payload["recommendations"]) == 1
    assert payload["recommendations"][0]["similar_product_id"] == "SKU-2"


def test_limit_validation(api_client: TestClient):
    response = api_client.get("/api/recommendations/SKU-1", params={"limit": 0})
    assert response.status_code == 400
    assert response.json()["detail"] == "limit must be positive"
