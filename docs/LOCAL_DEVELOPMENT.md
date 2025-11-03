# Local Development & Testing Guide

This project ships with a self-contained Python pipeline, FastAPI backend, and optional Angular dashboard. The steps below walk through setting up a local workstation, running the pipeline, exercising the API, and executing automated tests without any Azure dependencies.

## 1. Prerequisites

| Component | Version (or later) | Notes |
| --- | --- | --- |
| Python | 3.9 | The codebase relies on type annotations and pathlib helpers tested with Python 3.9+ |
| Node.js | 18 | Required only when compiling or serving the Angular dashboard |
| npm | 9 | Bundled with Node.js; used for installing Angular dependencies |

Optional but recommended:

- **Virtual environment manager** such as `venv`, `pyenv`, or `conda` to isolate dependencies.
- **Make** or similar task runner if you prefer wrapping the commands.

## 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
```

## 3. Install Python Dependencies

Install the backend, pipeline, and testing dependencies in the activated environment:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> 💡 The requirements file includes FastAPI and Uvicorn. In restricted environments without internet access you can skip the FastAPI features by installing only the core package: `pip install -e .`. Tests that require the API will be skipped automatically when FastAPI is unavailable.

## 4. Run the Sample Pipeline

Execute the medallion pipeline using the bundled CSV data. The command writes bronze/silver/gold JSON artifacts into `.lakehouse_local/` so you can inspect the intermediate outputs:

```bash
python scripts/run_pipeline.py --lakehouse-root .lakehouse_local \
    --orders data/sample_orders.csv \
    --products data/sample_products.csv \
    --customers data/sample_customers.csv
```

Key artifacts:

- `.lakehouse_local/silver/orders.json`
- `.lakehouse_local/gold/assoc_rules.json`
- `.lakehouse_local/gold/item_similarity.json`
- `.lakehouse_local/gold/user_recommendations.json`

You can override any of the file paths to point at your own data extracts.

## 5. Launch the FastAPI Service (Optional)

The backend exposes HTML and JSON endpoints for product intake and recommendation previews. Launch it after the pipeline has produced gold artifacts:

```bash
uvicorn app.main:app --reload
```

Environment variables you may want to adjust:

- `PRODUCT_STORE_PATH` – CSV used to persist catalog submissions (`data/user_products.csv` by default).
- `LAKEHOUSE_ROOT` – Location of the gold artifacts consumed by recommendation endpoints (defaults to `.lakehouse_ui_demo`).
- `ANGULAR_DASHBOARD_DIST` – Directory containing a production build of the Angular app.

Visit `http://127.0.0.1:8000` for the templated form or `http://127.0.0.1:8000/api/products` for the REST responses.

## 6. Run Automated Tests

Pytest validates data hygiene, model quality metrics, and (when FastAPI is installed) API contract tests:

```bash
pytest
```

Tests that require FastAPI will be skipped automatically if the dependency is missing, ensuring the suite still passes in offline environments.

## 7. Work with the Angular Dashboard (Optional)

To use the interactive dashboard for catalog management and recommendations:

```bash
cd frontend/angular-dashboard
npm install
npm start
```

The dev server runs on `http://localhost:4200`. Make sure the FastAPI backend is running so the dashboard can reach the REST endpoints.

For production builds served by FastAPI:

```bash
npm run build
export ANGULAR_DASHBOARD_DIST=$(pwd)/dist/dashboard/browser
cd -  # return to repo root
uvicorn app.main:app --reload
```

## 8. Troubleshooting Tips

- **Missing FastAPI dependencies:** Install from `requirements.txt` before running Uvicorn or the API tests.
- **Permission errors writing to `.lakehouse_local/`:** Ensure your shell has write access to the working directory or change `--lakehouse-root` to a writable path.
- **Model metrics below thresholds:** The regression tests enforce minimum precision/recall targets. If you supply custom datasets, adjust the `PipelineConfig` parameters or update expectations in `tests/test_validation.py` to match your data distribution.

With these steps you can validate the entire workflow locally prior to deploying the Azure-native architecture outlined in the main README.
