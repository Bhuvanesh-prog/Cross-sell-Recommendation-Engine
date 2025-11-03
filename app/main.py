"""FastAPI application that exposes a simple product entry UI."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cross_sell.data.ingestion import ProductRecord
from cross_sell.service.product_store import ProductStore


def _resolve_store_path() -> Path:
    configured = os.environ.get("PRODUCT_STORE_PATH")
    if configured:
        return Path(configured)
    return Path("data/user_products.csv")


app = FastAPI(title="Cross-Sell Product Admin")
templates = Jinja2Templates(directory="app/templates")
store = ProductStore(_resolve_store_path())


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
):
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


# Optional mount point for static assets if teams expand the UI.
app.mount("/static", StaticFiles(directory="app/static"), name="static")
