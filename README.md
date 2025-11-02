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

1. **(Optional) Install Python Dependencies** – The sample pipeline relies only on the Python standard library, so this step is needed only if you want parity with a richer environment.
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
