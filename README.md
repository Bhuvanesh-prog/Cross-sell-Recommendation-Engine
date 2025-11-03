# Azure Lakehouse Cross-Sell Recommendation Engine Blueprint

## 1. Project Overview
- **Business Goal:** Deliver a production-grade recommendation platform that surfaces next-best-product offers for existing customers, increasing cross-sell conversions and customer lifetime value.
- **Primary KPIs:**
  - Attach Rate uplift (% of orders containing recommended add-ons).
  - Average Order Value (AOV) uplift relative to control cohort.
  - Precision@K for top-K product recommendations.
  - Mean Average Precision@K (MAP@K) for aggregate ranked relevance.
- **Target Users:** Marketing campaign managers, sales enablement analysts, CRM operations teams, and product merchandising stakeholders who require timely, explainable recommendations to drive revenue programs.

## 2. Architecture Layers (Azure Services)
### Ingestion & Orchestration
- Azure Data Factory pipelines orchestrating batch ingestion of transactional orders, product catalog, and customer attributes from ERP/CRM sources.
- Optional Azure Event Hubs streams for near-real-time order events to capture same-day transactions.

### Storage (Delta Lakehouse)
- Azure Data Lake Storage Gen2 as unified storage with medallion architecture:
  - **Bronze** (raw landing) – landing zone for parquet/csv/json, schema-on-read.
  - **Silver** (validated & conformed) – curated Delta tables with cleaned dimensions/facts.
  - **Gold** (serving) – aggregated recommendation outputs optimized for consumption.

### Compute & Machine Learning
- Azure Databricks (premium tier) for PySpark ETL, feature engineering, FP-Growth rule mining, ALS collaborative filtering, and MLflow experiment tracking.
- Cluster policies enforcing autoscaling, job clusters for scheduled notebooks, and Unity Catalog for centralized governance.

### Warehouse / SQL Layer
- Azure Synapse Serverless SQL pools (or Snowflake on Azure) exposing Gold Delta tables for ad-hoc SQL analytics and BI connectivity.

### Operational Database (Serving Layer)
- Azure Database for PostgreSQL Flexible Server hosting curated marts: `assoc_rules`, `item_sim`, `user_topn`, `item_metadata` for low-latency API reads.

### API & Application Layer
- FastAPI microservice containerized and deployed on Azure App Service (Linux) or Azure Container Apps.
- Angular single-page app or Power BI reports consuming REST APIs and Synapse views for business-facing dashboards.

### Identity & Secrets
- Azure Entra ID (Azure AD) providing SSO for Databricks, Synapse, App Service, and Power BI.
- Managed Identities for service-to-service authentication.
- Azure Key Vault for secrets (database credentials, API keys) injected via Key Vault references.

### Monitoring & Observability
- Azure Monitor and Log Analytics aggregating infrastructure and Databricks job metrics.
- Application Insights for API telemetry, request traces, and dependency health.

## 3. Data Model
### Delta Tables in ADLS (Unity Catalog Schema `reco_lake`)
- `bronze.orders_raw` – raw transactional events (order_id, user_id, item_id, timestamp, channel, quantity, price, attributes_json).
- `bronze.products_raw` – product master data.
- `silver.orders` – cleaned fact table with conformed dimensions, deduplication, enriched categories.
- `silver.users` – consolidated customer profile features (RFM, segment, loyalty tier).
- `gold.assoc_rules` – FP-Growth results with support, confidence, lift per antecedent/consequent pair.
- `gold.item_sim` – ALS item similarity matrix (item-item cosine similarities, implicit ratings).
- `gold.user_topn` – top-N personalized recommendations (user_id, ranked product list, scores, model_version).
- `gold.model_metrics` – evaluation metrics (Precision@K, MAP@K, coverage) by model version.

### PostgreSQL Serving Schema `reco_api`
- `assoc_rules` – flattened rule set filtered for business thresholds.
- `item_sim` – nearest-neighbor lookup for item-to-item recommendations.
- `user_topn` – precomputed next-best products per active user.
- `metadata` – model lineage (version, training_date, source_path) and API configuration flags.

## 4. Machine Learning Workflow
1. **Daily Orchestration (Azure Data Factory Trigger):**
   - Execute Databricks notebook sequence for Bronze→Silver→Gold ETL (Delta Live Tables or standard jobs).
2. **Association Rule Mining:**
   - Run PySpark FP-Growth on `silver.orders` basket aggregations (user session-level). Persist results to `gold.assoc_rules` with support/confidence/lift filters.
3. **Collaborative Filtering:**
   - Train ALS implicit feedback model on user-item interaction matrix derived from `silver.orders` (weighted by frequency and recency).
   - Perform hyperparameter sweep (rank, regParam, alpha) tracked via MLflow.
4. **Top-N Generation:**
   - Produce user-personalized top-N recommendations blending ALS scores with rule-based boosts, store in `gold.user_topn`.
   - Create item-to-item similarity table for cold-start and browse experiences.
5. **PostgreSQL Sync:**
   - Databricks job writes Gold tables to PostgreSQL using JDBC (bulk upsert via `COPY` or `MERGE`).
6. **Model Governance:**
   - MLflow experiment logging (metrics, params, artifacts). Register best-performing ALS model in MLflow Model Registry with stage transitions (Staging→Production).

## 5. APIs & Endpoints
- `/recommend/user/{id}` – returns ranked next-best products for specified user using `user_topn` table with optional channel filters.
- `/recommend/item/{id}` – returns complementary products based on `item_sim` neighbors.
- `/rules/{id}` – returns FP-Growth association rules where the antecedent contains item `{id}`.
- FastAPI service integrates with PostgreSQL via SQLAlchemy, caches responses using Azure Cache for Redis (optional), and enforces Entra ID OAuth2 bearer tokens.

## 6. Governance & Security
- VNet integration for Databricks workspace, App Service, and PostgreSQL private endpoints within hub-spoke topology.
- Network Security Groups (NSGs) controlling subnet access; disable public network access on data services.
- Azure Purview cataloging for lineage (Data Factory pipelines, Databricks notebooks, Delta tables, Synapse views).
- Role-Based Access Control (RBAC) aligned with principle of least privilege (data engineers, data scientists, API operators).
- Key Vault-backed secrets, rotation policies, and Databricks secret scopes.
- Conditional Access policies enforcing MFA for privileged roles.

## 7. Infrastructure as Code (Terraform Example)
- Terraform modules provisioning:
  - Resource group, Log Analytics workspace, Application Insights.
  - Virtual Network with subnets for Databricks private link, App Service integration, PostgreSQL.
  - Azure Storage account (ADLS Gen2) with hierarchical namespace.
  - Azure Databricks workspace (Premium) with Managed Identity.
  - Azure Database for PostgreSQL Flexible Server (zone redundant) with VNet integration.
  - Azure App Service Plan (Linux) and App Service for FastAPI container.
  - Azure Key Vault with access policies for Databricks MI, App Service MI, Data Factory MI.
  - Azure Data Factory instance and pipeline definitions (optionally via ARM template deployment).
  - Optional Snowflake/Synapse resources declared via provider.
- Outputs: connection strings stored in Key Vault, Databricks workspace URL, PostgreSQL endpoint, App Service default hostname.

## 8. Runbook & Schedules
- **Daily (02:00 UTC):** Data Factory triggers Databricks ETL and sync jobs; monitor via pipeline runs and Databricks job status.
- **Hourly (Optional):** Micro-batch ingestion from Event Hubs for near-real-time updates.
- **Weekly (Sunday 03:00 UTC):** ALS model retraining with feature window refresh; FP-Growth recomputation for new associations.
- **MLflow Promotion Rules:** Promote model to Production when Precision@10 ≥ baseline + 2% and MAP@10 within SLA; require manual approval via Databricks Model Registry.
- **Monitoring:** Application Insights alerts for API latency >200 ms, Azure Monitor alerts for failed jobs, Data Factory pipeline failure notifications via Teams/Email.
- **Disaster Recovery:** Weekly full backup of PostgreSQL, daily incremental snapshots of ADLS (via storage account blob soft delete and lifecycle policies).

## 9. Performance Targets (SLOs)
- **API Latency:** p95 < 200 ms for recommendation endpoints under normal load (measured in App Insights).
- **Data Freshness:** Gold layer and PostgreSQL tables refreshed within 24 hours of source events.
- **Availability:** 99.9% uptime for API layer with App Service autoscale and zone-redundant PostgreSQL.
- **Model Quality:** Precision@10 ≥ 0.25, MAP@10 ≥ 0.18 maintained across weekly evaluations.

## 10. Quick-Start Guide

### Local Analytics Sandbox

1. **Install Python Dependencies** – Required for the product admin UI and CLI utilities.
   ```bash
   pip install -r requirements.txt
   ```
2. **Execute the Sample Pipeline** – Runs the bronze→silver→gold flow using the bundled orders, products, and customers CSVs (metadata can be overridden with CLI flags) and writes JSON tables into `.lakehouse/`.
   ```bash
   python scripts/run_pipeline.py --lakehouse-root .lakehouse \
       --orders data/sample_orders.csv \
       --products data/sample_products.csv \
       --customers data/sample_customers.csv
   ```
3. **Inspect Outputs** – Generated gold tables mirror the PostgreSQL marts defined in the architecture and now include human-readable metadata (product names, categories, customer segments).
   - `.lakehouse/gold/assoc_rules.json` → `/rules/{id}` API payloads with `lhs_details`/`rhs_details` context.
   - `.lakehouse/gold/item_similarity.json` → `/recommend/item/{id}` responses enriched with product catalog attributes.
   - `.lakehouse/gold/user_recommendations.json` → `/recommend/user/{id}` results annotated with customer segments and loyalty tiers.
4. **Run Automated Checks**
   ```bash
   pytest
   ```

The sample code demonstrates how the medallion pipeline, FP-Growth mining, and ALS collaborative filtering components interact before being lifted-and-shifted to Azure Databricks and PostgreSQL in production.

### Alternative Input Channels (Beyond CSV Uploads)

While the quick-start flow leans on local CSVs for simplicity, the architecture and codebase can source transactions, catalog data, and customer profiles from richer enterprise systems:

- **Direct CRM/ERP Connectors:** Use Azure Data Factory or Synapse pipelines with the native Salesforce Dynamics 365, SAP, or Oracle connectors to land incremental extracts straight into the **bronze** container. The bundled ingestion classes (`cross_sell.data.ingestion`) already accept iterables of `OrderRecord`, `ProductRecord`, and `CustomerRecord`, so you can swap the CSV reader with a connector that pages through CRM APIs and yields the same dataclasses.
- **Streaming & REST APIs:** Publish near-real-time events into Event Hubs or Azure Service Bus, then run a lightweight consumer (Databricks Structured Streaming job or Azure Function) that translates JSON payloads into the bronze schema. For on-demand pulls from partner APIs, schedule a Databricks notebook (or `scripts/run_pipeline.py`) with a custom loader that calls the remote endpoint (via `requests`/`aiohttp`) and feeds the response objects into the ingestion pipeline.
- **Manual or Analyst-Curated Data:** When business teams need to test hypotheses without upstream integrations, they can input orders through Power Apps/Forms or Databricks Delta tables maintained via the SQL editor. As long as the manually created rows adhere to the same column contract (order/user/product identifiers, quantities, timestamps), they can be promoted from bronze to silver using the existing validation steps; pytest fixtures (`tests/`) illustrate how to construct in-memory datasets for this purpose.

In each case, enforce the same schema and quality gates outlined in the testing plan so downstream FP-Growth and ALS stages remain stable. The medallion layout and PostgreSQL sync logic are agnostic to whether the records originated from files, APIs, or human-entered staging tables.

### Product Admin UI (Manual Catalog Curation)

Business users can capture or correct catalog details through a lightweight FastAPI experience bundled with the repo:

1. **Launch the UI locally**
   ```bash
   uvicorn app.main:app --reload
   ```
   The application stores submissions in `data/user_products.csv` by default. Set `PRODUCT_STORE_PATH=/path/to/products.csv` to change the backing file (for example, to point at a mounted ADLS path).
2. **Add or update products** – Navigate to `http://127.0.0.1:8000` and fill in the form. Records are upserted by `product_id` and can augment the existing sample catalog.
3. **Feed the pipeline** – Pass the captured CSV to the pipeline CLI so the new metadata flows into silver/gold layers:
   ```bash
   python scripts/run_pipeline.py --lakehouse-root .lakehouse \
       --products data/user_products.csv
   ```
   (Combine with `--orders`/`--customers` flags as needed. When omitted, the defaults fall back to the bundled sample data.)

The `ProductStore` helper in `src/cross_sell/service/product_store.py` reuses the ingestion dataclasses, so the same schema rules and pytest coverage protect both manual inputs and automated feeds.

### Angular Dashboard (Product Intake + Recommendation Preview)

An Angular single-page app is provided under `frontend/angular-dashboard/` for teams that prefer a richer dashboard experience when curating catalog updates and validating recommendations in the same screen.

1. **Install Node dependencies** (requires Node 18+ and npm):
   ```bash
   cd frontend/angular-dashboard
   npm install
   ```
2. **Run the development server** (served on port 4200 by default):
   ```bash
   npm start
   ```
   Ensure the FastAPI backend is running (`uvicorn app.main:app --reload`) so the dashboard can call `/api/products` and `/api/recommendations/{product_id}`.
3. **Use the dashboard** – Add a product via the form; the app posts JSON payloads to the FastAPI API, immediately refreshes the catalog list, and queries the latest item-to-item recommendations stored in `.lakehouse/gold/item_similarity.json`.
4. **Build for production** – Run `npm run build` to create static assets in `frontend/angular-dashboard/dist/dashboard/browser`. Setting `ANGULAR_DASHBOARD_DIST` when starting Uvicorn allows FastAPI to serve the compiled dashboard at `/dashboard`.

Environment flags exposed by `app/main.py`:

- `PRODUCT_STORE_PATH` – Absolute/relative CSV file used to persist catalog submissions (defaults to `data/user_products.csv`).
- `LAKEHOUSE_ROOT` – Lakehouse directory providing `gold/item_similarity.json` used for product-to-product recommendations (defaults to `.lakehouse_ui_demo`).
- `ANGULAR_DASHBOARD_DIST` – Path to a built Angular dashboard (defaults to `frontend/angular-dashboard/dist/dashboard/browser` when present).

### Azure Deployment Tasks (End-to-End Stack)

1. **Provision Infrastructure:**
   - Apply Terraform stack (`terraform init/plan/apply`) with environment variables for subscription, region, admin principals.
2. **Bootstrap Data Lake:**
   - Create Unity Catalog metastore, assign to Databricks workspace, configure external location pointing to ADLS containers (`bronze`, `silver`, `gold`).
3. **Sample Data Ingestion:**
   - Upload sample CSVs (`orders.csv`, `products.csv`, `customers.csv`) to `bronze` container.
   - Trigger Data Factory pipeline `ingest_orders` to land files into `bronze.orders_raw` Delta table.
4. **Databricks Notebook Execution:**
   - Run notebooks: `00_bronze_to_silver`, `01_silver_to_gold`, `02_fp_growth`, `03_als_training`, `04_postgres_sync` using job clusters.
   - Track experiments in MLflow UI; promote best ALS model to Production.
5. **API Deployment:**
   - Build Docker image for FastAPI service; push to Azure Container Registry; deploy to App Service with CI/CD (GitHub Actions or Azure DevOps).
   - Configure Managed Identity access to Key Vault and PostgreSQL.
6. **Visualization:**
   - Connect Power BI to Synapse Serverless views (`SELECT * FROM gold.user_topn`) and App Service REST APIs for real-time recommendation cards.
7. **Security Hardening:**
   - Enable private endpoints, configure Entra ID app registrations for API and Power BI, assign RBAC roles.
8. **Monitoring & Alerting:**
   - Configure Application Insights dashboards, Azure Monitor alerts, and Databricks job notifications.

### Azure Deployment Tasks for the Product Admin UI

To run the manual product-entry interface within Azure alongside the broader recommendation stack:

1. **Containerize the FastAPI app** – Use the provided `app/main.py` entrypoint in a lightweight Python image. Include `requirements.txt` during the build so FastAPI, Uvicorn, and Jinja2 are available.
2. **Publish to Azure Container Registry (ACR)** – Push the image and grant pull access to the App Service or Container Apps managed identity.
3. **Deploy on Azure App Service or Container Apps** – Configure `PRODUCT_STORE_PATH` to reference an Azure Files share, ADLS path mounted via Blobfuse, or (in production) an API endpoint that proxies writes into Databricks/SQL. Attach the deployment to the same virtual network as the data services and enable managed identity.
4. **Protect with Entra ID** – Register the application in Entra ID, require sign-in for catalog editors, and scope roles so only authorized merchandisers can submit changes. Use App Service authentication or an OAuth2 middleware for FastAPI.
5. **Persist catalog updates** – For production, point the store at a durable location such as:
   - An ADLS Gen2 container (bronze `products_manual` folder) ingested by the Databricks bronze job, or
   - A PostgreSQL table (`manual_products`) with stored procedures that merge entries into the master `products` dimension.
6. **Integrate with Databricks pipelines** – Extend the Bronze→Silver notebook to union the manual submissions with upstream feeds, applying Great Expectations checks to prevent malformed inputs.
7. **Monitor usage** – Emit request logs and custom metrics (product submissions per day, validation failures) to Application Insights. Configure alerts if manual updates fail so merchandisers receive feedback.

---
**Diagram (Conceptual Flow):**

```
[Source Systems] --(ADF/Event Hubs)--> [ADLS Bronze] --(Databricks ETL)--> [ADLS Silver]
      |                                                      |
      |                                            (FP-Growth / ALS)
      v                                                      v
[Azure Databricks Jobs] ------------------------------> [ADLS Gold Delta]
                                                         |
                                             (JDBC Sync via Databricks)
                                                         v
                                          [PostgreSQL Serving Layer]
                                                         |
                          [FastAPI on App Service] <---> [Angular / Power BI]
                                                         |
                                          [App Insights & Azure Monitor]
```

---
**Document Version:** v1.0 (Generated blueprint for IIT Kanpur Data Science portfolio / Enterprise proposal)
