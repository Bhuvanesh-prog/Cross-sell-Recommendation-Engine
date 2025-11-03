"""FastAPI application that exposes product admin APIs and optional UI."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from cross_sell.config import LakehousePaths
from cross_sell.data.ingestion import ProductRecord
from cross_sell.service.product_store import ProductStore
from cross_sell.service.recommendation_index import RecommendationIndex


def _resolve_store_path() -> Path:
    configured = os.environ.get("PRODUCT_STORE_PATH")
    if configured:
        return Path(configured)
    return Path("data/user_products.csv")


def _resolve_lakehouse_root() -> Path:
    configured = os.environ.get("LAKEHOUSE_ROOT")
    if configured:
        return Path(configured)
    return Path(".lakehouse_ui_demo")


app = FastAPI(title="Cross-Sell Product Admin")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="app/templates")
store = ProductStore(_resolve_store_path())
lakehouse_paths = LakehousePaths(_resolve_lakehouse_root())
recommendation_index = RecommendationIndex(lakehouse_paths)


class ProductPayload(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=256)
    category: str = Field(..., min_length=1, max_length=256)
    subcategory: str = Field(default="", max_length=256)
    brand: str = Field(default="", max_length=256)
    base_price: float = Field(default=0.0, ge=0.0)

    def to_record(self) -> ProductRecord:
        return ProductRecord(
            product_id=self.product_id.strip(),
            name=self.name.strip(),
            category=self.category.strip(),
            subcategory=self.subcategory.strip(),
            brand=self.brand.strip(),
            base_price=float(self.base_price),
        )


def _serialize_product(record: ProductRecord) -> Dict[str, object]:
    return asdict(record)


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": store.list_products(),
        },
    )


@app.post("/products")
async def create_product(
    product_id: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    subcategory: str = Form(""),
    brand: str = Form(""),
    base_price: float = Form(0.0),
):  # pragma: no cover - exercised via API tests
    store.upsert(
        ProductRecord(
            product_id=product_id.strip(),
            name=name.strip(),
            category=category.strip(),
            subcategory=subcategory.strip(),
            brand=brand.strip(),
            base_price=float(base_price),
        )
    )
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/api/products")
def api_list_products() -> List[Dict[str, object]]:
    return [_serialize_product(product) for product in store.list_products()]


@app.post("/api/products", status_code=status.HTTP_201_CREATED)
def api_create_product(payload: ProductPayload) -> Dict[str, object]:
    record = store.upsert(payload.to_record())
    return _serialize_product(record)


@app.get("/api/recommendations/{product_id}")
def api_recommendations(product_id: str, limit: int = 5) -> Dict[str, object]:
    if limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be positive",
        )
    recommendations = recommendation_index.recommendations_for(product_id, limit)
    return {"product_id": product_id, "recommendations": recommendations}


# Optional mount point for static assets if teams expand the UI.
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _mount_angular_dashboard() -> None:
    dist_root = os.environ.get(
        "ANGULAR_DASHBOARD_DIST",
        "frontend/angular-dashboard/dist/dashboard/browser",
    )
    dist_path = Path(dist_root)
    if dist_path.exists():
        app.mount(
            "/dashboard",
            StaticFiles(directory=dist_path, html=True),
            name="dashboard",
        )


_mount_angular_dashboard()
